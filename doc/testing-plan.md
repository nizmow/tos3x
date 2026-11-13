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

## Next tiers, not included in this expansion

1. **Allocation and process lifecycle:** a small guest PRG can exercise
   allocate/free/shrink, load/exit and repeat cycles. The assertions should
   check preservation of live data, return values and eventual memory reuse,
   not incidental allocation addresses. This needs a reproducible guest
   executable fixture but no external disk driver.
2. **Directory/pool and path stress:** exercise large entry counts, nested
   traversal, recursive search and repeated operations that consume/release
   directory state. Choose counts from a demonstrated limit or documented
   patch contract, not an arbitrary large number. The expanded folder pool
   is not proven merely by copying a small nested tree.
3. **Real GEMDOS disk path:** generate a partitioned disposable disk image,
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
resolution/country/patch configuration. No original TOS behavior was changed
or optional ROM patch enabled by this test-only expansion.
