# Non-exact ROM build review

## Scope and conclusion

Reviewed the direct `BINEXACT` conditionals in the ROM component sources
(`bios`, `vdi`, `bdos`, `aes`, `desk`), shared headers/layout (`common`), and
ROM glue. The inventory below contains **361 conditional sites in 89 files**.
The build configuration generator in `config.mak` was also checked against
these consumers. This is a source review, not a proof of semantic equivalence.

The runtime target is the Alcyon-built UK TOS 2.06 ROM on a Hatari Mega STE,
4 MiB RAM, with `TP_47=1`, `SHBUFSIZE=16384`, `FOLDER_POOL_BLOCKS=180`, and
other optional numeric TP patches disabled. Legacy versions, alternate
boards/CPUs and inactive conditional branches were classified from source,
not exhaustively executed. The separate unused `pixvdi` tree, disassembly
listings and compiler implementation are not additional ROM component builds.

No further custom-only runtime defect was demonstrated beyond the previously
fixed OS-BSS boundary and Show Information pointer clobber. One compiler
frontend defect was demonstrated and fixed: an extra `)` in
`bios/nvram.S`'s RTC conditional is rejected by GNU preprocessing. Removing it
leaves both the reviewed custom ROM and stock UK ROM byte-identical to their
working baselines. No speculative safety initializers or unrelated original
TOS fixes were added.

`BINEXACT=0` does more than enable selected patches: it also selects existing
TOS fixes, different compiler/ABI accommodations, and some backported behavior.
The explicit-patch frontend controls optional TP macros; it does not suppress
those existing non-exact branches. This distinction remains important.

## Classification

- **Binary layout/encoding:** padding, register-allocation accommodations and
  instruction spellings needed to reproduce original bytes; not necessarily
  changes to intended behavior.
- **Compiler/ABI accommodation:** split word/long trap arguments, register
  saves, return types, linkage and explicit returns. Alcyon still uses the
  old 16-bit-int ABI in a non-exact build; GNU is a separate compiler path.
- **Inherited TOS fix:** deliberate correction of an original defect retained
  by exact mode. These are not evidence that custom mode is broken.
- **Feature/version gate:** behavior intentionally made available in another
  version or build mode, such as desktop patterns or country mappings.
- **Warning-only initialization:** reviewed for a live value overwritten after
  a branch, reads before assignment and incorrect control-flow placement.
- **Reconstruction defect:** the previous BSS and directory-pointer failures;
  frontend syntax acceptance also belongs to build/reconstruction correctness.

## Shared layout, BIOS and GEMDOS

| Sources / branches | Classification and disposition |
|---|---|
| `common/vars.S`, startup BSS clear and GEM MUPB | Fixed template is not the true end of non-exact module BSS/commons. Previously corrected to link68 `_end` for Alcyon custom builds, including alternate clearing paths. Preserve the distinct VDI end marker. `check_os_memory.py` enforces that the TPA cannot start inside linked BSS. |
| `common/asmdefs.h` / `RESERVE_SPACE` | Exact instruction padding; ABSW/CPU selection remains version-dependent. Reviewed CPU/frame assumptions alongside BIOS trap dispatch. |
| `common/nopatch.h`, `bios.h`, `biosdefs.h`, `config.mak` | Exact mode resets optional patches; GNU is forced non-exact; frontend configuration is generated before compilation. Shared pool size is used by both C and assembly reservations. |
| `common/sections.inc` PL exact RAM selection | Historical image/version behavior, inactive for UK 2.06. No change. |
| `bios/blkdev.c` | Exact `flopini` argument-packing workaround; custom typed call has correct pointer/word widths. Custom floppy BPB handling honors reserved/FAT-count fields. Hades instruction patches are inactive for Mega STE. Sector checksums are arithmetically equivalent. Existing geometry divide-by-zero risk on malformed media is not a new custom-only defect. |
| `bios/chardev.S` | Version-dependent zero-displacement encodings and fully specified immediate registers; custom printer route tests the correct byte/bit. Register clearing and missing-register initialization are inherited fixes. Ordinary 2.06 serial loops mostly select the same branch in either mode. External printer/serial devices were not runtime-tested. |
| `bios/dma.inc` | Custom clears the full floppy-lock word rather than only its high byte; a correction to lock release, not a new failure. No ACSI hardware test is claimed. |
| `bios/floppy.S`, `sounds.c`, `scrdmp.inc` | Most branches already select the same code in 2.06; older-version immediates/palette addresses are encoding or inherited-fix choices. |
| `bios/ikbdclk.S` | Existing year-encoding/Y2K behavior change. Not altered by this review; physical IKBD clock interoperability was not tested. |
| `bios/nvram.S` | Custom RTC detection preserves the probed alarm register and restores the saved stack/vector on failed detection; earlier-version bank/weekday choices are fixes. **Removed one unmatched parenthesis** after a failing GNU preprocessing run. Native frontend regression checks cover 2.06 and 3.06; this does not prove a complete GNU-built ROM or RTC hardware operation. |
| `bios/startup.S` | Non-exact ST video register-existence checks, inactive-drive AUTO exit correction and runtime exception-frame checks are inherited fixes/compatibility changes. Hades FPU opcode correction and Medusa/padding branches are not active on the selected machine. |
| `bios/hadxbios.S`, `m64_pci.S`, `medusamm.S`, `fpsp060/skel060.S` | Alternate-board padding, country-ID and FPU/cache opcode corrections; source-reviewed, not hardware-tested. |
| `bios/keytbl.c`, `keytbl.h` | Extra countries/multilingual mappings are feature gates, not warning-only initialization. |
| `bdos/fsfat.c`, `bdos/xfer.S` | The exact tail-copy call's extra trailing word is unused by the assembly callee; the three live argument offsets agree. Byte-copy loops enter through DBF and copy the requested count, not count+1. |
| `bdos/fsopnclo.c`, `ldiv.S`, `osinit.S` | Hades relocation quirk, stack-adjust instruction spellings, longjmp literal and time-call routing are exact/ABI/version accommodations. No incorrect custom stack offset was demonstrated. |
| `bdos/osmem.c`, `umem.c` | Explicit NULL return and typed Bconout are compiler/ABI corrections. Positive-length shrink rounding is equivalent for valid lengths. The separate zero-length shrink fix remains optional `TP_29`; it was not silently enabled. |
| `glue/cartridg.S` | Local BINEXACT definition selects assembly macros for the ST-Book cartridge. No Mega STE runtime path. |

