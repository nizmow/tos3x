#!/usr/bin/env python3
"""Exercise UK TOS 2.06 filename conflicts on disposable Hatari drives.

Usage: python3 test/check_desktop_conflicts.py ROM LINKED_IMAGE --output DIR
Uses the real desktop input harness; no guest function calls or RAM writes.
"""

import argparse
import json
from pathlib import Path
import tempfile

from check_desktop_operations import Desktop, word
from check_show_information import long_at, symbols

OPERATIONS = ("overwrite", "conflict-cancel", "rename-collision")


def snapshot(root):
    """Include empty directories and exact file contents, not host timestamps."""
    return {path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
            for path in sorted(root.rglob("*"))}


def objects(data, tree):
    # GEM OBJECT arrays end at LASTOB. Keep corrupt dialog data bounded.
    for index in range(64):
        yield index, word(data, tree + index * 24 + 6) & 0xff
        if word(data, tree + index * 24 + 8) & 0x20:
            return
    raise AssertionError("dialog has no LASTOB within 64 objects")


def finish_dialog(ui, data, tree, label):
    buttons = {}
    for index, kind in objects(data, tree):
        if kind == 26:  # G_BUTTON stores a direct string pointer.
            text = ui.string(data, long_at(data, tree + index * 24 + 12)).strip()
            buttons[text.casefold()] = index
    if label.casefold() not in buttons:
        raise AssertionError(f"{ui.label}: expected {label!r} button, found {list(buttons)}")
    token = ui.arm_desktop()
    ui.click(*ui.center(data, tree, buttons[label.casefold()]))
    ui.desktop(token)


def dialog_text(ui, data, tree):
    result = []
    for index, kind in objects(data, tree):
        if kind in (21, 22, 29, 30):  # TEXT/BOXTEXT/FTEXT/FBOXTEXT use TEDINFO.
            result.append(ui.field(data, tree, index))
        elif kind in (26, 28, 32):  # BUTTON/STRING/TITLE use direct strings.
            result.append(ui.string(data, long_at(data, tree + index * 24 + 12)))
    return result


def check_conflict(ui, data, tree):
    if "CONFLICT" not in ui.field(data, tree, 1).upper():
        raise AssertionError(f"{ui.label}: expected filename-conflict dialog")
    for index in (2, 3):
        if ui.field(data, tree, index).replace(" ", "").replace(".", "") != "SOURCETXT":
            raise AssertionError(f"{ui.label}: conflict names do not identify SOURCE.TXT")


def run(rom, syms, output, operations):
    passed = []
    payload = bytes(range(256)) * 39 + b"odd-boundary!"
    previous = b"old destination data, including a tail that must be truncated\n" * 1024
    for operation in operations:
        with tempfile.TemporaryDirectory(prefix="tos-conflict-") as tmp:
            drive = Path(tmp)
            (drive / "SOURCE.TXT").write_bytes(payload)
            (drive / "KEEP.BIN").write_bytes(b"unselected sentinel must remain untouched\0\xff")
            if operation == "rename-collision":
                (drive / "EXISTING.TXT").write_bytes(previous)
            else:
                (drive / "TARGET").mkdir()
                (drive / "TARGET/SOURCE.TXT").write_bytes(previous)
            before = snapshot(drive)
            expected = dict(before)
            with Desktop(rom, syms, drive, output, operation) as ui:
                ui.open_c()
                if operation == "rename-collision":
                    ui.select("SOURCE.TXT")
                    token = ui.arm_dialog("information")
                    ui.key("s")
                    data, tree = ui.dialog(token)
                    ui.click(*ui.center(data, tree, 5))
                    ui.key("0x1")
                    ui.press_text("EXISTING.TXT")
                    edited = ui.field(ui.dump(), tree, 5).replace(" ", "")
                    if edited != "EXISTINGTXT":
                        raise AssertionError(f"rename-collision: editable name is {edited!r}")
                    token = ui.arm_dialog("rename-error")
                    ui.key(28)
                    data, tree = ui.dialog(token)
                    if not any("rename error" in text.casefold() for text in dialog_text(ui, data, tree)):
                        raise AssertionError("rename-collision: expected the Rename error alert")
                    finish_dialog(ui, data, tree, "Cancel")
                else:
                    # Stop at the initial copy dialog to arm the next capture
                    # before the desktop can enter the filename-conflict form.
                    ui.drag("SOURCE.TXT", "TARGET", confirm=False)
                    token = ui.arm_dialog("collision")
                    ui.key(28)
                    data, tree = ui.dialog(token)
                    check_conflict(ui, data, tree)
                    finish_dialog(ui, data, tree, "Copy" if operation == "overwrite" else "Cancel")
                    if operation == "overwrite":
                        destination = drive / "TARGET/SOURCE.TXT"
                        ui.wait(lambda: destination.read_bytes() == payload, "replacement contents and truncation")
                        expected["TARGET/SOURCE.TXT"] = payload
                # Unchanged data alone could pass while a dialog is still open.
                # A fresh selection proves the desktop event loop is responsive.
                ui.select("KEEP.BIN")
                after = snapshot(drive)
                if after != expected:
                    changed = sorted(name for name in after.keys() | expected.keys()
                                     if name not in after or name not in expected or after[name] != expected[name])
                    raise AssertionError(f"{operation}: unexpected filesystem changes: {changed}")
                ui.screenshot("result")
            passed.append(operation)
            print(f"PASS {operation}", flush=True)
    return passed


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
    passed = run(rom, symbols(args.linked_image.resolve()), output, args.operation or OPERATIONS)
    (output / "results.json").write_text(json.dumps({"passed": passed}, indent=2) + "\n")


if __name__ == "__main__":
    main()
