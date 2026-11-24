#!/usr/bin/env python3
"""Build YD67BLE (KBD67 Lite BLE PCB) firmware with Bluetooth host-switch keys.

The YD67BLE runs YDKB's closed-source TMK-based firmware. Its keymap is a
plain table at 0x6000-0x67FF of the 26 KiB application image, and the
firmware already implements the actions this tool maps:

    0xF50B  BT_NEXT  disconnect the current Bluetooth host and connect the
                     next bonded one (falls back to the previous host on
                     timeout, see ydkb.io/help ble-series/device-switching)
    0xF00B  BT_USB   toggle output between USB and Bluetooth
    0xFD0B  BT_POWER turn the Bluetooth function on; with LCtrl held, turn it
                     off. Stored in EEPROM, applied by restarting the keyboard
                     (same as the LShift+RShift+W / +LCtrl+W shortcuts)

This does what https://ydkb.io does in the browser: keep the code, rewrite
the keymap, then fix the image checksum so the bootloader accepts it.
Python stdlib only.
"""

import argparse
import base64
import gzip
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = HERE / "firmware" / "YD67BLE_DO6M_base.bin"
DEFAULT_KEYMAP = HERE / "firmware" / "default_keymap.json"

FW_SIZE = 0x6800
KEYMAP_ADDR = 0x6000
LAYERS, SLOTS = 8, 128  # 8 layers x 128 unimap slots (8 rows x 16 cols)
# ydkb.io CONFIG.kbd.yd67ble.checksum: the 16-bit little-endian word sum of
# the whole image must equal this (it is the USB PID, 0x2167). The word at
# CHECKSUM_ADDR (layer 7, slot 0, an unused position) is the adjustment.
CHECKSUM_ADDR = 0x6700
CHECKSUM_VALUE = 0x2167

TRNS = 0x0001
BT_NEXT = 0xF50B
BT_USB = 0xF00B
BT_POWER = 0xFD0B

# Unimap slot of every key on the KBD67 Lite (from ydkb.io layout-yd67ble.html).
KEYS = {
    "ESC": 0x29, "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27, "MINUS": 0x2D,
    "EQUAL": 0x2E, "BSPC": 0x2A, "HOME": 0x4A,
    "TAB": 0x2B, "Q": 0x14, "W": 0x1A, "E": 0x08, "R": 0x15, "T": 0x17,
    "Y": 0x1C, "U": 0x18, "I": 0x0C, "O": 0x12, "P": 0x13, "LBRC": 0x2F,
    "RBRC": 0x30, "BSLS": 0x31, "PGUP": 0x4B,
    "CAPS": 0x39, "A": 0x04, "S": 0x16, "D": 0x07, "F": 0x09, "G": 0x0A,
    "H": 0x0B, "J": 0x0D, "K": 0x0E, "L": 0x0F, "SCLN": 0x33, "QUOT": 0x34,
    "ENTER": 0x28, "PGDN": 0x4E,
    "LSHIFT": 0x79, "Z": 0x1D, "X": 0x1B, "C": 0x06, "V": 0x19, "B": 0x05,
    "N": 0x11, "M": 0x10, "COMMA": 0x36, "DOT": 0x37, "SLASH": 0x38,
    "RSHIFT": 0x7D, "UP": 0x52, "END": 0x4D,
    "LCTRL": 0x78, "LGUI": 0x7B, "LALT": 0x7A, "SPACE": 0x2C, "RALT": 0x7E,
    "FN": 0x7C, "LEFT": 0x50, "DOWN": 0x51, "RIGHT": 0x4F,
}
SLOT_NAME = {v: k for k, v in KEYS.items()}

YDKB_FN = {
    0xF00B: "BT/USB toggle", 0xF20B: "BT hide", 0xF30B: "BT discoverable",
    0xF40B: "BT clear bonds", 0xF50B: "BT next host", 0xFB0B: "battery %",
    0xFD0B: "BT on (LCtrl: BT off)",
    0xFC0B: "Lock Mode", 0xF002: "Reset/flash", 0xF003: "Win Lock",
    0xF001: "Alt+F4", 0xF004: "Space2", 0xF300: "Esc/~`", 0xF200: "Esc/~`(L)",
    0xF100: "Esc/~`(R)", 0xF700: "Esc/~` (tricky)",
}


def describe(code):
    if code == TRNS:
        return "____"
    if code in YDKB_FN:
        return YDKB_FN[code]
    kind = code >> 12
    if kind in (0, 1) and code < 0x100:
        return f"key 0x{code:02X}"
    if kind in (0xA, 0xB):
        return f"Fn(L{(code >> 8) & 0x1F})/tap 0x{code & 0xFF:02X}"
    if kind == 4:
        return f"consumer 0x{code & 0x3FF:03X}"
    if kind == 5:
        return f"mouse 0x{code & 0xFF:02X}"
    return f"0x{code:04X}"


def read_image(path):
    data = Path(path).read_bytes()
    if len(data) < FW_SIZE:
        sys.exit(f"{path}: {len(data)} bytes, expected at least {FW_SIZE}")
    image = bytearray(data[:FW_SIZE])
    if "YD67BLE (USB_D".encode("utf-16-le") not in image:
        sys.exit(f"{path}: not a YD67BLE ydkb.io firmware (USB product string missing)")
    return image