## AES

| Location / symbol | Classification; 2.06 | Observed risk / disposition |
|---|---|---|
| `aes.h:56-60,102-107` | Binary-layout/compiler workaround; all | Exact mode available only Alcyon; STATIC becomes externally visible for linker layout. Variant mechanism, not a custom-only bug. |
| `aes.h:287,895`; `geminit.c:172-174,766-769`; `gemshlib.c:690-692` | Feature gate / ABI symbol availability; 2.06 | Desktop color `adeskp` introduced for >=3.30 or custom variant. 2.06 custom gets symbol/storage and desktop color initialization/use; intentional backport behavior. |
| `aes.h:598-602`; `gemmnlib.c:45-48`; `gemctrl.c:65-67` | Binary-layout/width workaround; 2.06 | `gl_mnpid` is long in exact, short in custom; comments call out historical allocated-long/accessed-short issue. Do not alter ABI/layout. |
| `aes.h:637-640`; `gemobed.c:69-72`; `gemoblib.c:87-90,507-510` | Storage lifetime / binary layout; all incl. 2.06 | Exact mode external/static-duration resource scratch objects vs custom function-local scratch objects (the latter avoid shared/re-entrant lifetime and symbol layout constraints). No demonstrated clobber found. |
| `gemoblib.c:1440-1449` `ob_dxywh` | ABI/argument-width workaround; **not active in 2.06** (AES3D off) | Exact branch calls 8-parameter `ob_gclip` with only 5 args; comments document stack/pointer corruption. Custom branch passes all 8. Existing exact-only historical defect; custom path is already corrected, so no change. |
| `gemaplib.c:165-168,248-258,292-296`; `gemctrl.c:880-893`; `gemdisp.c:198-215`; `geminput.c:596-625`; `gemfmlib.c:293-296,374-377`; `gemmnlib.c:446-449` | Variadic/stack ABI packing; applicable 2.06 | Exact passes packed longs where custom supplies separate short words (or pointer-sized fields); customary GEM/VDI/trap call encoding. No custom-only mismatch found. |
| `gembind.c:161-172` | Integer-width / timer ABI; applicable 2.06 | Exact preserves big-endian two-short-as-long workaround; custom combines high/low timer words and initializes absent timer value to zero (avoids undefined read). Correct custom behavior. |
| `gembind.c:455-478`; `gemctrl.c:375-378,636-647,690-717`; `gemdisp.c:180-183,227-230`; `gemflag.c:40-56`; `gemasync.c:138-141` | ABI/signature or width workaround; applicable 2.06 | Branch-specific callback argument splitting, corrected `ob_find` arity, menu-message arity, window accessor arity, event callback word split, tick reconstruction, and event flag initialization. Custom-side changes are intentional ABI corrections; no further defect demonstrated. `wm_get(...WF_FIRST/NEXT...)` missing extra arg is in exact/legacy branch, custom AES3D branch supplies NULL and is not active in 2.06. |
| `geminit.c:440-...` and `geminit.c:759-762,856-870,943-980`; `gemrom.c:121-141,211-213,261-...`; `gemrslib.c:143-146`; `gemshlib.c:413-430` | Inherited TOS fix / return-value and argument-arity corrections; applicable according to version guards | Custom variant restores missing return values, country/resource entries, correct ROM/cache call arity and `gsx_fix` arity. No demonstrated custom-only regression. |
| `gemwmlib.c:128-...` | Mostly exact compatibility quirks plus custom corrections; applicable portions depend on AESVERSION | Exact-only `garbage` data, exact-return oddities, bounds-check order and missing cleanup behavior are inherited image-matching defects. Custom-only fixes include bounds check ordering and release of window records; these are consistent corrections. Window-state branches examined; no additional custom regression demonstrated. |
| `apgrlib.S:510-513`; `apgsxif.S:863-...`; `gemgsxif.S:53-57,149-...`; `gemjstrt.S:101-110,279-282`; `jbind.S:267-270` | Binary-layout / instruction encoding / compiler workaround; version-specific | Exact/custom select stack-adjust encoding, historical plane-count and cache behavior, and assembler symbol availability. No custom-only state or ABI bug demonstrated. |
| `gemevlib.c:347-349`, `gemfslib.c:351-353`, `gemfslib330.c:220-223`, `gemmnlib.c:239-241, mn_mbar.c:398-400`, `gemoblib.c:1914-1916` | Compiler-warning workaround; applicable by source/version | Initialize otherwise-unread warning-only values for the custom compiler path; no runtime change intended. |
| `gemrom.c:368-370`; remaining `gemrom.c` country tables | Country/resource feature behavior; applicable 2.06 | Custom adds country mappings/return behavior missing in exact historical image. Intentional. |

No AES custom-only regression was demonstrated that warranted a code change. Review was static; no runtime proof claimed. Integration/build and the desktop scenarios were subsequently verified as recorded below.
## VDI

