#!/usr/bin/env python3
"""Build a self-contained 720 KiB DD test floppy using bundled Alcyon tools.

Usage: mise run guest-disk -- --output build/guest-disk
Requires Linux x86_64 and mtools, but no ROM, symbols, Hatari or disk driver.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

DISK_README = """NATIVE GEMDOS REGRESSION DISK

Use dedicated writable test media. No ROM is supplied or installed.
This is a 720 KiB DD FAT12 image for a 68000 ST-family machine.

Boot cleanly from A: (disable hard-disk boot/other AUTO programs), or run
A:\\AUTO\\REGRESS.PRG manually from the desktop. Keep this disk in A:.
The child and directory fixtures must remain at their supplied locations.

Tests: memory allocation/free/positive shrink; child launch/exit; native
file reads across 128 directories. The program writes A:\\RESULT.TXT.
The console may clear when the desktop starts: open RESULT.TXT afterward.
Success is exactly:
PASS memory
PASS process
PASS filesystem
DONE

A missing, incomplete or FAIL report is not success. Preserve the report
and record ROM version/patches, RAM, machine and resident software. Compare
with stock TOS using the same fixture. Results alone cannot identify a ROM
bug versus hardware, driver or resident-software behavior.

The workload does not prove the expanded folder pool's capacity boundary,
ACSI reliability, or disk-full recovery. This image contains fixtures, not
an operating system: the installed TOS ROM runs the tests.
"""


def build_guest(work, log, programs):
    tools = ROOT / "bin/linux"
    for source in ("guest_start.s", *programs.values()):
        shutil.copy2(ROOT / "test" / source, work / source)
    for library in ("gem.a", "libc.a"):
        shutil.copy2(ROOT / "lib" / library, work / library)
    for source in ("guest_start.s", *programs.values()):
        subprocess.run([str(tools / "cc68"), "-c", source], cwd=work,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
    for name, source in programs.items():
        subprocess.run([str(tools / "link68"), "[sy,locals]",
                        f"{name}.rel=guest_start.o,{Path(source).stem}.o,gem.a,libc.a"], cwd=work,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
        subprocess.run([str(tools / "relmod"), f"{name}.rel", f"{name}.PRG"], cwd=work,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)


def make_floppy(work, image, zero_shrink):
    image.write_bytes(bytes(720 * 1024))
    subprocess.run(["mformat", "-i", str(image), "-f", "720", "::"], check=True)
    tree = work / "drive"
    (tree / "AUTO").mkdir(parents=True)
    shutil.copy2(work / "REGRESS.PRG", tree / "AUTO/REGRESS.PRG")
    shutil.copy2(work / "CHILD.PRG", tree / "CHILD.PRG")
    readme = DISK_README
    if zero_shrink:
        shutil.copy2(work / "ZERO.PRG", tree / "AUTO/ZERO.PRG")
        readme += ("\nZERO-LENGTH MSHRINK PROBE ENABLED: requires TP_29.\n"
                   "Do not run this variant on stock TOS on real hardware: the\n"
                   "known bug corrupts memory lists. Also require ZERO.TXT to\n"
                   "contain PASS zero-shrink followed by DONE.\n")
    (tree / "README.TXT").write_bytes(readme.replace("\n", "\r\n").encode("ascii"))
    for outer in range(8):
        for inner in range(16):
            directory = tree / f"D{outer:02d}" / f"S{inner:02d}"
            directory.mkdir(parents=True)
            (directory / "DATA.BIN").write_bytes(
                bytes((i + outer * 17 + inner * 3) & 255 for i in range(257)))
    subprocess.run(["mcopy", "-s", "-i", str(image),
                    *[str(path) for path in sorted(tree.iterdir())], "::"], check=True)


def build_disk(output, zero_shrink=False):
    if sys.platform != "linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise ValueError("the bundled guest toolchain requires Linux x86_64")
    for command in ("mformat", "mcopy"):
        if shutil.which(command) is None:
            raise ValueError(f"missing {command}; install mtools (apt install mtools)")
    for name in ("cc68", "cp68", "c068", "c168", "as68", "link68", "relmod"):
        if not os.access(ROOT / "bin/linux" / name, os.X_OK):
            raise ValueError(f"missing executable bundled tool bin/linux/{name}")
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.json"
    manifest.unlink(missing_ok=True)
    programs = {"REGRESS": "guest_regress.c", "CHILD": "guest_child.c"}
    if zero_shrink:
        programs["ZERO"] = "guest_zero.c"
    with tempfile.TemporaryDirectory(prefix="tos-guest-build-") as tmp:
        work = Path(tmp)
        with (output / "build.log").open("w") as log:
            build_guest(work, log, programs)
        for name in programs:
            shutil.copy2(work / f"{name}.PRG", output / f"{name}.PRG")
        image = output / "native-test.st"
        make_floppy(work, image, zero_shrink)
        data = {
            "built_image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "image_bytes": image.stat().st_size,
            "geometry": {"tracks": 80, "sides": 2, "sectors_per_track": 9, "sector_bytes": 512},
            "zero_shrink_probe": zero_shrink,
            "program_sha256": {f"{name}.PRG": hashlib.sha256((output / f"{name}.PRG").read_bytes()).hexdigest()
                               for name in programs},
        }
        manifest.write_text(json.dumps(data, indent=2) + "\n")
        return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/guest-disk",
                        help="artifact directory (default: build/guest-disk)")
    parser.add_argument("--zero-shrink", action="store_true",
                        help="Include the TP_29 probe (unsafe on stock TOS; default: off)")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.zero_shrink:
        print("WARNING: zero-shrink probe requires TP_29; use disposable test media.", file=sys.stderr)
    try:
        image = build_disk(output, zero_shrink=args.zero_shrink)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\nArtifacts: {output}\n")
    print(f"Built hardware test disk: {image}")
    print("Boot from writable A: media; inspect A:\\RESULT.TXT after the test.")


if __name__ == "__main__":
    main()
