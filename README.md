# YD67BLE Bluetooth keys

Add Bluetooth control keys to the **KBDFans KBD67 Lite** fitted with **YDKB's
YD67BLE** dual-mode (USB + Bluetooth) PCB: one-key host switching and a
Bluetooth on/off switch.

The stock YDKB firmware already implements these actions, but the default keymap
doesn't bind them to any key. This repo rebuilds your firmware image with them bound.
It changes only the keymap; the firmware code is left as it is.

| Keys | Action |
| --- | --- |
| `Fn` + `Tab` | Switch to the next paired Bluetooth host |
| `Fn` + `Caps Lock` | Toggle output between USB and Bluetooth |
| `Fn` + `T` | Turn Bluetooth **on**. The keyboard restarts. |
| `LCtrl` + `Fn` + `T` | Turn Bluetooth **off**. The keyboard restarts. |

`Fn` is the key just left of the arrow keys (tap = Menu, hold = Fn layer).
Every other key keeps its current function.

## Is this for my keyboard?

Plug the keyboard in over USB and check:

```console
$ lsusb | grep -i ydkb
Bus 001 Device 004: ID feed:2167 YDKB YD67BLE (USB_DMBT)
```

If you see `feed:2167 YDKB YD67BLE (USB_Dxxx)`, it's supported.
The suffix is the firmware version: `DMBT` = 2022-11-29, `DO6M` = 2024-06-22.

Not supported:

- The original wired KBD67 Lite PCB. It runs QMK and has no Bluetooth.
- YDKB's VIA/Vial firmware for this board, shown as `(VIAL_Dxxx)`. YDKB's
  docs say it doesn't support switching between Bluetooth hosts.

## Requirements

- Linux with `udisks2` (`udisksctl`), which most desktop distributions have, and `sudo` access.
- Python 3.8+. Only the standard library is used.

