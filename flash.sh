#!/usr/bin/env bash
# Flash the YD67BLE with Bluetooth host-switch keys, keeping your current keymap.
#
#   ./flash.sh            back up current firmware, rebuild with its keymap, flash
#   ./flash.sh --default  use the ydkb.io default keymap instead of your current one
#   ./flash.sh --upgrade  also move the code to the bundled DO6M (2024-06-22) build
#                         (by default your keyboard's current firmware code is kept)
set -euo pipefail
cd "$(dirname "$0")"

USE_CURRENT_KEYMAP=1
KEEP_CODE=1
for arg in "$@"; do
  case "$arg" in
    --default) USE_CURRENT_KEYMAP=0 ;;
    --upgrade) KEEP_CODE=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

LABEL=YD67BLE
MAX_BYTES=$((4 * 1024 * 1024))   # the bootloader's virtual disk is tiny; never dd to anything big

cat <<EOF
Put the keyboard in flash mode now (USB cable connected), either:
  * press  LShift + RShift + LCtrl + B, or
  * unplug, hold Esc, plug the cable back in, release Esc.
The Caps LED blinks continuously and a disk named "$LABEL" appears.
Waiting up to 120 s...
EOF

dev=""
for _ in $(seq 120); do
  # The label may sit on the whole disk (superfloppy) or on a partition.
  dev=$(lsblk -rpno NAME,LABEL,TYPE,PKNAME | awk -v l="$LABEL" '$2==l {print ($3=="part" ? $4 : $1); exit}')
  [ -n "$dev" ] && break
  sleep 1
done
[ -n "$dev" ] || { echo "No whole-disk device labelled $LABEL found." >&2; exit 1; }

size=$(lsblk -bdno SIZE "$dev")
if [ "$size" -gt "$MAX_BYTES" ]; then
  echo "$dev is $size bytes - too big to be the keyboard bootloader. Aborting." >&2
  exit 1
fi
echo "Found $dev ($(lsblk -dno MODEL,SIZE "$dev" | xargs))"

# Read the current firmware through the filesystem (udisks, no root needed).
fsdev=$(lsblk -rpno NAME,LABEL | awk -v l="$LABEL" '$2==l {print $1; exit}')
mnt=$(lsblk -no MOUNTPOINT "$fsdev" | head -n1)
if [ -z "$mnt" ]; then
  udisksctl mount -b "$fsdev" >/dev/null
  mnt=$(lsblk -no MOUNTPOINT "$fsdev" | head -n1)
fi
fw=$(find "$mnt" -maxdepth 1 -iname "$LABEL.BIN" | head -n1)
[ -n "$fw" ] || { echo "$LABEL.BIN not found on $mnt" >&2; exit 1; }

mkdir -p backups build
backup="backups/YD67BLE-$(date +%Y%m%d-%H%M%S).BIN"
cp "$fw" "$backup"
echo "Backed up current firmware to $backup"
if ! python3 yd67ble.py check "$backup"; then
  echo "The backup doesn't look like a valid image, so neither its code nor its keymap is reused." >&2
  echo "Re-run with:  ./flash.sh --upgrade --default" >&2
  exit 1
fi

build_args=(build -o build/YD67BLE.BIN)
[ "$KEEP_CODE" = 1 ] && build_args+=(--base "$backup")
[ "$USE_CURRENT_KEYMAP" = 1 ] && build_args+=(--keymap-from "$backup")
python3 yd67ble.py "${build_args[@]}"

udisksctl unmount -b "$fsdev" >/dev/null 2>&1 || true

read -r -p "Write build/YD67BLE.BIN to $dev? [y/N] " ok
[ "$ok" = y ] || [ "$ok" = Y ] || { echo "Cancelled, nothing written."; exit 0; }

# Same method as ydkb.io's Linux instructions (help/bootloader/msd-bootloader).
sudo dd if=build/YD67BLE.BIN of="$dev" seek=4 conv=fsync status=none
sync
echo "Flashed. The keyboard leaves flash mode by itself; if the Caps LED keeps blinking, press Esc."