| File:lines / symbol | Classification and review |
|---|---|
| `copyrfm.S:62,80,91` | Assembler-optimization workaround: omits zero-valued operands on >=3.0 or custom builds. No behavior change intended. |
| `entry.S:139` | Binary-layout/data-segment placement for legacy exact builds. |
| `escape.S:58-62` | Compiler compatibility: GNU builds force BINEXACT off. Branch-width choices at 327, 852, 909, 1305 are exact-code encoding/branch-range compatibility only. |
| `gsxasm1.S:67,190`; `sbhline.S:32`; `sbtxtblt.S:41`; `sbvline.S:30,76` | Assembler optimization / branch-encoding workarounds (elide explicit zero operand; select short branch where build/version permits). No custom functional regression found. |
| `gsxasm2.S:171-187` (`PX_PUTPIX`) | Custom uses active VDI context `a1` for line width, bytes-per-pixel and planes; exact path uses suspicious `a4` and raw 68030 opcode. Custom is correction of incorrect context/register encoding, not regression. |
| `gsxasm2.S:302-333` (`_get_pix`) | ABI/compiler workaround: custom saves/restores callee-saved `d3`; exact legacy omits to preserve binary. Loop executes once then DBRA using planes-minus-one; not an off-by-one. |
| `gsxasm2.S:359-383` (`_fill_line`) | C ABI adaptation: custom saves registers, reads stack arguments at post-save offset 36, restores; exact path uses legacy frame and tail branch. Argument ordering `x1,x2,y` is consistent with subsequent exchange. |
| `gsxasm2.S:414-425,584-587,765-780` (`_end_pts` paths) | C ABI save-frame offsets and restores. Inspected surrounding path: custom stack frame sizes 36/40 match saved register sets; paths restore before return. No demonstrated error. |
| `gsxasm2.S:989-993` (`_SetOverlay`) | Definite custom correction: C arguments d3/d4 saved at entry (4 bytes), so flag parameter is at 16(sp) after saved regs and four 16-bit coordinate loads; exact tests 12(sp), an incorrect argument. Correct custom path selects set/clear flag. |
| `isin.c:51` | Version/API availability gate for Isin implementation; not a custom-only runtime bug. |
| `monout.c:192,202,507,589-592,997-1006,1113-1121,1255-1261` | Exact compiler/register-allocation accommodations and unused declarations, not custom behavior. |
| `monout.c:386-388` | Custom break prevents fallthrough/repeated `d_justified()` in switch case; correct switch termination (inherited TOS behavior fix). |
| `monout.c:982-985` | Custom default handles invalid fill style instead of using undefined `pp`; robustness fix, not a regression. |
| `monout.c:1352-1372` | Exact-code padding/branch-shape accommodation for old versions/country; no custom behavior change. |
| `monout.c:1554-1557` | Custom initializes `line_len`, `dx`, `dy` before use when `NPTSIN < 1`; demonstrable undefined/uninitialized-state fix. |
| `monout.c:1947-1950` | Return type/value distinction for exact legacy ABI versus custom void path; custom `return;` follows function's declared return type (inspect declaration if modifying). No demonstrated incorrect behavior. |
| `mouse.S:401,412` | Structure-offset compatibility across version/layout (hotspot and save length fields), not a custom-only fix. No mouse restoration regression identified in these branches. |
| `palette.S:361-364` | Hades/country exact binary padding/table layout. |
| `sbescape.S:306-309` | Custom fixes pointer arithmetic: `d0` is a byte offset in long-width address arithmetic; exact `add.w` truncates/doesn't carry into upper pointer bits. Correctness improvement for larger offsets. |
| `sbtxtblt.S:1054-...` | Embedded exact instruction words assembler workaround for TOS >=3.0; binary encoding preservation. |
| `sbtxtblt.S:2271-2274` | Branch width compatibility only. |
| `spxblit.S:223-226,395-398,567-570,739-742,910-913,1081-1085` | Six NOT-D-only loops. Correct loop targets are own loop labels in custom code; exact paths have inherited wrong labels. `d7` is initialized to width-minus-one immediately at each `oA*Line` entry and DBRA is reached after the first NOT, so iteration count is correct including one-pixel width. Custom correction prevents jumping into a different Boolean-operation loop and unintended source/destination accesses. |
| `text.c:127-130` | Legacy TOS 1.04 font-specific behavior gate. |
| `text.c:149-152,222-225,236-239` | Custom defaults avoid undefined values for invalid input cases; robustness fixes, not introduced regressions. |
| `text.c:1292-1294,1343-1345` | Exact-code layout/branch-shape padding. |
| `vdi.h:10-14` | GNU compiler compatibility forces non-exact mode. |
| `vdidefs.h:49-50` | Default BINEXACT setting. |
| `xfrmform.S:79,116-122,169-171,204-207,213-226,238-240,271-310` | Form-transform algorithm: custom clears high bits, retains plane count, uses long-width counters/address arithmetic and explicit count loops. These are necessary correctness fixes for 32-bit dimensions/offsets and not a performance change; exact branches preserve legacy code. Reviewed transfer iteration setup/termination; no custom off-by-one observed. |

### Static-review limits

Inventory is from source text search for `BINEXACT` within `vdi/` and covers each matching source conditional, including assembly and included-source candidates. `BINEXACT` may also affect generated/indirect code through external macros/includes without its token occurring in VDI source; those are outside this audit. Static inspection only: no runtime proof or compilation performed. `monout.c:1947` return-value branch and wider `xfrmform.S` algorithm are classified from local signatures/control flow, not exercised on hardware.
## Desktop

