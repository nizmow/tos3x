# What is this?

These are the sources used to build orginal ROM versions of TOS 2.06/3.06,
the OS used by Atari STE and TT.

The goal of this project was to actually be able to
regenerate the original ROM images. 
The sources are not meant to be a base for serious further development, the Alcyon
compiler tools that were originally used are just too outdated and buggy.
They could be used to implement smaller patches/fixes.

It is therefor mainly intended to be used as reference.



# Directory Structure

- bin/tos:  
  Prebuild binaries of tools used in the build process. These are
  essentially identical to the ones from the developer kit, with 
  modifications as described in [alcyon/README](). Sources of almost
  all of these tools are found in the alcyon directory.

  It also contains a few tools that are not part of the developer-kit,
  but are now used in the build process (sed, rm, mv and bc). Those
  are taken from GNU packages.

- bin/linux:  
  Same tools as above, but compiled for linux-64bit. The cc68 executable
  in this directory is just a shell script that recognizes a few of
  the usual unix cc switches, and translates them to call the various
  alcyon executables.

- bin/win32:  
  Same tools as above, but compiled for windows-32bit.

- include:  
  Include files for the C compiler. Only a few of them are actually
  needed for TOS itself, most of them are only needed to build the
  tools.

- lib:  
  Prebuild libraries and startup files for the C runtime library.
  None of these is linked into a ROM image, they are only used for the tools.

- doc:  
  Some unsorted documentation.

- bios:  
  Source of the BIOS part of TOS.

- vdi:  
  Source of the VDI part of TOS.

- bdos:  
  Source of the GEMDOS part of TOS.

- aes:  
  Source of the AES part of TOS.

- desk:  
  Source of the desktop application.

- common:  
  Shared include files for the above components.

- tools:  
  Source of some small tools used in the build process,
  namely the one that glues the builtin resources and
  newdesk/desktop.inf files together. If you are cross-compiling,
  these must be compiled by your native host compiler.

- system:  
  Source of some small Atari tools.

- listings:  
  Disassembler listings of various TOS versions that were used while
  working on some parts of the system.

- glue:  
  The final ROM images will be build here. It also contains link maps
  for some ROM versions, for reference. The identifiers in those maps
  are truncated to 8 characters, though (a limitation of the DRI
  object file format).

- alcyon:  
  Source of the (modified) tools of the Alcyon C compiler & tools,
  as used to compile TOS.

- alcyon/orig:  
  Source of the tools of the Alcyon C compiler & tools, that compile to binary
  identical versions of the ones found in the developer kit.

(the contents of the alcyon directory are now available as a separate archive)


# Assembler sources

- Assembler sources are written in a format that is accepted
  both by as68 and by the GNU assembler with the --mri option.
  If you have to use a different assembler, they might need
  conversion.

- All comments in assembly files are in C-style. The makefile
  preprocesses them before passing them to the assembler. This
  avoids problems with different types of comment delimiters in
  different assemblers, and also works around some bugs of
  the conditional assembly directives of as68. It also allows
  using the same files defining some key constants to be
  used for both assembler and C.

- Don't put comments after constants that are used in assembler
  expressions. Since it is a K&R preprocessor, the spaces between
  the constant and the comment will make it to the source, and
  the assembler does not like spaces in operands.

- Assembling the assembler sources in the bios directory with
  the original as68 from the developer kit will not work, mostly
  because it does not support abs.w addressing mode, but also due
  to numerous bugs. Either use the fixed version from the bin
  directory or try some other assembler.


# Supported versions

BIOS, VDI, GEMDOS, AES, DESKTOP: 2.06, 2.08, 3.06
2.08 is 2.06 modified for ST-Book, it identifies itself as 2.06 though


# Supported language versions

- us - USA
- de - Germany
- fr - France
- uk - United Kingdom (uses US resources)
- es - Spain (no ROM yet found to verify)
- it - Italy (no ROM yet found to verify)
- se - Sweden
- fi - Finland (uses swedish keyboard and resources)
- no - Norway (uses swedish keyboard and resources)
- sf - Switzerland (French) (uses french keyboard and resources)
- sg - Switzerland (German) (uses german keyboard and resources)

- pl - Poland (only unofficial version 3.06 found on the net)
- cz - Czech (originally was a patched german version)


## Linux / WSL x86_64 quickstart

