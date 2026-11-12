#!/usr/bin/env python3
"""Check that an Alcyon-linked ROM reserves all its BSS before the TPA."""

import argparse
import struct
from pathlib import Path


def check(path):
    linked = path.read_bytes()
    if len(linked) < 36 or struct.unpack_from(">H", linked)[0] != 0x601B:
        raise ValueError("expected an absolute Alcyon link image (glue/tos.img)")
    bss_size = struct.unpack_from(">I", linked, 10)[0]
    bss_base = struct.unpack_from(">I", linked, 32)[0]
    rom = linked[36:]
    rom_base = struct.unpack_from(">I", rom, 8)[0]
    gem_mupb = struct.unpack_from(">I", rom, 20)[0] - rom_base
    if gem_mupb < 0 or gem_mupb + 12 > len(rom):
        raise ValueError("GEM memory descriptor is outside the ROM")
    magic, os_end = struct.unpack_from(">II", rom, gem_mupb)
    if magic != 0x87654321:
        raise ValueError("GEM memory descriptor has invalid magic")
    bss_end = bss_base + bss_size
    if os_end < bss_end:
        raise ValueError(
            f"TPA starts at ${os_end:x}, overlapping live OS BSS through ${bss_end:x}"
        )
    print(f"{path}: OS reserves BSS through ${bss_end:x}; TPA starts at ${os_end:x}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        check(args.image)
    except (ValueError, struct.error) as error:
        parser.exit(1, f"{args.image}: {error}\n")