| File:line / symbol | Classification | Review |
|---|---|---|
| `deskdefs.h:15-16`; `desktop.h:18-22` | build/compiler selection | Default BINEXACT and non-Alcyon fallback; not a runtime variant bug. `desktop.h:68-72` STATIC linkage choice and `:306-308` custom prototype are related ABI/build choices. |
| `deskif.S:32-36,386-389,895-898` | compiler/ABI + feature gate | GNU assembler forces non-BINEXACT; legacy Alcyon entry shim and AES>=2 cache shim. No custom-only defect demonstrated. |
| `deskact.c:155-157` (`which`) | quiet compiler | `mode` switch assigns `which` for the valid delete/copy/move cases before the dialog title uses it. |
| `deskact.c:240-242` (`ret`) | quiet compiler | Read only under `item == OKCP && ret`; `ret` assigned by `dofiles` on OK path; short-circuit protects cancel path. |
| `deskact.c:482-484` (`tmpx/y/x1/y1`) | quiet compiler | Drag coordinates assigned from mouse state before their loop uses; initial values are only for compiler diagnostics. |
| `deskact.c:905-907` (`docopy`, `exec`) | quiet compiler | `exec` assigned by `ch_obj` on drag-movement path; `docopy` assigned when destination changes before later action dispatch. No defect shown. |
| `deskdir.c:268-270` (`temp`) | quiet compiler | Used/freed only for `opcode == OP_DELETE`, branch assigns it from `fixdst`; non-delete path frees `fixdst`. |
| `deskdir.c:691-693` (`outhand`) | quiet compiler | `wrfile`: file handle is set by `Fcreate` before successful-write completion uses/closes it; error exits bypass the close or follow paths as noted below. No demonstrated custom-only issue. |
| `deskdir.c:797-800` | inherited TOS fix | Non-BINEXACT closes output before deleting a failed partial file; sensible compiler/custom path, and no evidence this introduces a regression. |
| `deskdir.c:841-844,853-857,864-876,887-890` | inherited TOS/version behavior | Close before delete on >=4/custom; legacy 3.x exact branch takes `y0` close label instead. Keep exact-version behavior pending runtime evidence. |
| `deskdir.c:1345-1349,1357-1361` (`backdir`) | inherited return-value/ABI accommodation | BINEXACT returns resource-index `OK` despite void-like use; custom build returns. No change warranted without caller evidence. |
| `deskdisk.c:224-226` (`field`) | quiet compiler | Each format/copy selection case assigns `field` (`0`/`NIL`) before subsequent dialog operation; initial value is not consumed first. |
| `deskdisk.c:185-…`, `239-242`, `256-260` | binary-layout/TOSPATCH | Hades exact-build object-index relocation workaround, gated to exact Hades/resource configuration. Preserve. |
| `deskdisk.c:438-440,456-459,470-473,613-616,636-… ,697-700` | compiler ABI / miscompile workarounds | BINEXACT argument layout and inline asm paths intentionally differ from custom typed calls; documented sector-count/relocation code. Not a demonstrated custom-only regression. |
| `deskfile.c:253-255` (`ret`) | quiet compiler | All active `switch(mode)` cases assign `ret` before comparison; `S_DATE` initializes it itself. |
| `deskfile.c:436-440` | ABI accommodation | Cartridge search uses historical exact call shape vs custom call with explicit attributes; comment says attribute is unused. No demonstrated behavior difference. |
| `deskfile.c:488-492` | inherited TOS fix | Dot-directory filtering fix for >=4/custom prevents skipping names whose only dot is in extension; old 3.x exact behavior intentionally retained. |
| `deskinf.c:607-611` | compiler ABI accommodation | Historical exact call passes extra argument; custom C declaration uses two. No demonstrated custom-only failure. |
| `deskinf.c:622-636` | feature/version gate | Default desktop/window pattern values differ for AES>=3.30/custom vs earlier exact builds. Inherited compatibility behavior, not a compiler regression. |
| `deskins.c:356-…` | inherited TOS fix | >=4/custom branch guards handling of empty app string; existing 3.x exact behavior remains separate. |
| `deskins.c:424-426` (`which`, `ret`) | quiet compiler | `which`/`ret` assigned by dialog/input processing before reads; no actionable stale read found. |
| `deskmenu.c:677-682` | quiet initialization / message ABI | Custom path zeroes unused tail of AES message for `do_scroll`; exact path relies on legacy message-buffer behavior. No output-path regression demonstrated. |
| `deskmenu.c:1027-1029` (`i`) | quiet compiler | `i` assigned `0` for view cases and `3` for sort cases before `xxxview[i]`; other cases return (`SCOLTYPE`) or flow only through documented cases. |
| `deskmenu.c:1544-…`, `1564-1568` | binary-layout/TOSPATCH | Exact Hades object-index patch for DEFFILE resource layout; custom uses symbolic index. Preserve. |
| `deskmenu.c:1584-1586` (`fi`) | quiet compiler | `fi` is set in the loop/state-handling path before use; initialized due to initial jump to `ad_2`. |
| `deskmisc.c:622-624` (`pm`) | quiet compiler | In 12-hour path every branch sets AM/PM before formatting; 24-hour path does not read `pm`. |
| `deskopen.c:32-36` | BINEXACT ABI shim | Exact AES call-stack/return convention; custom uses declared wrapper elsewhere. |
| `deskopen.c:209-212` (`subtype`, `dir2`) | quiet compiler / confirmed fix | `subtype` only used after path assignment; `dir2` is initialized before desktop-vs-window branch, then window path overwrites with `w_memory`. Existing fix prevents the demonstrated clobbering of an initialized window pointer. No further edit. |
| `deskopen.c:590-593` (`item`) | inherited TOS fix | Custom-only initializer avoids compiler warning before `open_subdir`; TOS exact path preserves original call behavior. No custom-only defect found. |
| `deskpref.c:151-153` (`outpat`) | quiet compiler | `outpat` set on `DESKPREF`/`WINPREF` selection before target dereference; SOK/cancel leave without reading it. |
| `deskpref.c:217-220` | inherited TOS fix | Null object-pointer guard on >=4/custom; avoids dereference when no window object. Preserve. |
| `desksear.c:298-300` (`newi`) | quiet compiler | Used only on rename/highlight path after match sets it; `first` ensures first hit assignment. |
| `desktop.c:261-265` | ABI accommodation | Exact return convention for legacy helper; custom returns void-compatible. No evidence for change. |
| `desktop.c:399-401` (`i`) | quiet compiler | Sort switch assigns index before use. |
| `desktop.c:467-469` | inherited TOS fix | New-desktop wind_set for >=4/custom only; compatibility/version behavior. |
| `desktop.c:535-539` | inherited TOS fix | TT detection handles version field for >=4/custom; old exact test retains legacy semantics. |
| `desktop.c:575-…` | binary-layout/compiler workaround | Alcyon-specific register/data placement hack; deliberately excluded from non-Alcyon exact mode by header. |
| `deskupda.c:55-57` (`copy2`) | quiet compiler | `copy2` is set in the branch that establishes/uses the second copy buffer before reads; initialization only quiets custom compiler. |
| `deskwin.c:207-209` (`ret`) | quiet compiler; pre-existing generic risk, not custom-only | The custom ret=FALSE default covers the cartridge branch where no media check assigns ret; the non-cartridge branch supplies the check result. No live-value clobber was found. |
| `deskwin.c:900-918` (`ted/text/len/iblk`) | quiet compiler | Icon branch assigns `iblk`, text branch assigns `ted/text/len`; each corresponding drawing path consumes only its branch's live fields. |


## Runtime and build verification

The reviewed custom ROM matches `build/tos206uk-info-fixed/tos206uk.img`
byte-for-byte. The rebuilt exact UK ROM matches the original working stock
build byte-for-byte. The compiler frontend fix therefore adds no behavior
change to either of those Alcyon images.

`test/check_desktop_operations.py` drives actual desktop input and only reads
emulated RAM to synchronize/inspect UI state. It does not invoke desktop
functions directly or change their variables. Each scenario gets a disposable
host-directory drive and fresh Hatari process/configuration:

- **Copy:** drag a selected file onto a folder; verify all 9,997 bytes at the
  destination and that the original remains.
