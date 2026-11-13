#!/usr/bin/env python3
"""Check native GNU preprocessing of the custom 2.06/3.06 RTC assembly.

This checks the compiler frontend only, not a complete GNU-built ROM or RTC
hardware. It needs gcc, but no m68k compiler and no generated/local config.
"""

import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpp", default="gcc", help="GNU-compatible C preprocessor driver")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tos-cpp-") as directory:
        directory = Path(directory)
        for version in ("206", "306"):
            (directory / "config.h").write_text(
                f"#define TOSVERSION 0x{version}\n"
                "#define BINEXACT 0\n#define OS_COUNTRY CTRY_UK\n"
                "#define RAMVERSION 0\n#define HADES 0\n#define MEDUSA 0\n"
                '#include "ctrycode.h"\n#include "patchdef.h"\n#include "nopatch.h"\n'
            )
            subprocess.run([
                args.cpp, "-E", "-P", "-x", "assembler-with-cpp",
                "-I" + str(directory), "-I" + str(ROOT / "common"),
                "-I" + str(ROOT / "include"), str(ROOT / "bios/nvram.S"),
                "-o", str(directory / "nvram.i"),
            ], check=True)
            print(f"PASS TOS {version}: GNU RTC preprocessing")


if __name__ == "__main__":
    main()