def firmware_version(image):
    tag = "(USB_D".encode("utf-16-le")
    i = image.find(tag) + len(tag)
    return "D" + image[i:i + 6].decode("utf-16-le")


def word_sum(image):
    return sum(struct.unpack(f"<{len(image) // 2}H", image)) & 0xFFFF


def checksum_ok(image):
    return word_sum(image) == CHECKSUM_VALUE


def fix_checksum(image):
    struct.pack_into("<H", image, CHECKSUM_ADDR, 0)
    struct.pack_into("<H", image, CHECKSUM_ADDR, (CHECKSUM_VALUE - word_sum(image)) & 0xFFFF)


def get_keymap(image):
    flat = struct.unpack_from(f"<{LAYERS * SLOTS}H", image, KEYMAP_ADDR)
    return [list(flat[i * SLOTS:(i + 1) * SLOTS]) for i in range(LAYERS)]


def set_keymap(image, km):
    struct.pack_into(f"<{LAYERS * SLOTS}H", image, KEYMAP_ADDR, *[c for layer in km for c in layer])


def load_default_keymap():
    km = json.loads(DEFAULT_KEYMAP.read_text())["keymaps"]
    return [[c for row in layer for c in row] for layer in km]


def fn_layer(km):
    """Layer activated by the key in the Fn position (LT(1, Menu) by default)."""
    code = km[0][KEYS["FN"]]
    if code >> 12 in (0xA, 0xB):
        return (code >> 8) & 0x07
    return 1


def print_layer(km, layer):
    for name, slot in KEYS.items():
        code = km[layer][slot]
        if code != TRNS:
            print(f"    Fn+{name:7s} {describe(code)}")


def cmd_info(args):
    image = read_image(args.file)
    km = get_keymap(image)
    layer = fn_layer(km)
    print(f"{args.file}: firmware {firmware_version(image)}, "
          f"checksum {'OK' if checksum_ok(image) else 'NOT VALID'}")
    print(f"  Fn layer = L{layer}:")
    print_layer(km, layer)


def cmd_check(args):
    image = read_image(args.file)
    if not checksum_ok(image):
        sys.exit(f"{args.file}: checksum invalid (misread or not a ydkb.io image)")
    print(f"{args.file}: firmware {firmware_version(image)}, checksum OK")


def cmd_build(args):
    base = read_image(args.base)
    if args.keymap_from:
        src = read_image(args.keymap_from)
        if not checksum_ok(src):
            sys.exit(f"{args.keymap_from}: checksum invalid, refusing to trust its keymap "
                     "(the backup may be truncated or misread)")
        km = get_keymap(src)
        origin = f"{args.keymap_from} ({firmware_version(src)})"
    else:
        km = load_default_keymap()
        origin = "ydkb.io default keymap"

    layer = fn_layer(km)
    wanted = {}
    for key, code in ((args.next_key, BT_NEXT), (args.mode_key, BT_USB), (args.power_key, BT_POWER)):
        if not key:
            continue
        if KEYS[key] in wanted:
            sys.exit(f"Fn+{key} is assigned to two actions; pick different keys.")
        wanted[KEYS[key]] = code
    for slot, code in wanted.items():
        cur = km[layer][slot]
        if cur not in (TRNS, code) and not args.force:
            sys.exit(f"Fn+{SLOT_NAME[slot]} is already '{describe(cur)}'. "
                     "Pick another key or pass --force to overwrite it.")
        km[layer][slot] = code

    image = bytearray(base)
    set_keymap(image, km)
    fix_checksum(image)
    assert checksum_ok(image)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_bytes(image)

    print(f"Wrote {args.output}")
    print(f"  code:   {args.base} ({firmware_version(base)})")
    print(f"  keymap: {origin}, Fn layer L{layer}")
    print_layer(km, layer)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("info", help="show firmware version, checksum and Fn layer of a .BIN")
    i.add_argument("file")
    i.set_defaults(func=cmd_info)

    c = sub.add_parser("check", help="exit non-zero unless the image has a valid checksum")
    c.add_argument("file")
    c.set_defaults(func=cmd_check)

    b = sub.add_parser("build", help="build a YD67BLE.BIN with Bluetooth switch keys")
    b.add_argument("--base", default=str(DEFAULT_BASE),
                   help="firmware image providing the code (default: official DO6M, 2024-06-22)")
    b.add_argument("--keymap-from", metavar="BIN",
                   help="take the keymap from this image (e.g. a backup of your keyboard) "
                        "instead of the ydkb.io default")
    b.add_argument("--next-key", default="TAB", choices=sorted(KEYS),
                   help="Fn + this key = switch to next Bluetooth host (default: TAB)")
    b.add_argument("--mode-key", default="CAPS", choices=sorted(KEYS) + [""],
                   help="Fn + this key = toggle USB/Bluetooth output (default: CAPS, '' to skip)")
    b.add_argument("--power-key", default="T", choices=sorted(KEYS) + [""],
                   help="Fn + this key = Bluetooth on, LCtrl + Fn + this key = Bluetooth off "
                        "(default: T, '' to skip)")
    b.add_argument("--force", action="store_true", help="overwrite keys already bound on the Fn layer")
    b.add_argument("-o", "--output", default=str(HERE / "build" / "YD67BLE.BIN"))
    b.set_defaults(func=cmd_build)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
