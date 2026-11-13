#!/usr/bin/env python3
"""Exercise UK TOS 2.06 desktop file operations on disposable Hatari drives.

Usage: python3 test/check_desktop_operations.py ROM LINKED_IMAGE --output DIR
Uses real keyboard/mouse input, not direct calls to desktop functions. Hatari
2.5's limited control API is sufficient: TOS's Alt-arrow/Alt-Insert keyboard
mouse supplies pointer movement and clicks. No user's disk/config is used.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time

from check_show_information import ROOT, long_at, symbols, text_at

OPERATIONS = ("copy", "move", "rename", "delete", "search", "save")

def word(data, address):
    return struct.unpack_from(">h", data, address)[0]


class Desktop:
    def __init__(self, rom, linked_symbols, drive, output, label):
        self.rom = rom.read_bytes()
        self.rom_base = long_at(self.rom, 8)
        self.syms = linked_symbols
        self.output, self.label = output, label
        self.tmp = tempfile.TemporaryDirectory(prefix="tos-desktop-")
        self.path = Path(self.tmp.name)
        self.log = (output / f"{label}.log").open("w")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection = None
        self.proc = None
        self.sequence = 0
        try:
            control = self.path / "control.socket"
            self.server.bind(str(control))
            self.server.listen(1)
            self.server.settimeout(15)
            ready = self.path / "ready.bin"
            script = self.path / "ready.ini"
            script.write_text(f"savebin {ready} 0 1\nc\n")
            boot = self.path / "boot.ini"
            boot.write_text(f"b VBL = 1500 :once :file {script}\nc\n")
            env = os.environ.copy()
            env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", HOME=str(self.path))
            self.proc = subprocess.Popen([
                "hatari", "--configfile", "/dev/null", "--machine", "megaste",
                "--memsize", "4", "--mono", "--tos", str(rom), "--harddrive", str(drive),
                "--gemdos-drive", "C", "--gemdos-case", "upper", "--protect-hd", "off",
                "--sound", "off", "--fast-forward", "yes", "--fast-boot", "yes",
                "--confirm-quit", "no", "--control-socket", str(control), "--parse", str(boot),
            ], env=env, stdout=self.log, stderr=subprocess.STDOUT)
            self.connection, _ = self.server.accept()
            self.wait(lambda: ready.exists(), "desktop boot")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        if self.connection:
            self.connection.close()
        self.server.close()
        self.log.close()
        self.tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def wait(self, condition, description, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = condition()
            if result:
                return result
            if self.proc.poll() is not None:
                raise AssertionError(f"{self.label}: Hatari exited during {description}")
            time.sleep(0.02)
        self.send(f"hatari-debug screenshot {self.output / (self.label + '-failure.png')}")
        time.sleep(0.05)
        raise AssertionError(f"{self.label}: timed out waiting for {description}; see {self.label}.log")

    def send(self, message):
        self.connection.sendall((message + "\n").encode("ascii"))

    def key(self, value, action="keypress"):
        self.send(f"hatari-event {action} {value}")
        # Pace serial keyboard input; completion is checked through UI state below.
        time.sleep(0.012)

    def dump(self, size=4194304):
        self.sequence += 1
        path = self.path / f"memory-{self.sequence}.bin"
        self.send(f"hatari-debug savebin {path} 0 {size}")
        self.wait(lambda: path.exists() and path.stat().st_size == size, "memory snapshot")
        data = path.read_bytes()
        path.unlink()
        return data

    def string(self, data, address):
        if self.rom_base <= address < self.rom_base + len(self.rom):
            return text_at(self.rom, address - self.rom_base)
        return text_at(data, address)

    def press_text(self, text):
        for char in text.lower():
            self.key(52 if char == "." else char)

    def open_c(self):
        self.key(56, "keydown")
        self.key("c")
        self.key(56, "keyup")
        self.wait(lambda: self.windows(self.dump()), "C: directory window")

    def windows(self, data):
        result = []
        pointer = long_at(data, self.syms['_winhead'])
        seen = set()
        while pointer and pointer not in seen:
            seen.add(pointer)
            if word(data, pointer + 4) != -1:
                result.append(pointer)
            pointer = long_at(data, pointer)
        return result

    def entries(self, data):
        windows = self.windows(data)
        if not windows:
            return {}
        win = windows[0]
        directory = long_at(data, win + 106)
        count = word(data, win + 110)
        return {text_at(data, directory + i * 28 + 10): (win, i, word(data, directory + i * 28 + 24))
                for i in range(count)}

    def object_xy(self, data, tree, index):
        parents = {}

        def visit(parent):
            child = word(data, tree + parent * 24 + 2)
            tail = word(data, tree + parent * 24 + 4)
            while child >= 0 and child != parent:
                parents[child] = parent
                visit(child)
                if child == tail:
                    break
                child = word(data, tree + child * 24)

        visit(0)
        x = y = 0
        current = index
        while True:
            obj = tree + current * 24
            x += word(data, obj + 16)
            y += word(data, obj + 18)
            if current == 0:
                break
            current = parents[current]
        obj = tree + index * 24
        return x, y, word(data, obj + 20), word(data, obj + 22)

    def center(self, data, tree, index):
        x, y, width, height = self.object_xy(data, tree, index)
        return x + width // 2, y + height // 2

    def icon(self, name):
        data = self.dump()
        win, index, _ = self.entries(data)[name]
        first = word(data, win + 100)
        tree = long_at(data, win + 96)
        # Click the graphic portion, rather than the blank part of an icon cell.
        x, y, width, height = self.object_xy(data, tree, index - first + 1)
        return x + min(width // 2, 24), y + min(height // 2, 12)

    def move_mouse(self, x, y):
        self.key(56, "keydown")
        for _ in range(8):
            data = self.dump(65536)
            current_x = word(data, self.syms['_xrat'])
            current_y = word(data, self.syms['_yrat'])
            if (current_x, current_y) == (x, y):
                break
            for delta, negative, positive in ((x - current_x, 75, 77), (y - current_y, 72, 80)):
                key = negative if delta < 0 else positive
                for _ in range(abs(delta) // 8):
                    self.key(key)
                self.key(42, "keydown")
                for _ in range(abs(delta) % 8):
                    self.key(key)
                self.key(42, "keyup")
        else:
            raise AssertionError(f"{self.label}: keyboard mouse did not reach {(x, y)}")
        self.key(56, "keyup")

    def click(self, x, y):
        self.move_mouse(x, y)
        self.key(56, "keydown")
        self.key(82, "keydown")
        self.key(82, "keyup")
        self.key(56, "keyup")

    def select(self, name):
        self.click(*self.icon(name))
        self.wait(lambda: self.entries(self.dump()).get(name, (0, 0, 0))[2] & 1, f"selection of {name}")

    def arm_dialog(self, label):
        self.sequence += 1
        capture = self.path / f"dialog-{self.sequence}.ini"
        ram = self.path / f"dialog-{self.sequence}.bin"
        tree = self.path / f"tree-{self.sequence}.bin"
        capture.write_text(
            f'savebin {tree} "a7+4" 4\n'
            f"savebin {ram} 0 4194304\n"
            f"screenshot {self.output / (self.label + '-' + label + '.png')}\nc\n"
        )
        self.send(f"hatari-debug b PC = ${self.syms['_fm_do']:x} :once :file {capture}")
        return ram, tree

    def dialog(self, token):
        ram, tree = token
        self.wait(lambda: ram.exists() and ram.stat().st_size == 4194304 and tree.exists(), "modal dialog")
        return ram.read_bytes(), long_at(tree.read_bytes(), 0)

    def field(self, data, tree, index):
        ted = long_at(data, tree + index * 24 + 12)
        return self.string(data, long_at(data, ted))

    def screenshot(self, name):
        path = self.output / f"{self.label}-{name}.png"
        self.send(f"hatari-debug screenshot {path}")
        self.wait(path.exists, "screenshot")

    def drag(self, source, target, move=False):
        self.select(source)
        source_xy, target_xy = self.icon(source), self.icon(target)
        self.move_mouse(*source_xy)
        self.key(56, "keydown")
        self.key(82, "keydown")
        self.move_mouse(*target_xy)
        # Releasing Alt leaves the keyboard-emulated button held. A physical
        # right-button packet then releases left without leaving Alt (rename)
        # active when the desktop samples the copy/move modifier.
        self.key(56, "keyup")
        if move:
            self.key(29, "keydown")
        token = self.arm_dialog("confirm")
        self.send("hatari-event rightdown")
        data, tree = self.dialog(token)
        self.send("hatari-event rightup")
        self.key(29, "keyup")
        self.key(56, "keydown")
        self.key(82, "keyup")
        self.key(56, "keyup")
        title = self.field(data, tree, 1).upper()
        expected = "MOVE" if move else "COPY"
        if expected not in title or "RENAME" in title:
            raise AssertionError(f"{self.label}: unexpected operation title {title!r}")
        self.key(28)


def run(rom, syms, output, operations):
    results = []
    payload = bytes(range(256)) * 39 + b"odd-boundary!"
    for operation in operations:
        with tempfile.TemporaryDirectory(prefix="tos-files-") as tmp:
            drive = Path(tmp)
            (drive / "SOURCE.TXT").write_bytes(payload)
            if operation in ("copy", "move"):
                (drive / "TARGET").mkdir()
            if operation == "search":
                (drive / "OTHER.BIN").write_bytes(b"not selected")
            configuration = drive / "NEWDESK.INF"
            if operation in ("delete", "save"):
                # These menu commands have no default key. A valid desktop INF
                # assigns D=Delete and T=Text, as the preferences UI permits.
                keys = [0] * 29
                for index, key in ((0, "O"), (1, "S"), (2, "L"), (3, "D"),
                                   (4, "F"), (5, "B"), (6, "C"), (7, "W"),
                                   (8, "E"), (9, "X"), (12, "T"), (27, "V")):
                    keys[index] = ord(key)
                initial = (ROOT / "desk/rsc/206/deskuk.inf").read_bytes().rstrip(b"\0\x1a\r\n")
                initial += b"\r\n#K " + " ".join(f"{key:02X}" for key in keys).encode("ascii") + b" @\r\n"
                configuration.write_bytes(initial)
            with Desktop(rom, syms, drive, output, operation) as ui:
                ui.open_c()
                if operation in ("copy", "move"):
                    ui.drag("SOURCE.TXT", "TARGET", operation == "move")
                    destination = drive / "TARGET/SOURCE.TXT"
                    ui.wait(destination.exists, "destination file")
                    ui.wait(lambda: destination.read_bytes() == payload, "complete copied contents")
                    if (drive / "SOURCE.TXT").exists() != (operation == "copy"):
                        raise AssertionError(f"{operation}: incorrect source-file disposition")
                elif operation == "rename":
                    ui.key("e")
                    token = ui.arm_dialog("information")
                    ui.key("s")
                    data, tree = ui.dialog(token)
                    ui.click(*ui.center(data, tree, 5))
                    ui.key("0x1")  # A one-digit event would type '1', not Escape.
                    ui.press_text("RENAMED.TXT")
                    ui.screenshot("edited")
                    edited = ui.field(ui.dump(), tree, 5)
                    if edited.replace(" ", "") != "RENAMEDTXT":
                        raise AssertionError(f"rename: editable field contains {edited!r}")
                    ui.key(28)
                    try:
                        ui.wait(lambda: (drive / "RENAMED.TXT").exists(), "renamed file")
                    except AssertionError as error:
                        raise AssertionError(f"{error}; drive contains {[p.name for p in drive.iterdir()]}") from error
                    if (drive / "SOURCE.TXT").exists() or (drive / "RENAMED.TXT").read_bytes() != payload:
                        raise AssertionError("rename: name/content mismatch")
                elif operation == "delete":
                    ui.select("SOURCE.TXT")
                    token = ui.arm_dialog("confirm")
                    ui.key("d")
                    ui.dialog(token)
                    ui.key(28)
                    ui.wait(lambda: not (drive / "SOURCE.TXT").exists(), "deleted file")
                elif operation == "search":
                    token = ui.arm_dialog("query")
                    ui.key("l")
                    ui.dialog(token)
                    ui.press_text("SOURCE.TXT")
                    ui.key(28)
                    ui.wait(lambda: ui.entries(ui.dump()).get("SOURCE.TXT", (0, 0, 0))[2] & 1, "search result selection")
                    entries = ui.entries(ui.dump())
                    if entries["OTHER.BIN"][2] & 1:
                        raise AssertionError("search selected a non-matching file")
                else:
                    ui.key("t")
                    ui.wait(lambda: word(ui.dump(), syms['_s_view']) == 1, "text view")
                    token = ui.arm_dialog("confirm")
                    ui.key("v")
                    ui.dialog(token)
                    ui.key(28)
                    ui.wait(lambda: configuration.read_bytes() != initial, "updated desktop configuration")
                ui.screenshot("result")
            if operation == "save":
                with Desktop(rom, syms, drive, output, "reload") as ui:
                    ui.wait(lambda: word(ui.dump(), syms['_s_view']) == 1, "persisted text view after reboot")
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