- **Move:** Ctrl-drag a selected file onto a folder; verify destination bytes
  and removal of the source.
- **Rename:** edit Show Information's filename; verify the old name disappears
  and the new file retains its contents.
- **Delete:** select a file and accept the desktop deletion dialog; verify
  that the selected file is removed.
- **Search:** enter a filename in the actual search dialog; verify that the
  matching directory item is selected and a non-match is not.
- **Configuration saving:** switch to text view, save desktop configuration,
  verify that NEWDESK.INF changed, then start a new emulator process and verify
  that text view is restored.

Delete and Text are assigned keyboard shortcuts through a valid fixture
NEWDESK.INF, as normal desktop preferences permit; mouse-menu navigation is
not claimed as covered. The older Show Information regression remains
available separately for file/folder names, sizes and contained-file count.
Screenshots, emulator logs and a machine-readable list of passed scenarios
are saved in the selected output directory. All six operation scenarios
passed in a single consolidated run against the reviewed ROM.

Run these checks after building a matching UK 2.06 ROM and linked image:

```sh
python3 test/check_bios_preprocess.py
python3 test/check_os_memory.py build/tos206uk-reviewed/tos.img
python3 test/check_desktop_operations.py \
  build/tos206uk-reviewed/tos206uk.img build/tos206uk-reviewed/tos.img \
  --output build/tos206uk-reviewed/desktop-proof
```

Use `--operation copy` (or another operation, repeatable) to diagnose a
specific scenario without rerunning the others.

Six further data-loss scenarios subsequently passed in
`check_desktop_folders.py` and `check_desktop_conflicts.py`: recursive folder
copy/move/delete, overwrite with truncation, conflict cancellation, and
rename collision rejection. The original six scenarios also passed with
the synchronized event-loop harness. See the
[prioritized test plan](testing-plan.md) for exact assertions, commands,
fixture dependencies and the remaining tiers.

## Remaining verification limits

This is not a declaration that TOS or every custom configuration is bug-free.
The UI scenarios use Hatari's GEMDOS host-directory drive, not an ACSI disk
image or HDDRIVER; they do not prove BIOS media-I/O behavior. Physical Mega STE
hardware, printers/serial devices, alternate boards/CPUs, all resolutions,
all countries and patch combinations were not exercised. Nor does this suite
cover recursive folder search, disk-full/write-error recovery, multiple
selection permutations, or every dialog/menu entry method.

GNU preprocessing is checked, not a complete GNU compiler/linker ROM build.
Inherited TOS defects and optional fixes remain distinct from new
reconstruction regressions; no original-TOS fix was enabled merely because
it appeared in this review. Future changes should add a consumer-visible
regression scenario when a new failure is demonstrated, rather than relying
on successful boot as evidence of general correctness.

## Direct conditional inventory

This appendix records direct source sites, including inactive version/CPU
branches and configuration defaults. It is an audit snapshot, not a test that
pins source wording or line numbers. Shared macros can also affect generated
code indirectly; the layout/configuration review above covers the principal
shared mechanisms.

### `aes/aes.h`

```text
56: #if BINEXACT
103: #if BINEXACT
287: #if (AESVERSION >= 0x330) | !BINEXACT
599: #if !BINEXACT
637: #if BINEXACT
895: #if (AESVERSION >= 0x330) | !BINEXACT
```

### `aes/aesdefs.h`

```text
61: #ifndef BINEXACT
```

### `aes/apgrlib.S`

```text
510: #if (AESVERSION >= 0x200) | !BINEXACT
```

### `aes/apgsxif.S`

```text
863: #if (AESVERSION <= 0x320) & BINEXACT
935: #if (AESVERSION >= 0x200) | !BINEXACT
1332: #if (AESVERSION >= 0x200) | !BINEXACT
```

### `aes/gemaplib.c`

```text
165: #if BINEXACT
248: #if BINEXACT
255: #if BINEXACT
292: #if BINEXACT
```

### `aes/gemasync.c`

```text
138: #if BINEXACT
```

### `aes/gembind.c`

```text
48: #if BINEXACT & (AESVERSION < 0x330)
161: #if BINEXACT
170: #if !BINEXACT
455: #if (AESVERSION >= 0x330) | !BINEXACT
474: #if (AESVERSION >= 0x330) | !BINEXACT
```

### `aes/gemctrl.c`

```text
65: #if BINEXACT
375: #if BINEXACT
529: #if BINEXACT
612: #if !BINEXACT
636: #if BINEXACT
644: #if BINEXACT
690: #if AES3D & !BINEXACT
714: #if AES3D & !BINEXACT
880: #if BINEXACT /* sigh */
890: #if BINEXACT
```

### `aes/gemdisp.c`

```text
180: #if BINEXACT
198: #if BINEXACT /* sigh */
212: #if BINEXACT
227: #if BINEXACT
```

### `aes/gemevlib.c`

```text
347: #if !BINEXACT
```

### `aes/gemflag.c`

```text
40: #if BINEXACT
49: #if !BINEXACT
55: #if !BINEXACT
```

### `aes/gemfmlib.c`

```text
293: #if BINEXACT /* sigh... */
374: #if BINEXACT /* sigh... */
479: #if BINEXACT
```

### `aes/gemfslib.c`

```text
351: #if !BINEXACT
```

### `aes/gemfslib330.c`

```text
220: #if !BINEXACT
```

### `aes/gemgsxif.S`

```text
53: #if BINEXACT
149: #if (AESVERSION >= 0x330) | !BINEXACT
1222: #if (AESVERSION >= 0x200) & !BINEXACT
```

### `aes/geminit.c`

```text
172: #if (AESVERSION >= 0x330) | !BINEXACT
441: #if BINEXACT
506: #if !BINEXACT
656: #if (AESVERSION < 0x330) & BINEXACT
694: #if (AESVERSION >= 0x200) & BINEXACT
719: #if (AESVERSION >= 0x200) | !BINEXACT
727: #if (AESVERSION >= 0x330) | !BINEXACT
759: #if BINEXACT
766: #if (AESVERSION >= 0x330) | !BINEXACT
837: #if (AESVERSION >= 0x330) | !BINEXACT
856: #if (AESVERSION >= 0x200) | !BINEXACT
866: #if BINEXACT /* sigh... */
939: #if (TOSVERSION >= 0x400) | !BINEXACT
943: #if BINEXACT /* sigh... */
948: #if (TOSVERSION >= 0x400) | !BINEXACT
970: #if (TOSVERSION >= 0x400) | !BINEXACT
978: #if !BINEXACT
```