To use macOS or Windows instead, see [Other operating systems](#other-operating-systems).

## Quick start

```sh
git clone <this repo>
cd <this repo>
./flash.sh
```

`flash.sh` will:

1. Ask you to put the keyboard in flash mode, with the USB cable connected.
   - Press `LShift` + `RShift` + `LCtrl` + `B`, **or**
   - unplug the cable, hold `Esc`, plug it back in, then release `Esc`.

   The Caps LED blinks continuously and a disk named `YD67BLE` appears.
2. Copy the keyboard's current firmware into `backups/` and check that it was read
   correctly.
3. Build `build/YD67BLE.BIN` from **your current firmware and keymap**, plus the keys
   above. It refuses to overwrite an `Fn` combination you already use.
4. Ask for confirmation, then write the image with `sudo dd ... seek=4`. This is
   [YDKB's documented Linux method](https://ydkb.io/help/#/en/bootloader/msd-bootloader).
   It's the only step that needs root.

When it finishes, the keyboard restarts on its own. If the Caps LED keeps blinking,
press `Esc`.

### Options

| Option | Effect |
| --- | --- |
| `--upgrade` | Use the bundled newest official firmware code (`DO6M`, 2024-06-22) instead of keeping your current version. It includes macOS sleep/wake fixes and makes USB 6KRO by default ([changelog](https://ydkb.io/help/#/changelog/yd67ble)). |
| `--default` | Start from the ydkb.io default keymap instead of your current one. |

## Turning Bluetooth off

Out of the box, the keyboard turns Bluetooth on whenever it runs on battery.
`LCtrl` + `Fn` + `T` disables the Bluetooth function entirely. The setting is saved
in the keyboard's EEPROM, so it survives restarts and battery power-offs.

With Bluetooth off:

- Over USB, the keyboard works normally, but the firmware doesn't start the Bluetooth
  module, so no host can find or connect to it.
- On battery, without a cable, the keyboard doesn't start.
- `LShift` + `RShift` + `S` no longer shows a connection status.

To turn Bluetooth back on, plug in the USB cable and press `Fn` + `T`. YDKB's docs
say pressing `F` + `J` together also works on battery for some of their boards.
Turning Bluetooth off doesn't clear your pairings.

`LShift` + `RShift` + `W` (on) and `LShift` + `RShift` + `LCtrl` + `W` (off) do the
same thing without the keymap change. For short breaks, Lock Mode (`Fn` + `Z`) is
usually the better choice. It puts the keyboard into deep sleep until you press
`F` + `J` together.

## Pairing two hosts

The Bluetooth module (Adafruit Bluefruit firmware) can't select a specific host.
`Fn` + `Tab` disconnects the current host and connects whichever other paired host
responds. If none responds, it reconnects to the previous one after a timeout.
It works best with **two** hosts, paired this way
([YDKB's guide](https://ydkb.io/help/#/en/ble-series/device-switching)):

1. On every host, remove the keyboard from the Bluetooth settings.
2. On the keyboard, press `LShift` + `RShift` + `LCtrl` + `R` to clear its stored pairings.
3. Pair host A. Once typing works, **turn Bluetooth off on host A**.
4. Pair host B.
5. Turn Bluetooth back on for host A. `Fn` + `Tab` now switches between A and B.

Tips:

- While the USB cable is connected, keystrokes go to USB. Press `Fn` + `Caps Lock`
  (or `LShift` + `RShift` + `U`) to send them over Bluetooth.
- `LShift` + `RShift` + `S` makes the Caps LED show the connection status: fast
  blinking means not connected, slow blinking means connected.
- Known limitations, according to YDKB:
  - The keyboard can't show which host is active.
  - After deep sleep it may reconnect to either host.
  - Switching *to* a Mac, iPhone or iPad can take a few seconds.

## Choosing different keys

```sh

python3 yd67ble.py build --keymap-from backups/<backup>.BIN --base backups/<backup>.BIN \
    --next-key 1 --power-key 0 --mode-key ""   # Fn+1 hosts, Fn+0 BT on/off, no USB/BT key
python3 yd67ble.py info build/YD67BLE.BIN     # show the resulting Fn layer
```

Run `python3 yd67ble.py build --help` to see every key name. Then flash
`build/YD67BLE.BIN` as described in [Recovery](#recovery) or
[Other operating systems](#other-operating-systems).

## Other operating systems

`yd67ble.py` runs anywhere Python 3 does. Only `flash.sh` is Linux-specific.

1. Enter flash mode as described in [Quick start](#quick-start).
2. Copy `YD67BLE.BIN` from the `YD67BLE` disk somewhere safe. This file is your backup.
3. Build the new image:
   ```sh
   python3 yd67ble.py build --base path/to/backup.BIN --keymap-from path/to/backup.BIN
   ```
4. Flash `build/YD67BLE.BIN`:
   - **Windows:** drag it onto the `YD67BLE` disk and overwrite the existing file,
     then eject the disk.
   - **macOS:** follow [YDKB's command-line steps](https://ydkb.io/help/#/en/bootloader/msd-bootloader)
     (`diskutil umount`, then `sudo dd ... seek=4`).

## Recovery

- To restore your previous firmware, enter flash mode, then run:
  ```sh
  sudo dd if=backups/<file>.BIN of=/dev/sdX seek=4 && sync
  ```
  Replace `/dev/sdX` with the `YD67BLE` disk. Use `lsblk` to find it.
- If the keyboard no longer starts:
  1. Hold a magnet over the battery reed switch, which is left of `Tab`, to cut the
     battery power.
  2. Hold `Esc` while plugging in the cable.
  3. Remove the magnet and flash again.
- You can also flash any image generated at [ydkb.io](https://ydkb.io): select
  *YD67BLE*, then download the `.bin`.

## How it works

`yd67ble.py` does what the [ydkb.io](https://ydkb.io) configurator does in the browser:

- The keymap is at `0x6000`–`0x67FF` of the 26 KiB application image: 8 layers × 128
  16-bit TMK action codes, indexed by unimap position.
- `0xF50B` is YDKB's "next Bluetooth host" action, `0xF00B` is "USB/Bluetooth toggle"
  and `0xFD0B` is "Bluetooth function on (off with `LCtrl`)".
- ydkb.io doesn't offer `0xFD0B` for the YD67BLE, though it does for other YDKB
  Bluetooth boards. The disassembled `DMBT` and `DO6M` firmware handle it on this board
  the same way as the `LShift` + `RShift` + `W` shortcut. The firmware writes `0x01` (on)
  or `0xBD` (off) to EEPROM address `0x20`, then restarts. At boot, `0xBD` keeps the
  Bluetooth module disabled.
- The word at `0x6700` is adjusted so that the 16-bit word sum of the image equals
  `0x2167` (the USB PID). The bootloader checks this, and `yd67ble.py check` uses it
  to verify backups.

The code region is never modified.

| File | Purpose |
| --- | --- |
| `flash.sh` | Linux helper: backup → build → flash |
| `yd67ble.py` | Builder and inspector (`build`, `info`, `check`) |
| `firmware/YD67BLE_DO6M_base.bin` | Official YD67BLE firmware, unmodified (`config/yd67ble.bin` in [ydkb/ydkb.github.io](https://github.com/ydkb/ydkb.github.io)) |
| `firmware/default_keymap.json` | ydkb.io default keymap (from `config/layout-yd67ble.html` in the same repo) |

## Credits and disclaimer

The YD67BLE PCB and its firmware are by YANG / [YDKB](https://ydkb.io). The bundled
firmware binary is their work, redistributed unmodified from their public
repository. This project isn't affiliated with YDKB or KBDFans.

Flashing firmware always carries some risk. Use these tools at your own risk.
`flash.sh` makes a backup before it writes anything, so keep that file.
