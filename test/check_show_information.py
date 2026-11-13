#!/usr/bin/env python3
"""Exercise file/folder Show Information on a UK TOS 2.06 desktop in Hatari.

Usage: python3 test/check_show_information.py ROM LINKED_IMAGE --output DIR
LINKED_IMAGE is the matching Alcyon tos.img (including its symbol table).
Requires Linux Hatari with control-socket support; no user disk is modified.
"""

import argparse
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def symbols(path):
    text = subprocess.check_output([str(ROOT / "bin/linux/cnm"), str(path)], text=True)
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]+)\s+\S+\s+(\S+)", line)
        if match:
            result[match[2]] = int(match[1], 16)
    return result


def long_at(data, address):
    return struct.unpack_from(">I", data, address)[0]


def text_at(data, address):
    end = data.index(0, address)
    return data[address:end].decode("latin-1")


def dialog_text(data, tree, object_id):
    tedinfo = long_at(data, tree + object_id * 24 + 12)
    return text_at(data, long_at(data, tedinfo))


def scenario(rom, syms, output, folder):
    label = "folder" if folder else "file"
    with tempfile.TemporaryDirectory(prefix="tos-info-") as tmp:
        tmp = Path(tmp)
        drive = tmp / "drive"
        drive.mkdir()
        if folder:
            (drive / "TESTDIR").mkdir()
            (drive / "TESTDIR/CHILD.TXT").write_bytes(b"1234567")
            expected_name, expected_size = "TESTDIR", 7
        else:
            payload = b"Show Information regression\r\n"
            (drive / "CHECK.TXT").write_bytes(payload)
            expected_name, expected_size = "CHECKTXT", len(payload)
        ready = tmp / "ready.bin"
        memory = tmp / "memory.bin"
        capture = tmp / "capture.ini"
        tree_pointer = tmp / "tree.bin"
        capture.write_text(
            f"screenshot {output / (label + '.png')}\n"
            f'savebin {tree_pointer} "a7+4" 4\n'
            f"savebin {memory} 0 4194304\nquit\n"
        )
        boot = tmp / "boot.ini"
        ready_script = tmp / "ready.ini"
        ready_script.write_text(f"savebin {ready} 0 1\nc\n")
        boot.write_text(f"b VBL = 1500 :once :file {ready_script}\nc\n")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        control = tmp / "control.socket"
        server.bind(str(control))
        server.listen(1)
        server.settimeout(15)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", HOME=str(tmp))
        command = [
            "hatari", "--configfile", "/dev/null", "--machine", "megaste",
            "--memsize", "4", "--mono", "--tos", str(rom),
            "--harddrive", str(drive), "--gemdos-drive", "C", "--protect-hd", "on",
            "--sound", "off", "--fast-forward", "yes", "--fast-boot", "yes",
            "--confirm-quit", "no", "--control-socket", str(control), "--parse", str(boot),
        ]
        with (output / (label + ".log")).open("w") as log:
            proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            connection = None
            try:
                connection, _ = server.accept()
                deadline = time.monotonic() + 15
                while not ready.exists():
                    if proc.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(f"{label}: desktop did not boot; see {label}.log")
                    time.sleep(0.02)

                def send(message):
                    connection.sendall((message + "\n").encode("ascii"))
                    time.sleep(0.15)

                # The clean built-in UK desktop uses Alt-C, E (select all), S (info).
                send("hatari-event keydown 56")
                send("hatari-event keypress c")
                send("hatari-event keyup 56")
                send("hatari-event keypress e")
                send(f"hatari-debug b PC = ${syms['_xform_do']:x} :once :file {capture}")
                send("hatari-event keypress s")
                proc.wait(timeout=15)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                if connection:
                    connection.close()
                server.close()
        if not memory.exists():
            raise RuntimeError(f"{label}: information dialog did not open; see {label}.log")
        data = memory.read_bytes()
        tree = long_at(tree_pointer.read_bytes(), 0)
        fields = {key: dialog_text(data, tree, index) for key, index in
                  (("path", 2), ("name", 5), ("size", 6), ("files", 10))}
        if fields["name"].replace(" ", "") != expected_name:
            raise AssertionError(f"{label}: incorrect displayed name: {fields}")
        size = int(fields["size"].replace(",", "").strip())
        if size != expected_size:
            raise AssertionError(f"{label}: incorrect displayed size: {fields}")
        if folder and int(fields["files"].strip()) != 1:
            raise AssertionError(f"folder: incorrect displayed file count: {fields}")
        print(f"{label}: {fields}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("linked_image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    header = args.rom.read_bytes()[:32]
    if struct.unpack_from(">H", header, 2)[0] != 0x206 or struct.unpack_from(">H", header, 28)[0] >> 1 != 3:
        parser.error("this scenario requires UK TOS 2.06 and its built-in default shortcuts")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    syms = symbols(args.linked_image.resolve())
    for folder in (False, True):
        scenario(args.rom.resolve(), syms, output, folder)


if __name__ == "__main__":
    main()