### `aes/geminput.c`

```text
596: #if BINEXACT /* sigh */
614: #if BINEXACT
622: #if BINEXACT
```

### `aes/gemjstrt.S`

```text
101: #if (TOSVERSION >= 0x200) | !BINEXACT
107: #if (TOSVERSION >= 0x200) | !BINEXACT
279: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `aes/gemmnlib.c`

```text
45: #if BINEXACT
239: #if !BINEXACT
446: #if BINEXACT /* sigh */
```

### `aes/gemobed.c`

```text
70: #if !BINEXACT
550: #if BINEXACT
```

### `aes/gemoblib.c`

```text
87: #if BINEXACT
226: #if BINEXACT
252: #if BINEXACT
507: #if !BINEXACT
1440: #if BINEXACT
1914: #if !BINEXACT
```

### `aes/gemrom.c`

```text
121: #if !BINEXACT
138: #if !BINEXACT
211: #if !BINEXACT
261: #if BINEXACT
338: #if BINEXACT
368: #if !BINEXACT
```

### `aes/gemrslib.c`

```text
143: #if !BINEXACT
```

### `aes/gemshlib.c`

```text
414: #if BINEXACT
427: #if BINEXACT
690: #if (AESVERSION >= 0x330) | !BINEXACT
```

### `aes/gemwmlib.c`

```text
128: #if (AESVERSION >= 0x200) & BINEXACT
241: #if BINEXACT
246: #if BINEXACT
251: #if BINEXACT
256: #if BINEXACT
260: #if !BINEXACT
343: #if (AESVERSION >= 0x200) | !BINEXACT
347: #if BINEXACT
408: #if BINEXACT
714: #if BINEXACT
964: #if BINEXACT
1186: #if BINEXACT
1213: #if BINEXACT
1236: #if BINEXACT
1492: #if !BINEXACT /* BUG: missing in 3.06 */
1522: #if BINEXACT
1643: #if BINEXACT
1744: #if !BINEXACT
1748: #if BINEXACT
1916: #if (AESVERSION < 0x200) & BINEXACT
1946: #if !BINEXACT
1953: #if BINEXACT
1998: #if (AESVERSION >= 0x330) | !BINEXACT
2020: #if (AESVERSION >= 0x330) | !BINEXACT
2106: #if (AESVERSION >= 0x330) | !BINEXACT
2145: #if (AESVERSION >= 0x330) | !BINEXACT
```

### `aes/jbind.S`

```text
267: #if (AESVERSION >= 0x200) | !BINEXACT
```

### `aes/mn_mbar.c`

```text
63: #if BINEXACT
398: #if !BINEXACT
```

### `bdos/fsfat.c`

```text
1148: #if BINEXACT
```

### `bdos/fsopnclo.c`

```text
285: #if HADES & BINEXACT & !RAMVERSION
```

### `bdos/ldiv.S`

```text
75: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `bdos/osinit.S`

```text
200: #if (TOSVERSION >= 0x200) | !BINEXACT
225: #if (TOSVERSION < 0x200) | !BINEXACT
521: #if (GEMDOS >= 0x18) | !BINEXACT
```

### `bdos/osmem.c`

```text
391: #if !BINEXACT
```

### `bdos/umem.c`

```text
344: #if GEMDOS >= 0x18 | !BINEXACT
385: #if GEMDOS >= 0x18 | !BINEXACT
797: #if BINEXACT
```

### `bios/bios.h`

```text
31: #if BINEXACT
```

### `bios/biosdefs.h`

```text
59: #ifndef BINEXACT
```

### `bios/blkdev.c`

```text
64: #if BINEXACT
115: #if HADES & BINEXACT
307: #if TP_25 | !BINEXACT /* ED_BIOS */
553: #if HADES & BINEXACT
896: #if HADES & BINEXACT
1060: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `bios/chardev.S`

```text
25: #if (TOSVERSION >= 0x200) | !BINEXACT
131: #if (TOSVERSION >= 0x200) | !BINEXACT
234: #if ((TOSVERSION >= 0x200) & (TOSVERSION < 0x300)) | !BINEXACT | (TOSVERSION >= 0x400)
268: #if BINEXACT
298: #if (TOSVERSION < 0x200) | !BINEXACT
306: #if (TOSVERSION < 0x200) | !BINEXACT
326: #if (TOSVERSION < 0x200) | !BINEXACT
346: #if (TOSVERSION < 0x200) | !BINEXACT
372: #if !BINEXACT
379: #if (TOSVERSION >= 0x200) | !BINEXACT
425: #if (TOSVERSION >= 0x200) | !BINEXACT
568: #if (TOSVERSION >= 0x200) | !BINEXACT
1015: #if (TOSVERSION >= 0x200) | !BINEXACT
1175: #if (TOSVERSION >= 0x200) | !BINEXACT
1311: #if (TOSVERSION >= 0x200) | !BINEXACT
1336: #if (TOSVERSION >= 0x200) | !BINEXACT
1360: #if (TOSVERSION >= 0x200) | !BINEXACT
1376: #if (TOSVERSION >= 0x200) | !BINEXACT
1398: #if (TOSVERSION >= 0x200) | !BINEXACT
1415: #if (TOSVERSION >= 0x200) | !BINEXACT
1421: #if (TOSVERSION >= 0x200) | !BINEXACT
2662: #if (TOSVERSION >= 0x300) | !BINEXACT
2768: #if (TOSVERSION >= 0x200) | !BINEXACT
2790: #if (TOSVERSION >= 0x200) | !BINEXACT
3674: #if (TOSVERSION >= 0x200) | !BINEXACT
3772: #if (TOSVERSION >= 0x200) | !BINEXACT
4055: #if (TOSVERSION < 0x200) | !BINEXACT
4093: #if (TOSVERSION < 0x200) | !BINEXACT
4135: #if (TOSVERSION < 0x200) | !BINEXACT
4254: #if (TOSVERSION >= 0x200) | !BINEXACT
4391: #if ((TOSVERSION >= 0x200) & (TOSVERSION < 0x300)) | !BINEXACT | (TOSVERSION >= 0x400)
4586: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `bios/dma.inc`

