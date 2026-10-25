#!/bin/sh
# Build in an isolated source copy; leave the checkout's configuration alone.
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
country=${COUNTRY:-uk}
ram_mb=${MONSTER_RAM_MB:-8}
case "$country" in us|de|fr|uk|es|it|se|sf|sg|cz|nl) ;; *) echo "Invalid COUNTRY" >&2; exit 1;; esac
case "$ram_mb" in 2|4|6|8) ;; *) echo "MONSTER_RAM_MB must be 2, 4, 6, or 8" >&2; exit 1;; esac
output_dir="$repo_dir/build/monster-$country-$ram_mb"
mkdir -p "$output_dir"

podman run --rm --network=none \
    -v "$repo_dir:/src:ro" -v "$output_dir:/out:rw" \
    "${TOS3X_IMAGE:-localhost/tos3x-cross}" sh -ec '
        mkdir -p /out/source
        tar --exclude=.git --exclude=build -C /src -cf - . | tar -xf - -C /out/source
        cd /out/source
        # clean after copying so compiler/configuration changes cannot reuse objects
        make TOSVERSION=206 COUNTRY="$1" clean > /out/build.log 2>&1
        touch common/localcnf.h
        make TOSVERSION=206 COUNTRY="$1" BINEXACT=0 MONSTER=1 MONSTER_RAM_MB="$2" >> /out/build.log 2>&1
        cp "glue/tos206$1.img" /out/
        bin/linux/cnm glue/tos.img > /out/tos.sym
        bin/linux/cc68 -c -o test/monster.o test/monster-check.S
        bin/linux/link68 "[prgflags[1]]" /out/monster.rel=test/monster.o
        bin/linux/relmod /out/monster.rel /out/MONSTER.TOS
        python3 /src/test/monster_test.py "/out/tos206$1.img" /out/tos.sym \
            --ram-mb "$2" --checker /out/MONSTER.TOS
    ' sh "$country" "$ram_mb"
echo "ROM and hardware test: $output_dir"
