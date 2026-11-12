#!/usr/bin/env python3
"""Build reproducible TOS ROM snapshots without touching the working tree."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHDEF = ROOT / "common/patchdef.h"
VERSIONS = ("206", "208", "306")
COUNTRIES = ("us", "de", "fr", "uk", "es", "it", "se", "sf", "sg", "cz", "nl")


def patch_info():
    text = PATCHDEF.read_text()
    names = set(re.findall(r"^#ifndef\s+([A-Za-z_]\w*)", text, re.M))
    names.update(re.findall(r"^#undef\s+(TP_\w+)", (ROOT / "common/nopatch.h").read_text(), re.M))
    names.add("FOLDER_POOL_BLOCKS")
    descriptions = {}
    for line in text.splitlines():
        m = re.match(r"\s*\*?\s*(TP_[^:]+):\s*([^:]+):\s*(.*?)\s*$", line)
        if m:
            descriptions[m.group(1)] = f"{m.group(2)}: {m.group(3)}"
        else:
            m = re.match(r"\s*\*?\s*(TP_[^:]+):\s*(.*?)\s*$", line)
            if m:
                descriptions[m.group(1)] = m.group(2)
    return names, descriptions


def profile(path):
    import tomllib
    with open(path, "rb") as f:
        data = tomllib.load(f)
    allowed = {"tos", "country", "exact", "defines"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown profile key(s): {', '.join(sorted(unknown))}")
    defines = data.pop("defines", {})
    if not isinstance(defines, dict):
        raise ValueError("profile [defines] must be a TOML table")
    if "exact" in data and not isinstance(data["exact"], bool):
        raise ValueError("profile exact must be true or false")
    for key in ("tos", "country"):
        if key in data and not isinstance(data[key], (str, int)):
            raise ValueError(f"profile {key} must be a string or integer")
    data["defines"] = {str(k): macro_value(v) for k, v in defines.items()}
    return data


def macro_value(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    raise ValueError(f"invalid macro value: {value!r}")


def define_argument(text):
    name, separator, value = text.partition("=")
    if not separator or not value:
        raise argparse.ArgumentTypeError("expected NAME=VALUE")
    return name, value


def doctor():
    missing = []
    if sys.platform != "linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        missing.append("host must be Linux x86_64")
    if sys.version_info < (3, 11):
        missing.append("Python 3.11 or newer is required")
    for command in ("git", "make", "gcc", "bc", "dc"):
        if shutil.which(command) is None:
            missing.append(f"missing command: {command}")
    tools = ROOT / "bin/linux"
    for name in ("analyze", "ar68", "as68", "c068", "c168", "cc68", "cmprom", "cnm", "cp68", "link68", "lo68", "nm68", "optimize", "relmod", "size68", "stripex"):
        p = tools / name
        if not p.is_file() or not os.access(p, os.X_OK):
            missing.append(f"missing executable bundled tool: {p.relative_to(ROOT)}")
    if missing:
        print("Build prerequisites are not ready:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        print("Install host packages (for example: apt install build-essential bc git dc).", file=sys.stderr)
        return 1
    print("Build prerequisites are ready (Linux x86_64, Python", sys.version.split()[0], ").")
    return 0


def snapshot(dest):
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        rel = Path(os.fsdecode(raw))
        if rel.name in ("localcnf.h", "localcnf.mak"):
            continue
        src, dst = ROOT / rel, dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            target = os.readlink(src)
            try:
                dst.symlink_to(target, target_is_directory=src.is_dir())
            except FileExistsError:
                pass
        elif src.is_file():
            shutil.copy2(src, dst)


def build(args):
    if doctor():
        raise RuntimeError("build prerequisites are missing; see doctor output")
    cfg = {"tos": None, "country": None, "exact": None, "defines": {}}
    if args.profile:
        cfg.update(profile(args.profile))
    if args.tos_cli is not None: cfg["tos"] = args.tos_cli
    if args.country_cli is not None: cfg["country"] = args.country_cli
    cfg["tos"] = str(cfg["tos"] or "206")
    cfg["country"] = str(cfg["country"] or "uk")
    if cfg["tos"] not in VERSIONS:
        raise ValueError("tos must be one of 206, 208, 306")
    if cfg["country"] not in COUNTRIES:
        raise ValueError(f"country must be one of {', '.join(COUNTRIES)}")
    resources = (
        f"aes/rsc/{cfg['tos']}/gem{cfg['country']}.rsc",
        f"desk/rsc/{cfg['tos']}/desk{cfg['country']}.rsc",
        f"desk/rsc/{cfg['tos']}/desk{cfg['country']}.inf",
    )
    missing = [path for path in resources if not (ROOT / path).is_file()]
    if missing:
        raise ValueError(
            f"missing resources for TOS {cfg['tos']} / {cfg['country']}: "
            + ", ".join(missing)
            + "; choose a country supplied under aes/rsc and desk/rsc for this version"
        )
    definitions = dict(cfg["defines"])
    definitions.update(dict(args.define))
    cfg["defines"] = definitions
    names, _ = patch_info()
    allowed = names
    for key, value in definitions.items():
        if not re.fullmatch(r"[A-Za-z_]\w*", key) or key not in allowed:
            raise ValueError(f"unknown or invalid define {key!r}; see `build_rom.py patches` for supported names")
        if "\n" in str(value) or "\r" in str(value):
            raise ValueError(f"newline is not allowed in define {key}")
    exact = cfg["exact"] if cfg["exact"] is not None else not bool(definitions)
    if exact and definitions:
        raise ValueError("exact=true conflicts with --define; set exact=false in the profile")
    numeric = sorted(set(re.findall(r"^#ifndef\s+(TP_[A-Za-z0-9_]+)", PATCHDEF.read_text(), re.M)) - {"TP_36"})
    selected = {} if exact else dict.fromkeys(numeric, "0")
    selected.update(definitions)
    output = args.output or (f"tos{cfg['tos']}{cfg['country']}-stock" if exact else f"tos{cfg['tos']}{cfg['country']}-custom")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", output) or output in (".", ".."):
        raise ValueError("--output must be a simple basename (letters, digits, dot, underscore, hyphen)")
    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    final = build_root / output
    if final.is_symlink() or (final.exists() and not final.is_dir()):
        raise ValueError(f"output path exists and is not a directory: {final}")
    with tempfile.TemporaryDirectory(prefix="tos-rom-", dir=build_root) as td:
        src = Path(td) / "src"
        src.mkdir()
        snapshot(src)
        lines = [f"#define {k} {v}" for k, v in sorted(selected.items())]
        (src / "common/localcnf.h").write_text("\n".join(lines) + ("\n" if lines else ""))
        command = ["make", f"TOSVERSION={cfg['tos']}", f"COUNTRY={cfg['country']}", f"BINEXACT={1 if exact else 0}"]
        env = os.environ.copy()
        for key in ("MAKEFLAGS", "MAKEOVERRIDES", "MAKEFILES"):
            env.pop(key, None)
        env["PATH"] = str(src / "bin/linux") + os.pathsep + env.get("PATH", "")
        proc = subprocess.run(command, cwd=src, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = proc.stdout
        if proc.returncode:
            if final.exists():
                (final / "build.log").write_text(log)
                (final / "FAILED").write_text("Build failed; all previous artifacts here are stale.\n")
            else:
                print(log, file=sys.stderr)
            raise RuntimeError(f"make failed ({proc.returncode}); log: {final / 'build.log' if final.exists() else 'shown above'}")
        linked = src / "glue/tos.img"
        checker = subprocess.run([sys.executable, str(src / "test/check_os_memory.py"), str(linked)], cwd=src, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if checker.returncode:
            raise RuntimeError("OS memory boundary check failed:\n" + checker.stdout)
        tosfile = src / f"glue/tos{cfg['tos']}{cfg['country']}.img"
        if not tosfile.is_file():
            raise RuntimeError(f"make succeeded but ROM payload is missing: {tosfile.relative_to(src)}")
        rom = tosfile.read_bytes()
        if len(rom) % 2:
            raise RuntimeError("ROM payload has odd byte length; cannot create byte lanes")
        image = linked
        tempout = Path(tempfile.mkdtemp(prefix=f".{output}-", dir=build_root))
        shutil.copy2(tosfile, tempout / f"tos{cfg['tos']}{cfg['country']}.img")
        shutil.copy2(image, tempout / "tos.img")
        (tempout / f"tos{cfg['tos']}{cfg['country']}-hi.bin").write_bytes(rom[::2])
        (tempout / f"tos{cfg['tos']}{cfg['country']}-lo.bin").write_bytes(rom[1::2])
        shutil.copy2(src / "common/localcnf.h", tempout / "localcnf.h")
        (tempout / "build.log").write_text(log + "\n" + checker.stdout)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
        manifest = {"tos": cfg["tos"], "country": cfg["country"], "exact": exact, "defines": definitions, "command": command, "source_revision": revision, "rom_sha256": hashlib.sha256(rom).hexdigest()}
        (tempout / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        final.mkdir(exist_ok=True)
        for artifact in sorted(tempout.iterdir(), key=lambda path: path.name == "manifest.json"):
            os.replace(artifact, final / artifact.name)
        tempout.rmdir()
        (final / "FAILED").unlink(missing_ok=True)
    print(f"Built verified ROM artifacts in {final}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="subcommand", required=True)
    subs.add_parser("doctor", help="check native build prerequisites")
    subs.add_parser("patches", help="list supported patch/configuration macros")
    p = subs.add_parser("build", help="build ROM in an isolated tracked-file snapshot")
    p.add_argument("--tos", dest="tos_cli", choices=VERSIONS)
    p.add_argument("--country", dest="country_cli", choices=COUNTRIES)
    p.add_argument("--define", action="append", default=[], type=define_argument)
    p.add_argument("--profile")
    p.add_argument("--output")
    args = parser.parse_args()
    try:
        if args.subcommand == "doctor": return doctor()
        if args.subcommand == "patches":
            names, descriptions = patch_info()
            for n in sorted(names): print(f"{n}\t{descriptions.get(n, '')}")
            return 0
        build(args)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, RuntimeError, KeyError) as e:
        parser.error(str(e))

if __name__ == "__main__":
    sys.exit(main())
