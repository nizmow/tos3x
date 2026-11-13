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

from check_show_information import ROOT, symbols

EXPECTED = ["PASS memory", "PASS process", "PASS filesystem", "DONE"]


def build_guest(work, log):
    tools = ROOT / "bin/linux"
    for source in ("guest_start.s", "guest_regress.c", "guest_child.c"):
        shutil.copy2(ROOT / "test" / source, work / source)
    for library in ("gem.a", "libc.a"):
        shutil.copy2(ROOT / "lib" / library, work / library)
    for source in ("guest_start.s", "guest_regress.c", "guest_child.c"):
        subprocess.run([str(tools / "cc68"), "-c", source], cwd=work,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
    for name, obj in (("REGRESS", "guest_regress.o"), ("CHILD", "guest_child.o")):
        subprocess.run([str(tools / "link68"), "[sy,locals]",
                        f"{name}.rel=guest_start.o,{obj},gem.a,libc.a"], cwd=work,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
        subprocess.run([str(tools / "relmod"), f"{name}.rel", f"{name}.PRG"], cwd=work,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)


def make_floppy(work, image):
    image.write_bytes(bytes(720 * 1024))
    subprocess.run(["mformat", "-i", str(image), "-f", "720", "::"], check=True)
    tree = work / "drive"
    (tree / "AUTO").mkdir(parents=True)
    shutil.copy2(work / "REGRESS.PRG", tree / "AUTO/REGRESS.PRG")
    shutil.copy2(work / "CHILD.PRG", tree / "CHILD.PRG")
    for outer in range(8):
        for inner in range(16):
            directory = tree / f"D{outer:02d}" / f"S{inner:02d}"
            directory.mkdir(parents=True)
            (directory / "DATA.BIN").write_bytes(
                bytes((i + outer * 17 + inner * 3) & 255 for i in range(257)))
    subprocess.run(["mcopy", "-s", "-i", str(image),
                    *[str(path) for path in sorted(tree.iterdir())], "::"], check=True)


def run(rom, linked_image, output, timeout):
    for command in ("hatari", "mformat", "mcopy"):
        if shutil.which(command) is None:
            raise ValueError(f"missing {command}; install Hatari and mtools")
    syms = symbols(linked_image)
    pool_size = syms["_bpbsums"] - syms["_ofdbuf"]
    if pool_size <= 0 or pool_size % 70:
        raise ValueError("unsupported linked filesystem-pool layout")
    with tempfile.TemporaryDirectory(prefix="tos-guest-") as tmp:
        work = Path(tmp)
        with (output / "build.log").open("w") as log:
            build_guest(work, log)
        for name in ("REGRESS.PRG", "CHILD.PRG"):
            shutil.copy2(work / name, output / name)
        image = output / "native-test.st"
        make_floppy(work, image)
        marker = work / "desktop.bin"
        pool = output / "pool.bin"
        console = output / "guest-console.png"
        console.unlink(missing_ok=True)
        guest_exit = work / "guest-exit.ini"
        # Refresh at each child/parent exit; the parent's final exit captures
        # the complete report before AES clears the boot console.
        guest_exit.write_text(f"screenshot {console}\nc\n")
        finish = work / "finish.ini"
        finish.write_text(
            f"savebin {pool} ${syms['_ofdbuf']:x} {pool_size}\n"
            f"savebin {marker} 0 1\nquit\n")
        boot = work / "boot.ini"
        boot.write_text(
            f"b PC = ${syms['_xterm']:x} :trace :file {guest_exit}\n"
            f"b PC = ${syms['_deskmain']:x} :once :file {finish}\nc\n")
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", HOME=str(work))
        command = [
            "hatari", "--configfile", "/dev/null", "--machine", "megaste",
            "--memsize", "4", "--mono", "--tos", str(rom),
            "--disk-a", str(image), "--drive-b", "off", "--protect-floppy", "off",
            "--sound", "off", "--fast-forward", "yes", "--fast-boot", "yes",
            "--fastfdc", "yes", "--confirm-quit", "no", "--run-vbls", "30000",
            "--trace", "gemdos", "--trace-file", str(output / "gemdos.log"),
            "--parse", str(boot),
        ]
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
        data = pool.read_bytes()
        if len(data) != pool_size:
            raise AssertionError("incomplete post-guest pool capture")
        flags = [struct.unpack_from(">h", data, offset + 4)[0] for offset in range(0, pool_size, 70)]
        result = {
            "passed": ["memory", "process", "filesystem"],
            "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
            "guest_sha256": hashlib.sha256((output / "REGRESS.PRG").read_bytes()).hexdigest(),
            "filesystem": {"backend": "native FAT12 floppy", "leaf_directories": 128, "rounds": 3},
            "pool_at_desktop_entry": {"blocks": len(flags), "unused_blocks": flags.count(0)},
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
        run(rom, args.linked_image.resolve(), output, args.timeout)
    except (ValueError, AssertionError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\nArtifacts: {output}\n")


if __name__ == "__main__":
    main()
