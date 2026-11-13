#!/usr/bin/env python3
"""Exercise recursive folder copy, move, and delete in the UK TOS 2.06 desktop.

Usage: python3 test/check_desktop_folders.py ROM LINKED_IMAGE --output DIR
Uses disposable host drives and real desktop input under Hatari.
"""

import argparse
import json
from pathlib import Path
import tempfile

from check_desktop_operations import Desktop, word
from check_show_information import ROOT, symbols

OPERATIONS = ("folder-copy", "folder-move", "folder-delete")


def fixture(drive, operation):
    source = drive / "SOURCE"
    (source / "NESTED").mkdir(parents=True)
    (source / "EMPTY").mkdir()
    files = {
        "ROOT.DAT": bytes(range(256)) * 17 + b"root-odd-boundary!",
        "NESTED/INNER.BIN": bytes(reversed(range(256))) * 3 + b"tail",
        "NESTED/TINY.TXT": b"x",
    }
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    sentinel = b"unrelated root data\x00\xff"
    (drive / "SENTINEL.DAT").write_bytes(sentinel)
    if operation != "folder-delete":
        (drive / "TARGET").mkdir()
    if operation == "folder-delete":
        keys = [0] * 29
        for index, key in ((0, "O"), (1, "S"), (2, "L"), (3, "D"),
                           (4, "F"), (5, "B"), (6, "C"), (7, "W"),
                           (8, "E"), (9, "X"), (12, "T"), (27, "V")):
            keys[index] = ord(key)
        initial = (ROOT / "desk/rsc/206/deskuk.inf").read_bytes().rstrip(b"\0\x1a\r\n")
        (drive / "NEWDESK.INF").write_bytes(
            initial + b"\r\n#K " + " ".join(f"{key:02X}" for key in keys).encode("ascii") + b" @\r\n"
        )
    return files, sentinel


def assert_tree(root, files, label):
    expected = {"NESTED": True, "EMPTY": True, **dict.fromkeys(files, False)}
    actual = {path.relative_to(root).as_posix(): path.is_dir() for path in root.rglob("*")}
    if actual != expected:
        raise AssertionError(f"{label}: tree/kind mismatch, expected {expected}, got {actual}")
    for relative, content in files.items():
        path = root / relative
        if not path.is_file() or path.read_bytes() != content:
            raise AssertionError(f"{label}: incorrect contents for {relative}")


def run(rom, syms, output, operations):
    results = []
    for operation in operations:
        with tempfile.TemporaryDirectory(prefix="tos-folders-") as tmp:
            drive = Path(tmp)
            files, sentinel = fixture(drive, operation)
            with Desktop(rom, syms, drive, output, operation) as ui:
                ui.open_c()
                if operation in ("folder-copy", "folder-move"):
                    ui.drag("SOURCE", "TARGET", operation == "folder-move")
                    destination = drive / "TARGET/SOURCE"
                    ui.wait(lambda: destination.is_dir(), "destination folder")
                    ui.wait(lambda: all((destination / name).is_file() and (destination / name).read_bytes() == data
                                        for name, data in files.items()), "complete recursive folder contents")
                    source = drive / "SOURCE"
                    ui.wait(lambda: source.exists() == (operation == "folder-copy"), "source folder disposition")
                else:
                    ui.select("SOURCE")
                    token = ui.arm_dialog("confirm")
                    ui.key("d")
                    ui.dialog(token)
                    ready = ui.arm_desktop()
                    ui.key(28)
                    ui.desktop(ready)
                    ui.wait(lambda: not (drive / "SOURCE").exists(), "recursive folder deletion")
                # A real selection proves the desktop is accepting input after the operation.
                ui.select("SENTINEL.DAT")
                if operation in ("folder-copy", "folder-move"):
                    assert_tree(destination, files, operation)
                    if operation == "folder-copy":
                        assert_tree(source, files, operation + " source")
                if (drive / "SENTINEL.DAT").read_bytes() != sentinel:
                    raise AssertionError(f"{operation}: unrelated sentinel changed")
                ui.screenshot("result")
            results.append(operation)
            print(f"PASS {operation}", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("linked_image", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--operation", choices=OPERATIONS, action="append",
                        help="Run only the selected operation (repeatable)")
    args = parser.parse_args()
    rom = args.rom.resolve()
    header = rom.read_bytes()[:32]
    if word(header, 2) != 0x206 or (word(header, 28) >> 1) != 3:
        parser.error("requires UK TOS 2.06 with its built-in default desktop resources")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = run(rom, symbols(args.linked_image.resolve()), output, args.operation or OPERATIONS)
    (output / "results.json").write_text(json.dumps({"passed": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
