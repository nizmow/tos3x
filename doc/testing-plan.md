# Prioritized ROM regression tests

## First expansion: six data-loss cases

These six cases are implemented and passed against the reviewed UK TOS 2.06
ROM in Hatari. They prioritize incorrect file contents, lost source data and
unintended changes over cosmetic behavior. They need no external driver,
disk image, network access or physical hardware.

| Case | Consumer-visible invariant | Runner / selection |
|---|---|---|
| Recursive folder copy | Destination has the exact nested tree, empty directory and byte contents; source remains unchanged. | `check_desktop_folders.py --operation folder-copy` |
| Recursive folder move | Destination has the exact tree and contents; original folder is removed. | `check_desktop_folders.py --operation folder-move` |
| Recursive folder delete | Entire selected tree is removed, including nested files and empty folders; unrelated root data remains. | `check_desktop_folders.py --operation folder-delete` |
| Overwrite with truncation | Copying over a longer existing file replaces all bytes and removes the old tail; source is preserved. | `check_desktop_conflicts.py --operation overwrite` |
| Cancel at a filename conflict | Cancel the actual conflict dialog; the entire fixture's names, directory kinds and file contents remain unchanged. | `check_desktop_conflicts.py --operation conflict-cancel` |
| Rename onto an existing file | Desktop reports Rename error; cancel preserves both original names and byte contents, and unrelated files. | `check_desktop_conflicts.py --operation rename-collision` |

Folder cases preserve an unselected sentinel file; conflict cases compare a
snapshot of the entire disposable drive. Both suites finish by selecting an
unrelated file through real input, proving that the desktop is responsive,
not merely that a filesystem predicate happened to be true during a dialog.

## Running the expansion

Requirements are the existing Python/Hatari desktop test setup, a UK TOS 2.06
ROM and its matching linked `tos.img` (for symbols). The harness uses bundled
Linux tools, Hatari's control/debugger interface and headless SDL drivers.
The reviewed ROM is not rebuilt by these tests.

```sh
python3 test/check_desktop_folders.py \
  build/tos206uk-reviewed/tos206uk.img build/tos206uk-reviewed/tos.img \
  --output build/tos206uk-reviewed/folder-proof
python3 test/check_desktop_conflicts.py \
  build/tos206uk-reviewed/tos206uk.img build/tos206uk-reviewed/tos.img \
  --output build/tos206uk-reviewed/conflict-proof
```

Each runner defaults to all three of its cases. `--operation` is repeatable
for narrow diagnosis. Fresh temporary drive/HOME/configuration fixtures keep
user data out of scope. Logs, dialog/result screenshots and `results.json`
are retained under `--output`; temporary fixtures and emulator processes are
cleaned up on exit. Use a separate output directory for concurrent runs of
the same runner.

The six original desktop-operation cases also passed after the harness
changes. The harness now synchronizes window opening and completed mutations
at the desktop's main event-loop boundary, rather than treating an early
host-file change as proof that the directory's clickable object tree has
already been refreshed. Modal captures finish writing their screenshots
before exposing the captured tree pointer to the caller. Only breakpoints
and RAM reads are used: no guest code calls or RAM writes.

## Native guest probes

`check_guest_gemdos.py` builds two PRGs with the bundled Alcyon tools and boots
a generated 720 KiB FAT12 floppy. No Hatari host-directory drive is mounted:
the workload goes through TOS's native GEMDOS filesystem. No disk driver or
downloaded binary fixture is needed. Requirements: the existing Linux x86_64
toolchain, Hatari and mtools (`apt install hatari mtools` if absent).

For physical-machine use, `mise run guest-disk` invokes the shared build-only
frontend `test/build_guest_disk.py`. It needs no ROM, symbols or Hatari.
Default image: `build/guest-disk/native-test.st`; alternate artifact directory:
`mise run guest-disk -- --output build/st-test-disk`. The image includes an
AUTO-starting parent, child, all directory fixtures and `README.TXT`.
Use dedicated writable A: media, boot cleanly, and inspect `RESULT.TXT` after
returning to the desktop; console text may no longer be visible. On an
existing hard-disk boot, manually launching `A:\AUTO\REGRESS.PRG` also works,
but resident software becomes part of the tested configuration.

The emulator runner imports the same builder; no duplicated compile or
fixture-generation path is maintained. The build manifest hashes the pristine
image and programs; booting it creates/updates RESULT.TXT and changes the image.

The guest covers:

- Eight allocation/free/shrink cycles with odd and larger-than-32-KiB blocks,
  deterministic byte patterns, survivor checks and positive-length shrinking.
  The largest free block must recover to its warmed-up value after each cycle.
- One warm-up and sixteen child launches. Each child allocates, checks and
  frees a block, then returns 37. Parent data must survive and the largest
  free block must recover after every launch.
- Three forward/reverse traversals of 128 leaf directories. Each file must
  yield exactly 257 expected bytes, then EOF; file calls and paths are checked.

