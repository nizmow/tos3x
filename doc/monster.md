# MonSTer alternate RAM in TOS 2.06

This adds optional ROM initialization for the original Alan Hourihane MonSTer
board on ST, STE, and Mega STE. It does not target MonSTerbo or change IDE,
RTC, or flash programming support.

## Build

From the repository root on Linux x86-64:

```sh
podman build -f tools/Containerfile.cross -t localhost/tos3x-cross .
tools/build-monster.sh
```

The default is UK TOS 2.06 with 8 MiB of alternate RAM. Output:

- `build/monster-uk-8/tos206uk.img`: 256 KiB ROM image.
- `build/monster-uk-8/MONSTER.TOS`: hardware memory test program.
- `build/monster-uk-8/tos.sym`: symbols for Hatari and the routine tests.
- `build/monster-uk-8/build.log`: build log.

Choose another language or reduce the RAM window if other hardware occupies it:

```sh
COUNTRY=us MONSTER_RAM_MB=6 tools/build-monster.sh
```

Supported RAM sizes are 2, 4, 6, and 8 MiB, starting at `0x400000`.
The ROM caps the size at 6 MiB on Mega STE because VME starts at `0xA00000`.
Other expansion conflicts must be accounted for by the selected build size.

The script builds in an isolated source copy with Alcyon, using
`TOSVERSION=206 BINEXACT=0 MONSTER=1`. `BINEXACT=0` also enables the existing
patch defaults in `common/patchdef.h` and the existing IKBD year correction.
MonSTer is off by default; ordinary binary-exact ROM builds remain available.
The non-binary-exact configuration currently enables TP_05, TP_13, TP_15,
TP_19, TP_20, TP_28, TP_29, TP_53, TP_57, TP_61, TP_62, and TP_66 by default; some apply only
to particular hardware or TOS versions. Arrowfix, SHBUF, and WinX remain off.

## Behaviour

After GEMDOS initialization, before disk boot and AUTO programs, the ROM:

1. Checks Alt; holding it bypasses MonSTer initialization.
2. Probes `0xFFFFFE00` with bus-error protection. An absent board leaves the
   machine's memory pools and cookie jar unchanged.
3. Enables the configured RAM using the board's read/write/write sequence.
4. Reuses an existing `_FRB` cookie or allocates a permanent 64 KiB ST-RAM
   transfer buffer and installs the cookie. This is required by TOS floppy
   routines when a program's buffer is in alternate RAM.
5. Registers the RAM with GEMDOS through `xmaddalt()`.

If a new transfer buffer cannot be allocated, the cookie jar is full, or RAM
registration fails, no alternate RAM is added. A new buffer is freed if
registration fails. The hardware window may already have been enabled, but
GEMDOS will not allocate from it. Warm resets initialize a fresh GEMDOS pool
and repeat registration; this does not append the region to an old pool.

The old `_ramtop` variable remains reserved for TT-style memory above 16 MiB.
MonSTer memory is registered as a separate region and is not counted as ST-RAM.
Program header flags and `Mxalloc()` modes continue to control its use.

## Testing on the board

1. Keep a working ROM/flash bank available. Install the new image using your
   existing MonSTer flash procedure. This repository does not program flash.
2. Remove `M_ALTRAM.PRG` from AUTO for this ROM: it must not register the same
   RAM region a second time. Also disable any other automatic RAM registrar.
3. Cold boot and run `MONSTER.TOS`. It allocates the largest alternate RAM
   block, writes and verifies two address-dependent patterns over its complete
   longwords, frees the block, and displays PASS or FAIL. The test only writes
   allocated RAM; it does not write disk sectors or flash. The byte count is
   printed in hexadecimal; other resident programs may already use some RAM.
   The checker itself loads into ST-RAM so it can test the alternate RAM.
4. Test an application marked for alternate RAM, including file reads from
   floppy and your hard-disk driver, then repeat after a warm reset.
5. Cold boot with Alt held and verify no alternate RAM is available. Use this
   mode when the flash tool needs the RAM/flash address window.

Some software must remain in ST-RAM. This addition does not make ST video,
blitter, or DMA hardware able to address MonSTer RAM. Hard-disk drivers must
handle alternate-RAM buffers correctly; `_FRB` supplies a conventional buffer
but cannot repair an incompatible external driver.

## Emulator coverage

`tools/build-monster.sh` runs `test/monster_test.py` against the actual linked
ROM code using Unicorn's 68000 CPU. GEMDOS calls and the MonSTer register are
simulated. Tests cover ST/STE/Mega STE sizes, absence, read/write bus-error
recovery, Alt bypass, existing buffers, full cookie jars, allocation failures,
registration failure cleanup, and register/stack/vector preservation.
The checker executable is also relocated and executed with simulated GEMDOS
calls, checking its PASS, bad-memory, and no-memory paths.

Hatari can verify booting on a machine without MonSTer, with ROM patching
disabled. It does not reproduce the physical MonSTer register/RAM mapping;
successful hardware enablement, memory reliability, and DMA require board tests.

Hardware protocol references:

- [Jo Even Skarstein's MonSTer tools](https://atari.joska.no/monster/).
- [EmuTOS hardware definitions](https://github.com/emutos/emutos/blob/master/bios/machine.h).
- [EmuTOS alternate RAM initialization](https://github.com/emutos/emutos/blob/master/bios/memory2.c).

The new initializer is an independent 68000 assembly implementation of the
board protocol using this tree's GEMDOS allocator and cookie jar.
