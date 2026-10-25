# Building TOS 2.06 for an ST

The bundled Linux Alcyon compiler builds a working 256 KiB TOS 2.06 ROM.
The GCC path exists but needs compatibility fixes before it can produce a ROM.
The existing `localhost/pistorm-atari-cross:trixie` image targets ARM64, not 68000.

## Verified baseline

Build the container from the repository root (Linux x86-64):

```sh
podman build -f tools/Containerfile.cross -t localhost/tos3x-cross .
```

The container includes native build tools, Hatari, and Unicorn for testing
the MonSTer routine. The ROM uses the bundled Alcyon tools:

```sh
podman run --rm --network=none -v "$PWD:/work" localhost/tos3x-cross \
  make TOSVERSION=206 COUNTRY=uk
```

Use `COUNTRY=us`, `de`, etc. for another keyboard/resource configuration.
Always run `make clean` with the same configuration before changing compiler,
country, or TOS version. Build separate copies if retaining both compiler builds.

The output is `glue/tos206uk.img`. The verified UK build has:

- Size: 262144 bytes; linked image has 8500 bytes free before padding.
- MD5: `e690bec90d902024beed549d22150755`, matching `hatari/MD5SUMS`.
- SHA-256: `b776d5ade5ace0d09cb9f13a85ac07f6d492ab69fcac1b56995573f620f74e6c`.
- ROM base: `0xE00000`.

The `roms/` reference files are symlinks to the original author's machine;
they are unavailable here. `make check` therefore cannot compare their bytes.

## Hatari smoke test

This boots a plain 8 MHz ST with 4 MiB RAM and Hatari ROM patches disabled.
Hatari emulates the ROM mapping; the real ST needs the ROM decoder to expose
the 256 KiB image at `0xE00000`. Chip interleaving/programming depends on the
decoder board and is a separate step.

```sh
mkdir -p build
cat > build/boot.ini <<'EOF'
b VBL = 10000 :once :file /work/build/capture.ini
c
EOF
cat > build/capture.ini <<'EOF'
screenshot /work/build/tos206uk-st.png
quit
EOF
podman run --rm --network=none -v "$PWD:/work" localhost/tos3x-cross \
  sh -c 'SDL_AUDIODRIVER=dummy xvfb-run -a hatari \
    --tos /work/glue/tos206uk.img --machine st --memsize 4 \
    --monitor mono --sound off --fast-forward on --confirm-quit off \
    --patch-tos off --run-vbls 10100 --parse /work/build/boot.ini'
```

Verified with Hatari 2.5.0: the ROM finishes its memory test and reaches the
GEM desktop. A bus-error warning during RAM-size probing is expected in this
configuration. This is a boot smoke test; applications, peripherals, and the
physical ROM decoder have not been tested.

## GCC findings

The exploratory compiler packages were from the [MiNT toolchain maintainer](https://tho-otto.de/crossmint.php).
They are not included in the Alcyon container above.
GCC runs and selects its `mshort/libgcc.a` runtime. Keep `-mshort` for TOS's
16-bit integer ABI and target the 68000. A GCC ROM will not be binary identical
to Atari's Alcyon ROM; `common/config.h` forces `BINEXACT=0` under GCC, which
also enables the patch defaults in `common/patchdef.h`.

An exploratory build in a separate copy used:

```sh
touch common/localcnf.h
make USE_CROSS_ALCYON=0 CROSS=yes TOSVERSION=206 COUNTRY=uk BINEXACT=0 \
  RUN_OPTIMIZE_1= SUBDIRS='common tools bios vdi bdos aes desk glue'
```

This is a diagnostic command, not a working GCC recipe yet. Required work:

1. Fix GCC selection for `common` (`CROSS=yes` workaround above) and avoid
   passing Alcyon's `--optimize` to GCC (`RUN_OPTIMIZE_1=` workaround).
   Create `common/localcnf.h` before preprocessing configuration; the existing
   rule creates it too late for the first non-binary-exact build.
2. Replace two `.even` directives in `bios/dma.inc` with MRI-compatible `even`.
3. Correct mismatched parentheses in `bios/nvram.S:316` and
   `bios/floppy.S:128,138`.
4. Express the signed MOVEQ immediates in `tospatch/patches/fastprn.S` as
   `-64` and `-33` instead of `$c0` and `$DF`.
5. Resolve the pointer/integer argument mismatch at `bdos/umem.c:405`
   (`xmfree` expects `int32_t`).
6. Supply compatible MiNT headers: AES compilation reaches
   `include/string.h`'s `include_next`, then fails because the target system
   `string.h` is missing. The GCC package alone does not contain these headers.
7. Finish linking, check ROM size and RAM layout, audit default patches, and
   repeat Hatari boot/runtime tests. No GCC ROM has been linked or booted yet.

After exploratory fixes to items 2–4, BIOS, VDI, and desktop source compilation
completed with GCC 4.6.4. Binutils additionally needs `libfl.so.2` (provided by
`libfl2` on Debian). Optional `system` and `tospatch` utilities are
excluded from the diagnostic command; they are unnecessary for the ROM and
may need further target-library support.