The minimal assembly startup moves the stack inside its own BSS before
shrinking the initial TPA. It retains through link68 `_end`, including all
linked BSS/commons, not just its own stack. GEMDOS calls use explicit word/long
argument widths. The report is closed during child execution, then reopened
for append.

Run the same workload on stock and custom ROMs, each with its matching
Alcyon linked image:

```sh
python3 test/check_guest_gemdos.py \
  build/tos206uk-reviewed-stock/tos206uk.img build/tos206uk-reviewed-stock/tos.img \
  --output build/native-guest-stock
python3 test/check_guest_gemdos.py \
  build/tos206uk-reviewed/tos206uk.img build/tos206uk-reviewed/tos.img \
  --output build/native-guest-custom
```

Both passed on UK TOS 2.06, Mega STE, 4 MiB RAM, monochrome. The guest PRG
hashes match. Post-run pool captures identify 80 blocks in stock and 180 in
the reviewed custom build, each with one unused block at desktop entry.
These are post-run observations, **not** peak usage or proof of the expanded
pool's capacity boundary.

Artifacts: both PRGs, fixture image `native-test.st`, `guest-result.txt`,
console screenshot, build/emulator/GEMDOS logs, raw pool capture and
`results.json` with input hashes. The report is read from FAT only after
Hatari quits cleanly and flushes the image. A timeout or incomplete/failing
report cannot produce a successful results manifest.

The automated runner targets TOS 2.06 / Mega STE / 4 MiB, with fast-forward
and fast FDC enabled. The mise-built image also passed all three checks on
an emulated ST/68000 with 1 MiB RAM and fast FDC disabled, using the reviewed
UK TOS 2.06 ROM. Its 720 KiB DD BPB geometry was checked. Real hardware,
512 KiB configurations, other TOS versions and other resolutions remain
unverified; this is not a physical floppy-timing certification.
The default disk still omits zero-length Mshrink. It remains untested for
child allocations left unfreed at exit, ALT-RAM, general native filesystem
mutation/failure recovery beyond report writes, and ACSI/hard-disk drivers.

## Optional patch regression checks

Select patches through build arguments or a user-supplied profile. The test
options below verify existing patch implementations; they do not select ROM
patches, modify ROM routines or require a machine-specific build preset.

`check_guest_gemdos.py --check-auto-stack` captures the first AUTO Fsfirst
call frame and basepage using read-only debugger snapshots. Its eight-byte
WORD/LONG/WORD argument frame must end at the 256-byte basepage boundary,
after the preceding twelve-byte Mshrink call has been cleaned up. A build
without `TP_15` fails at offset 242 instead of 248; an enabled build passes.

`--zero-shrink` builds an optional ZERO.PRG child and requires its native
ZERO.TXT report as well as successful child exit. Sixteen iterations alternate
zero-shrinking the allocated-list head and a non-head entry, preserving and
freeing a live sibling allocation and checking recovery of the largest free
block. This catches the dangling allocated-list link left by the unpatched
direct freeit() call. An isolated unpatched control entered that zero-shrink
path, exited 1 and failed to return to desktop; the enabled build passes.

The parent invokes this optional child with its report closed and checks
the return status, independent of AUTO directory ordering. The zero-shrink
probe is deliberately excluded by default: do not run it on stock TOS on
physical hardware. `mise run guest-disk -- --zero-shrink` produces a pristine
disk containing the TP_29 probe. RESULT.TXT and ZERO.TXT must be generated
by the machine being tested, not supplied as pre-filled success files.

`--full-boot` disables Hatari TOS patches, fast boot, fast FDC and Timer-D
patching. Use it with a matching ROM/linked image to test an unpatched cold
boot rather than depending on emulator ROM modifications. This remains
emulator verification, not a certification of physical ACSI/HDDRIVER behavior.

## Next tiers, not yet covered

1. **Pool capacity boundary:** native traversal now exercises real GEMDOS
   state, but needs high-water/reclamation diagnostics and a source-informed
   workload/control to establish the expanded pool's benefit. Directory
   counts and post-run block counts do not prove that.
2. **Native filesystem mutations and failures:** bulk create/write,
   overwrite/rename/delete, fragmentation, disk-full and write-error recovery
   on disposable FAT images. Writing the native result file does not cover
   these operations and their failure paths.
3. **Driver-backed hard-disk path:** generate a partitioned disposable image,
   boot it with an identified, redistributable driver, and repeat basic
   create/read/write/rename/delete plus disk-full recovery. Record the driver
   version/checksum and partition geometry. This is the first tier with a
   meaningful new fixture dependency, and is closer to the original
   ACSI/HDDRIVER symptoms than Hatari's host-directory drive.
4. **Physical/timing coverage:** actual Mega STE disks, alternate drivers,
   peripherals and machine-specific timing require hardware or additional
   reproducible emulator configurations. Keep this separate from the quick
   host-directory checks rather than making them silently depend on it.

None of the new host-directory cases validates ACSI transfers, physical
media integrity, disk-full recovery, all selection combinations, or every
resolution/country/patch configuration. The test expansion changes no ROM
routines; users explicitly select patches through build arguments.