The `tools/build_rom.py` wrapper provides isolated builds on Linux x86_64 and
WSL. The legacy raw `make` workflow below remains available on other hosts.
Install [mise](https://mise.jdx.dev/), then from the repository root run:

```sh
mise trust
mise install
mise run doctor
```

`mise trust` approves this repository's mise configuration; `mise install`
installs its pinned Python 3.13. Native build prerequisites (Git, GCC/make,
`bc`, and `dc`) are OS packages rather than mise tools. Install them explicitly
on Debian/Ubuntu with `mise run deps` (which uses apt and sudo), or with your
distribution's package manager. Hatari is optional; on Debian/Ubuntu it can be
installed separately with `sudo apt-get install hatari`.

Build stock UK TOS 2.06:

```sh
mise run build -- --tos 206 --country uk
```

Build with an explicit patch combination:

```sh
mise run build -- --tos 206 --country uk --define TP_47=1 \
  --define SHBUFSIZE=16384 --define FOLDER_POOL_BLOCKS=180
```

To use a profile, create a TOML file, for example:

```toml
tos = 206
country = "uk"
exact = false

[defines]
TP_47 = 1
SHBUFSIZE = 16384
FOLDER_POOL_BLOCKS = 180
```

Then build with `mise run build -- --profile path/to/profile.toml`. The
profile's `[defines]` table maps directly to existing C macros. Without
custom definitions, builds default to `exact=true`; custom definitions default
to `exact=false`. Wrapper builds turn all optional numeric `TP_*` patches off
unless explicitly enabled, unlike raw `make`, which uses the defaults in
`common/patchdef.h`.

The next minimal UK TOS 2.06 Mega STE candidate keeps the 180-block pool and
16 KiB NEWDESK buffer, adding only `TP_15` (AUTO stack cleanup) and `TP_29`
(zero-length Mshrink):

```sh
mise run build -- --profile profiles/megaste-minimal-fixes.toml \
  --output tos206uk-megaste-minimal-fixes
```

The full flash payload is `tos206uk.img` (256 KiB); the `-hi.bin` and
`-lo.bin` files are 128 KiB upper/even-address and lower/odd-address byte
lanes. Match the board/programmer's mapping; do not flash the linked
`tos.img` debugger container. Keep a stock-ROM recovery option.

The wrapper supports TOS 2.06, 2.08, and 3.06 where matching resources exist.
For example, use `--tos 306 --country de` for the TT, or
`--tos 208 --country us` for the ST-Book. ST-Book resources are supplied only
for `us`, `de`, and `fr`; unsupported combinations fail before compilation.

Each build uses a clean snapshot of tracked working-tree files, so untracked
source files are not included: `git add` a new source file before building.
Existing ignored `common/localcnf.h` is not used by wrapper builds. Artifacts
are placed under `build/<name>/`: the country/version full ROM image (for
example `tos206uk.img`), the linked `tos.img` image, high/low byte lanes,
generated `localcnf.h`, `build.log`, and `manifest.json`. The wrapper also
checks the linked OS memory boundary. To run a ROM, pass its path to the
Hatari task: `mise run run -- build/tos206uk-stock/tos206uk.img`. The default
machine is Mega STE; use `--machine tt` for a TOS 3.06 image.

The wrapper's apt task is opt-in; builds do not install system dependencies
automatically.

An optional Hatari desktop regression check exercises file and folder
Show Information on a UK TOS 2.06 build:

```sh
python3 test/check_show_information.py \
  build/tos206uk-custom/tos206uk.img build/tos206uk-custom/tos.img \
  --output build/show-information-check
```

It uses a disposable host-directory drive, verifies the displayed names,
sizes and folder file count, and saves screenshots and emulator logs.

The broader disposable-drive desktop check covers copy, move, rename,
delete, search, and saving/reloading the desktop configuration:

```sh
python3 test/check_desktop_operations.py \
  build/tos206uk-custom/tos206uk.img build/tos206uk-custom/tos.img \
  --output build/desktop-operation-check
python3 test/check_bios_preprocess.py
```

Additional data-loss regressions cover recursive folder copy/move/delete,
overwrite with truncation, conflict cancellation, and rename collisions:

```sh
python3 test/check_desktop_folders.py \
  build/tos206uk-custom/tos206uk.img build/tos206uk-custom/tos.img \
  --output build/folder-operation-check
python3 test/check_desktop_conflicts.py \
  build/tos206uk-custom/tos206uk.img build/tos206uk-custom/tos.img \
  --output build/file-conflict-check
```

These use the same disposable-drive setup. See the
[prioritized test plan](doc/testing-plan.md) for assertions, the native guest
checks, and remaining pool-pressure and disk-driver coverage.

A native GEMDOS guest check builds small PRGs and boots a generated FAT12
floppy, without a host-directory drive or external disk driver. It checks
memory allocation/shrink/recovery, repeated child execution, and native
directory/file reads. Requires Hatari and mtools:

```sh
python3 test/check_guest_gemdos.py \
  build/tos206uk-custom/tos206uk.img build/tos206uk-custom/tos.img \
  --output build/native-guest-check
```

Run it separately on stock and custom ROMs with their matching linked images.
The [test plan](doc/testing-plan.md#native-guest-probes) describes assertions,
artifacts and limits; directory traversal alone does not prove pool capacity.

To build only a self-contained disk for a real ST, without a ROM, symbols or
Hatari:

```sh
mise run guest-disk
```

This produces `build/guest-disk/native-test.st`, a 720 KiB DD FAT12 image,
plus the PRGs, build log and manifest. Override the destination with
`mise run guest-disk -- --output build/st-test-disk`. Requires mtools.
Mount the image as writable A: on a Gotek/FlashFloppy, or use an appropriate
disk-imaging tool to write a dedicated DD floppy; copying the `.st` file
onto a floppy as an ordinary file is not sufficient.

Boot cleanly from A: with hard-disk boot disabled, or launch
`A:\AUTO\REGRESS.PRG` manually. Keep the supplied child and fixtures in place.
The console may clear on return to the desktop: inspect `A:\RESULT.TXT`.
Success requires all three PASS lines and DONE. The image includes
`README.TXT`; it contains no ROM and does not install anything.

For the minimal-fixes candidate, targeted validation is:

```sh
python3 test/check_guest_gemdos.py \
  build/tos206uk-megaste-minimal-fixes/tos206uk.img \
  build/tos206uk-megaste-minimal-fixes/tos.img \
  --zero-shrink --check-auto-stack --full-boot \
  --output build/tos206uk-megaste-minimal-fixes/native-proof
```

`--full-boot` disables Hatari TOS patches, fast boot and fast FDC. The
optional zero-shrink child checks list integrity, live data and memory
recovery; AUTO validation checks the captured GEMDOS call frame. To build
its physical test disk, use `mise run guest-disk -- --zero-shrink --output
build/minimal-fixes-disk` and also require `ZERO.TXT` to contain
`PASS zero-shrink` and `DONE`.
**Do not run this optional zero-shrink variant on stock TOS on real hardware:**
the known bug can corrupt memory lists. The default disk omits that probe.

See [the non-exact build review](doc/binexact-review.md) for classifications,
the conditional inventory, observed results, and verification limits.


# How to compile

First off to clarify: the goal of this project was to actually be able to
regenerate the original ROM images. Most parts of the sources used herein were
already available before, but scattered around in several archives, and most
of the time incomplete so they could be used for illustratve purposes at best.
They are not meant to be a base for serious further development, the Alcyon
compiler tools that were originally used are just too outdated and buggy.

Having that said, if you still feeling adventurous and want to try to compile
it yourself:

- unpack the archive in some directory of your choice. All pathnames used
  in the makefiles are relative, so its name does not matter. Sources,
  object files and any built files will need ~13MB of disk space.

- install some shell. In my case i used GEMINI (unfortunately german only).
  bash might work, but some of the tools will have problems with MiNT which
  bash requires. Using command.tos from the bin directory should also work.

- cd to the toplevel directory

- make sure the bin directory from the archive is on your PATH:
  PATH=$PWD\bin,$PATH
  (for gemini/mupfel; other shells might use ';' as path separator)

- type "make"
  This should build the default configuration (german TOS 3.06).
  If the build succeeds, the final image will be found in the "glue" directory.

- for building other configurations, you can say e.g.
  make TOSVERSION=206 COUNTRY=us
  Alternatively, you can edit config.mak in the toplevel directory.
  See there also for a list of valid configurations.
  Also, when switching configurations, always make sure to run
  make clean
  first.
  If you pass the configuration via commandline, be sure to always
  use the same command when having to restart make.

- For patched Alcyon builds, use `BINEXACT=0` and put overrides in
  `common/localcnf.h`. Startup reserves and clears through link68's `_end`,
  including module-local BSS and common storage beyond `common/vars.S`.
  Check the linked OS memory boundary with:
  `python3 test/check_os_memory.py glue/tos.img`.

- There might currently be some issues with \ vs / in pathnames. If
  that is the case, try to run it using some emulator. Hatari
  (https://www.hatari-emu.org/) is reported to work.

- There might be some more hints available on
  http://www.atari-forum.com/viewforum.php?f=16

- Be patient. On a STE, recompiling everything from scratch is reported
  to take ~2h, on a TT ~34 min. A Ramdisk might help, but note that the
  makefiles currently don't support to only put temporary files there.
  Without modifiying the makefiles you would need to put the sources there
  too, risking to loose any modifications you made if something goes awfully
  wrong.

# Hades ROMs

Hades ROMs can now also be built, by using

  make TOSVERSION=306 COUNTRY=uk HADES=1

Only the UK version has been checked against original images,
but it is expected that other versions work, too (except that the about
dialog is not patched).
Above example will build a hadesuk.img image in the glue directory.
