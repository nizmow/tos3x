#!/usr/bin/env python3
"""Build and boot native GEMDOS probes on a disposable FAT12 floppy.

Usage: python3 test/check_guest_gemdos.py ROM LINKED_IMAGE --output DIR
Requires Linux x86_64 bundled Alcyon tools, Hatari and mtools. No GEMDOS host
folder, hard-disk driver, network access or user disk/configuration is used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from build_guest_disk import build_disk
from check_show_information import symbols

EXPECTED = ["PASS memory", "PASS process", "PASS filesystem", "DONE"]


def run(rom, linked_image, output, timeout, *, zero_shrink=False, check_auto_stack=False, full_boot=False):
    if shutil.which("hatari") is None:
        raise ValueError("missing hatari; install Hatari to run emulator checks")
    syms = symbols(linked_image)
    pool_size = syms["_bpbsums"] - syms["_ofdbuf"]
    if pool_size <= 0 or pool_size % 70:
        raise ValueError("unsupported linked filesystem-pool layout")
    image = build_disk(output, zero_shrink=zero_shrink)
    with tempfile.TemporaryDirectory(prefix="tos-guest-") as tmp:
        work = Path(tmp)
        marker = work / "desktop.bin"
        pool = output / "pool.bin"
        console = output / "guest-console.png"
        console.unlink(missing_ok=True)
        exit_status = output / "guest-exit.bin"
        exit_status.unlink(missing_ok=True)
        guest_exit = work / "guest-exit.ini"
        # Refresh at each child/parent exit; the parent's final exit captures
        # the complete report before AES clears the boot console.
        guest_exit.write_text(
            f"screenshot {console}\n"
            f'savebin {exit_status} "a7+4" 2\nc\n')
        finish = work / "finish.ini"
        finish.write_text(
            f"savebin {pool} ${syms['_ofdbuf']:x} {pool_size}\n"
            f"savebin {marker} 0 1\nquit\n")
        boot = work / "boot.ini"
        breakpoints = (
            f"b PC = ${syms['_xterm']:x} :trace :file {guest_exit}\n"
            f"b PC = ${syms['_deskmain']:x} :once :file {finish}\n")
        if check_auto_stack:
            auto_frame = output / "auto-frame.bin"
            auto_page = output / "auto-basepage.bin"
            auto_frame.unlink(missing_ok=True)
            auto_page.unlink(missing_ok=True)
            capture = work / "auto-stack.ini"
            capture.write_text(
                f'savebin {auto_frame} "a7" 8\n'
                f'savebin {auto_page} "a6" 256\nc\n')
            breakpoints += f"b PC = ${syms['autosca1']:x} :once :file {capture}\n"
        boot.write_text(breakpoints + "c\n")
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", HOME=str(work))
        command = [
            "hatari", "--configfile", "/dev/null", "--machine", "megaste",
            "--memsize", "4", "--mono", "--tos", str(rom),
            "--disk-a", str(image), "--drive-b", "off", "--protect-floppy", "off",
            "--sound", "off", "--fast-forward", "yes", "--fast-boot", "no" if full_boot else "yes",
            "--fastfdc", "no" if full_boot else "yes", "--confirm-quit", "no", "--run-vbls", "30000",
            "--trace", "gemdos", "--trace-file", str(output / "gemdos.log"),
            "--parse", str(boot),
        ]
        if full_boot:
            command += ["--patch-tos", "no", "--timer-d", "no"]
        with (output / "hatari.log").open("w") as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=timeout)
        if not marker.exists():
            raise AssertionError("guest did not return to desktop; inspect hatari.log/gemdos.log")
        if not console.exists() or console.stat().st_size == 0:
            raise AssertionError("guest exit console was not captured; inspect hatari.log")
        report = output / "guest-result.txt"
        subprocess.run(["mcopy", "-o", "-i", str(image), "::RESULT.TXT", str(report)], check=True)
        lines = report.read_text(encoding="ascii").splitlines()
        for line in lines:
            print(line, flush=True)
        if lines != EXPECTED:
            raise AssertionError(f"guest report does not match successful completion: {lines}")
        if exit_status.read_bytes() != b"\0\0":
            raise AssertionError("last AUTO program exited nonzero; inspect guest console/log")
        passed = ["memory", "process", "filesystem"]
        if zero_shrink:
            zero_report = output / "zero-result.txt"
            subprocess.run(["mcopy", "-o", "-i", str(image), "::ZERO.TXT", str(zero_report)], check=True)
            zero_lines = zero_report.read_text(encoding="ascii").splitlines()
            for line in zero_lines:
                print(line, flush=True)
            if zero_lines != ["PASS zero-shrink", "DONE"]:
                raise AssertionError(f"zero-length Mshrink regression failed: {zero_lines}")
            passed.append("zero-shrink")
        if check_auto_stack:
            frame, page = auto_frame.read_bytes(), auto_page.read_bytes()
            # AUTO's public GEMDOS Fsfirst arguments are WORD/LONG/WORD (8
            # bytes), below the 256-byte basepage end after Mshrink cleanup.
            if len(frame) != 8 or len(page) != 256 or frame != page[-8:]:
                raise AssertionError(
                    f"AUTO Fsfirst frame at basepage offset {page.find(frame)}, expected 248")
            if struct.unpack_from(">H", frame)[0] != 0x4e or struct.unpack_from(">H", frame, 6)[0] != 7:
                raise AssertionError("AUTO Fsfirst has invalid opcode/attribute arguments")
            print("PASS auto-stack", flush=True)
            passed.append("auto-stack")
        data = pool.read_bytes()
        if len(data) != pool_size:
            raise AssertionError("incomplete post-guest pool capture")
        flags = [struct.unpack_from(">h", data, offset + 4)[0] for offset in range(0, pool_size, 70)]
        result = {
            "passed": passed,
            "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
            "guest_sha256": hashlib.sha256((output / "REGRESS.PRG").read_bytes()).hexdigest(),
            "filesystem": {"backend": "native FAT12 floppy", "leaf_directories": 128, "rounds": 3},
            "pool_at_desktop_entry": {"blocks": len(flags), "unused_blocks": flags.count(0)},
            "unpatched_full_boot": full_boot,
        }
        (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("linked_image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120,
                        help="Hatari wall-clock deadline in seconds (default: 120)")
    parser.add_argument("--zero-shrink", action="store_true",
                        help="Include the TP_29 regression (known unsafe on stock TOS)")
    parser.add_argument("--check-auto-stack", action="store_true",
                        help="Require correctly balanced AUTO GEMDOS stack (TP_15)")
    parser.add_argument("--full-boot", action="store_true",
                        help="Disable Hatari TOS patches, fast boot, and fast FDC")
    args = parser.parse_args()
    rom = args.rom.resolve()
    header = rom.read_bytes()[:32]
    if len(header) != 32 or struct.unpack_from(">H", header, 2)[0] != 0x206:
        parser.error("this runner currently targets TOS 2.06 / Mega STE")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave an earlier successful result manifest.
    (output / "results.json").unlink(missing_ok=True)
    try:
        run(rom, args.linked_image.resolve(), output, args.timeout,
            zero_shrink=args.zero_shrink, check_auto_stack=args.check_auto_stack,
            full_boot=args.full_boot)
    except (ValueError, AssertionError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\nArtifacts: {output}\n")


if __name__ == "__main__":
    main()