```text
350: #if ((TOSVERSION >= 0x300) & (TOSVERSION < 0x400)) | !BINEXACT
```

### `bios/floppy.S`

```text
617: #if (TOSVERSION >= 0x200) | !BINEXACT
627: #if (TOSVERSION >= 0x200) | !BINEXACT
634: #if (TOSVERSION >= 0x200) | !BINEXACT
649: #if (TOSVERSION >= 0x200) | !BINEXACT
657: #if (TOSVERSION >= 0x200) | !BINEXACT
664: #if (TOSVERSION >= 0x200) | !BINEXACT
680: #if (TOSVERSION >= 0x200) | !BINEXACT
709: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `bios/fpsp060/skel060.S`

```text
214: #if BINEXACT
248: #if BINEXACT
254: #if BINEXACT
```

### `bios/hadxbios.S`

```text
286: #if BINEXACT
2526: #if BINEXACT
```

### `bios/ikbdclk.S`

```text
25: #if BINEXACT /* Year 2k fix */
104: #if BINEXACT /* Year 2k fix */
```

### `bios/keytbl.c`

```text
604: #if (OS_COUNTRY == CTRY_DK) | (MULTILANG_SUPPORT & !BINEXACT)
646: #if (OS_COUNTRY == CTRY_PL) | (MULTILANG_SUPPORT & !BINEXACT)
706: #if (OS_COUNTRY == CTRY_CZ) | (MULTILANG_SUPPORT & !BINEXACT)
772: #if (OS_COUNTRY == CTRY_NL) | (MULTILANG_SUPPORT & !BINEXACT)
834: #if (OS_COUNTRY == CTRY_TR) | (MULTILANG_SUPPORT & !BINEXACT)
```

### `bios/keytbl.h`

```text
62: #if !BINEXACT
```

### `bios/m64_pci.S`

```text
2736: #if BINEXACT
```

### `bios/medusamm.S`

```text
272: #if BINEXACT
306: #if BINEXACT
```

### `bios/nvram.S`

```text
316: #if (TOSVERSION >= 0x200) | !BINEXACT
323: #if !BINEXACT
333: #if BINEXACT
342: #if (TOSVERSION >= 0x200) | !BINEXACT
400: #if (TOSVERSION < 0x200) & BINEXACT
440: #if (TOSVERSION >= 0x200) | !BINEXACT
487: #if (TOSVERSION < 0x200) & BINEXACT
496: #if (TOSVERSION >= 0x200) | !BINEXACT
506: #if (TOSVERSION >= 0x200) | !BINEXACT
517: #if (TOSVERSION >= 0x200) | !BINEXACT
526: #if (TOSVERSION >= 0x200) | !BINEXACT
672: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `bios/scrdmp.inc`

```text
37: #if (TOSVERSION < 0x200) & BINEXACT
```

### `bios/sounds.c`

```text
71: #if (TOSVERSION >= 0x200) | !BINEXACT
```

### `bios/startup.S`

```text
29: #if !BINEXACT
1180: #if BINEXACT
1210: #if BINEXACT
1863: #if BINEXACT
2829: #if BINEXACT
2975: #if !BINEXACT
3101: #if !P68010 | !BINEXACT
3145: #if !P68010 | !BINEXACT
3758: #if !BINEXACT
4191: #if STBOOK | !BINEXACT
4531: #if !TP_18 | BINEXACT
```

### `common/asmdefs.h`

```text
137: #if BINEXACT
```

### `common/nopatch.h`

```text
1: #if BINEXACT
```

### `common/sections.inc`

```text
96: #if BINEXACT
```

### `desk/deskact.c`

```text
155: #if !BINEXACT
240: #if !BINEXACT
482: #if !BINEXACT
905: #if !BINEXACT
```

### `desk/deskbind.c`

```text
186: #if !BINEXACT
```

### `desk/deskdefs.h`

```text
15: #ifndef BINEXACT
```

### `desk/deskdir.c`

```text
268: #if !BINEXACT
691: #if !BINEXACT
797: #if !BINEXACT
841: #if (TOSVERSION >= 0x400) | !BINEXACT
853: #if (TOSVERSION < 0x400) & BINEXACT
864: #if (TOSVERSION >= 0x400) | !BINEXACT
872: #if (TOSVERSION < 0x400) & BINEXACT
887: #if (TOSVERSION < 0x400) & BINEXACT
1345: #if BINEXACT
1357: #if BINEXACT
```

### `desk/deskdisk.c`

```text
185: #if HADES & BINEXACT & (FCBOXF == 9) & !RAMVERSION
224: #if !BINEXACT
239: #if HADES & BINEXACT & (FCBOXF == 9) & !RAMVERSION
256: #if HADES & BINEXACT & (FCBOXF == 9) & !RAMVERSION
438: #if BINEXACT
456: #if BINEXACT
470: #if BINEXACT
613: #if BINEXACT
636: #if BINEXACT
697: #if BINEXACT
```

### `desk/deskfile.c`

```text
253: #if !BINEXACT
436: #if BINEXACT
488: #if (TOSVERSION >= 0x400) | !BINEXACT
```

### `desk/deskif.S`

```text
32: #if BINEXACT
386: #if BINEXACT
895: #if !BINEXACT & (AESVERSION >= 0x200)
```

### `desk/deskinf.c`

```text
607: #if BINEXACT
622: #if (AESVERSION >= 0x330) | !BINEXACT
```

### `desk/deskins.c`

```text
356: #if (TOSVERSION >= 0x400) | !BINEXACT
424: #if !BINEXACT
```

### `desk/deskmenu.c`

```text
677: #if !BINEXACT
1027: #if !BINEXACT
1544: #if HADES & BINEXACT & (DEFFILE == 9) & !RAMVERSION
1564: #if HADES & BINEXACT & (DEFFILE == 9) & !RAMVERSION
1584: #if !BINEXACT
```

### `desk/deskmisc.c`

```text
622: #if !BINEXACT
```

### `desk/deskopen.c`

```text
32: #if BINEXACT
209: #if !BINEXACT
590: #if !BINEXACT
```

### `desk/deskpref.c`

```text
151: #if !BINEXACT
217: #if (TOSVERSION >= 0x400) | !BINEXACT
```

### `desk/desksear.c`

```text
298: #if !BINEXACT
```

### `desk/desktop.c`

```text
261: #if BINEXACT
399: #if !BINEXACT
467: #if (TOSVERSION >= 0x400) | !BINEXACT
535: #if (TOSVERSION >= 0x400) | !BINEXACT
575: #if BINEXACT
```

### `desk/desktop.h`

```text
18: #if BINEXACT
68: #if BINEXACT
306: #if !BINEXACT
```

### `desk/deskupda.c`

```text
55: #if !BINEXACT
```

### `desk/deskwin.c`

```text
207: #if !BINEXACT
900: #if !BINEXACT
916: #if !BINEXACT
```

### `vdi/copyrfm.S`

```text
62: #if (TOSVERSION >= 0x300) | !BINEXACT
80: #if (TOSVERSION >= 0x300) | !BINEXACT
91: #if (TOSVERSION >= 0x300) | !BINEXACT
```

### `vdi/entry.S`

```text
139: #if (TOSVERSION < 0x300) & BINEXACT
```

### `vdi/escape.S`

```text
58: #if BINEXACT
327: #if BINEXACT & (TOSVERSION < 0x400) & (TOSVERSION >= 0x300)
852: #if BINEXACT & (TOSVERSION < 0x300)
909: #if BINEXACT & (TOSVERSION < 0x300)
1305: #if BINEXACT & (TOSVERSION < 0x400)
```

### `vdi/gsxasm1.S`

```text
67: #if (TOSVERSION >= 0x300) | !BINEXACT
190: #if (TOSVERSION >= 0x300) | !BINEXACT
```

### `vdi/gsxasm2.S`

```text
171: #if BINEXACT
183: #if BINEXACT
302: #if (TOSVERSION >= 0x300) | !BINEXACT
332: #if (TOSVERSION >= 0x300) | !BINEXACT
359: #if (TOSVERSION >= 0x300) | !BINEXACT
377: #if (TOSVERSION >= 0x300) | !BINEXACT
419: #if (TOSVERSION >= 0x300) | !BINEXACT
584: #if (TOSVERSION >= 0x300) | !BINEXACT
765: #if (TOSVERSION >= 0x300) | !BINEXACT
777: #if (TOSVERSION >= 0x300) | !BINEXACT
989: #if BINEXACT
```

### `vdi/isin.c`

```text
51: #if (TOSVERSION >= 0x300) | !BINEXACT
```

### `vdi/monout.c`

```text
192: #if BINEXACT & (TOSVERSION < 0x400)
202: #if BINEXACT & (TOSVERSION < 0x400)
386: #if !BINEXACT
507: #if BINEXACT & (TOSVERSION < 0x400) /* only register declaration different */
589: #if BINEXACT & (TOSVERSION < 0x400)
982: #if !BINEXACT
997: #if BINEXACT & (TOSVERSION < 0x400)
1004: #if BINEXACT & (TOSVERSION < 0x400)
1113: #if BINEXACT & (TOSVERSION < 0x400)
1120: #if BINEXACT & (TOSVERSION < 0x400)
1255: #if BINEXACT & (TOSVERSION < 0x400)
1260: #if BINEXACT & (TOSVERSION < 0x400)
1352: #if (TOSVERSION < 0x300) & BINEXACT
1367: #if (TOSVERSION < 0x200) | (TOSVERSION >= 0x300) | !BINEXACT /* hmpf */
1370: #if (TOSVERSION <= 0x104) & BINEXACT & (OS_COUNTRY != CTRY_NL)
1554: #if !BINEXACT
1947: #if BINEXACT
```

### `vdi/mouse.S`

```text
401: #if (TOSVERSION >= 0x300) | !BINEXACT
412: #if (TOSVERSION >= 0x300) | !BINEXACT
```

### `vdi/palette.S`

```text
361: #if HADES & BINEXACT & (OS_COUNTRY != CTRY_DE)
```

### `vdi/sbescape.S`

```text
306: #if BINEXACT
```

### `vdi/sbhline.S`

```text
32: #if (TOSVERSION >= 0x300) | !BINEXACT
```

### `vdi/sbtxtblt.S`

```text
41: #if (TOSVERSION >= 0x300) | !BINEXACT
1054: #if BINEXACT
2271: #if (TOSVERSION < 0x300) & BINEXACT
```

### `vdi/sbvline.S`

```text
30: #if (TOSVERSION >= 0x300) | !BINEXACT
76: #if (TOSVERSION >= 0x300) | !BINEXACT
```

### `vdi/spxblit.S`

```text
223: #if BINEXACT
395: #if BINEXACT
567: #if BINEXACT
739: #if BINEXACT
910: #if BINEXACT
1081: #if BINEXACT
```

### `vdi/text.c`

```text
127: #if (TOSVERSION <= 0x104) & BINEXACT
149: #if !BINEXACT
222: #if !BINEXACT
236: #if !BINEXACT
1292: #if BINEXACT
1343: #if BINEXACT
```

### `vdi/vdi.h`

```text
10: #if BINEXACT
```

### `vdi/vdidefs.h`

```text
49: #ifndef BINEXACT
```

### `vdi/xfrmform.S`

```text
79: #if (TOSVERSION >= 0x300) | !BINEXACT
116: #if (TOSVERSION >= 0x300) | (!BINEXACT)
120: #if (TOSVERSION >= 0x400) | (!BINEXACT)
169: #if (TOSVERSION >= 0x300) | (!BINEXACT)
170: #if (TOSVERSION >= 0x400) | (!BINEXACT)
204: #if (TOSVERSION >= 0x300) | (!BINEXACT)
213: #if (TOSVERSION >= 0x300) | (!BINEXACT)
224: #if (TOSVERSION >= 0x300) | (!BINEXACT)
238: #if (TOSVERSION >= 0x300) | (!BINEXACT)
271: #if (TOSVERSION >= 0x300) | (!BINEXACT)
282: #if (TOSVERSION >= 0x300) | (!BINEXACT)
291: #if (TOSVERSION >= 0x300) | (!BINEXACT)
298: #if (TOSVERSION >= 0x300) | (!BINEXACT)
307: #if (TOSVERSION >= 0x300) | (!BINEXACT)
```

