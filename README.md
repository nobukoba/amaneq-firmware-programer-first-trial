# AMANEQ Firmware Programer (first trial)

**Language: English | [日本語](README.ja.md)**

Download and program AMANEQ firmware through openFPGALoader: MCS for the supported families, and temporary BIT loading for Skeleton.

## Quick installation

Python 3.10 or later and openFPGALoader are required. The Python program uses only the standard library; no `pip install` is required for this repository. openFPGALoader, USB drivers, and firmware images are not bundled.

For Ubuntu/Debian, install the tools, then clone this repository:

```bash
sudo apt update
sudo apt install git python3 openfpgaloader
git clone https://github.com/nobukoba/amaneq-firmware-programer-first-trial.git
cd amaneq-firmware-programer-first-trial
./amaneq-firmware-programer.py --help
```

## Check the cable first

Connect the cable to the correct JTAG connector and power the target board. Configure Linux USB permissions as described in the appendix, then list the connected cables:

More than one connected cable without `--serial` causes the program to print their serial numbers and exit with code 1. It never opens an interactive cable-selection menu. `--cable hs3` declares that the physical cable is an HS3; its USB ID is shared with other FT232H devices.

```bash
./amaneq-firmware-programer.py scan
```

## Write the latest v4 LRTDC MCS

The following command downloads the newest matching v4 MCS from the official default branch, prints the filename, checks the target, backs up the flash, programs it, and compares every written byte with a separate readback. The shortcut skips the final confirmation and starts programming immediately.

Use the serial shown by `scan` if multiple cables are connected. The serial in an example must be replaced with your selected device's value. After successful MCS verification, power-cycle the board to test flash boot.

```bash
./program-latest-mcs-amaneq-v4-lrtdc.sh --cable hs3
./program-latest-mcs-amaneq-v4-lrtdc.sh --cable hs3 --serial SERIAL_FROM_SCAN
```

## Select a firmware

Each shortcut has a `.sh` version and a Windows `.cmd` version. Keep the shared `firmware-latest-amaneq-common.sh` / `.cmd` alongside them.

| Firmware | Target | Shortcut stem |
|---|---|---|
| LRTDC, 1GbE | AMANEQ v4 | `program-latest-mcs-amaneq-v4-lrtdc` |
| HRTDC Base, 10GbE | AMANEQ v4 | `program-latest-mcs-amaneq-v4-hrtdc` |
| LRTDC-10G | AMANEQ v4 | `program-latest-mcs-amaneq-v4-lrtdc-10g` |
| Mikumari Clock Hub | AMANEQ v4 | `program-latest-mcs-amaneq-v4-mikumari` |
| Skeleton, persistent MCS | AMANEQ v4 | `program-latest-mcs-amaneq-v4-skeleton` |
| Skeleton, temporary BIT | AMANEQ v4 | `program-latest-bit-amaneq-v4-skeleton` |
| HRTDC mezzanine | HR-TDC mezzanine | `program-latest-mcs-amaneq-hrtdc-mzn` |

Skeleton supports BIT and MCS. All other families support MCS only. `mikumari` means MikuClockHub, not MikuClockPrim.

For a v1 board, use the Python command with `--target amaneq-v1`. Skeleton is shared by v1 and v4, as documented in the DAQ manual. Neither revision nor baseboard/mezzanine identity can be inferred from the shared FPGA ID alone.

```bash
./amaneq-firmware-programer.py program --latest --firmware skeleton --target amaneq-v1 --format bit --cable hs3
./program-latest-bit-amaneq-v4-skeleton.sh --cable hs3
./program-latest-mcs-amaneq-hrtdc-mzn.sh --cable hs3
```

## Use an existing file

`program --file` examines the contents to distinguish Intel HEX MCS from Xilinx BIT, regardless of the extension. The selected firmware family and physical target must agree with recognized filenames and FPGA metadata. The ordinary Python command asks for final confirmation; use `--yes` only for an intended unattended operation.

```bash
./amaneq-firmware-programer.py inspect --file firmware/amaneq-4-strlrtdc-v2.A.mcs
./amaneq-firmware-programer.py program --file firmware/amaneq-4-strlrtdc-v2.A.mcs --firmware lrtdc --target amaneq-v4 --cable hs3
```

## Download without programming

`download` does not access the hardware. GitHub downloads are pinned to a resolved commit and checked against the Git blob hash. Files and `.source.json` metadata are saved below `firmware/downloads/`. A mezzanine download without hardware probing requires selecting the flash variant, or choosing a file interactively if `--flash auto` finds multiple candidates.

```bash
./amaneq-firmware-programer.py download --latest --firmware lrtdc --target amaneq-v4 --format mcs
./amaneq-firmware-programer.py download --latest --firmware hrtdc --target hrtdc-mezzanine --format mcs --flash mt25qu256
```

## Choose an older version or another URL

History shows at most 10 total choices by default, including the current branch. Tags and commits pointing to the same revision are merged; historical revisions are sorted by commit date. Increase the total with `--history-limit` (maximum 1000), or specify a known tag/commit with `--ref`.

Use `--repo` for a GitHub repository URL and `--url` for a direct HTTP(S) file URL. A GitHub `blob` HTML page is not a direct firmware file. Direct downloads are content-checked; `--sha256` additionally checks a known expected digest. `--url` is separate from `--repo`, `--latest`, and `--ref`.

```bash
./amaneq-firmware-programer.py versions --firmware lrtdc --history-limit 30
./amaneq-firmware-programer.py download --choose-version --firmware lrtdc --target amaneq-v4 --format mcs --history-limit 30
./amaneq-firmware-programer.py download --repo https://github.com/AMANEQ-official/StrLrTdc --target amaneq-v4 --format mcs --ref v2.8
./amaneq-firmware-programer.py download --url "https://raw.githubusercontent.com/spadi-alliance/AMANEQ-Skeleton/main/bit/amaneq-skeleton-v2.2.bit" --firmware skeleton --target amaneq-v4
```

## Appendix

Further setup and operating details follow.

## Linux USB permissions

Install this host-side rule for HS3 / FT232H devices, join the group, then log out/in and reconnect the cable. The VID/PID is shared by other FT232H devices. Package installations may already provide appropriate udev rules.

```bash
sudo groupadd -f plugdev
sudo tee /etc/udev/rules.d/99-amaneq-hs3.rules >/dev/null <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6014", MODE="0660", GROUP="plugdev"
EOF
sudo usermod -aG plugdev "$USER"
sudo udevadm control --reload-rules
```

## Windows native setup

Install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/). Install openFPGALoader in the MSYS2 UCRT64 shell using the command below. For the standard `C:/msys64` layout, use the explicit executable and cygpath paths shown here. The repository contains no per-user registry setup and does not change `.py` associations.

The tested HS3 path requires WinUSB/libusb access; Vivado's FTDIBUS driver is not interchangeable. Driver replacement can also affect another HS3 with the same hardware ID. Back up the original driver before changing it. The tested Windows build did not include Xilinx Platform Cable support.

```bash
pacman -S mingw-w64-ucrt-x86_64-openFPGALoader
```

## Windows commands

Run these from PowerShell after cloning. The first two only inspect help/devices. The shortcut performs the write immediately. `AMANEQ_PYTHON` can override the Python executable; `AMANEQ_CYGPATH_DIR` can supply the directory containing `cygpath.exe`. Otherwise the Windows shortcut tries `py -3`, then `python`.

```powershell
py -3 amaneq-firmware-programer.py --help
py -3 amaneq-firmware-programer.py scan --loader C:/msys64/ucrt64/bin/openFPGALoader.exe
.\program-latest-mcs-amaneq-v4-lrtdc.cmd --cable hs3 --loader C:/msys64/ucrt64/bin/openFPGALoader.exe --cygpath-dir C:/msys64/usr/bin
```

## Platform and container status

Windows USB enumeration and the underlying Windows openFPGALoader/HS3 BIT and MCS commands were exercised on hardware. The final Python orchestration, Linux/WSL/container programming, and all mezzanine probing are tested with mocks, not on those physical environments. macOS download/inspection can run with Python, but macOS cable enumeration/programming is explicitly not implemented yet.

Linux containers still require host USB access. Docker Engine needs `/dev/bus/usb` access and device permissions. Apptainer usually exposes `/dev` and `/sys`; the host user's USB permissions still apply. WSL needs usbipd-win forwarding before Linux can see the cable. No Docker image or SIF is supplied in this first trial.

## Defaults, files, and failures

Defaults: firmware `lrtdc`, target `amaneq-v4`, download format `mcs`, cable `auto`, flash `auto`, network timeout 45 seconds, history total 10. All are shown by command-specific `--help`.

- Download files and source metadata: `firmware/downloads/`.
- Generated SPI bridge cache: `firmware/cache/`.
- Full flash backups, readbacks and result JSON: `logs/`.
- `--timeout` changes network inactivity timeout; it is not a programming deadline.
- DNS/offline errors, timeouts, HTTP 401/403/404/429, TLS failures, interrupted downloads, HTML/invalid firmware and checksum failures stop with an English `ERROR:` message.
- Exit codes: 0 for completion, 1 for operational/validation failure, 2 for argument syntax errors, 130 for interrupted input/operation.
- `--yes` skips the final programming confirmation. It does not silently resolve ambiguous hardware or file choices.

Keep the backups. MCS programming can erase the entire flash; verification covers the resulting image bytes. A successful byte comparison does not establish successful power-cycle boot or working DAQ/network operation.

```bash
./amaneq-firmware-programer.py program --help
```

## Mezzanine and SiTCP licenses

For GitHub MCS programming with `--flash auto`, the mezzanine command identifies the flash before selecting the download. Probing temporarily loads an SPI bridge into FPGA SRAM, replacing the running DAQ configuration, but does not erase flash. MT25QU256 and N25Q128 are selected by the JEDEC signature and capacity; the flash is checked again before erase. Unknown or contradictory devices stop.

Firmware programming does not install a SiTCP license. SiTCP and SiTCP-XG are separate licenses; moving between 1GbE and 10GbE firmware may require the appropriate EEPROM license/configuration using separate tools. This program does not write license EEPROMs.

## References and development

Use the [DAQ programming manual](https://www.rcnp.osaka-u.ac.jp/~spadi/wiki/?SPADI-A%20DAQ%20%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB/%E3%83%95%E3%82%A1%E3%83%BC%E3%83%A0%E3%82%A6%E3%82%A7%E3%82%A2/%E3%83%95%E3%82%A1%E3%83%BC%E3%83%A0%E3%82%A6%E3%82%A7%E3%82%A2%E3%81%AE%E6%9B%B8%E3%81%8D%E8%BE%BC%E3%81%BF%E6%96%B9%E6%B3%95) for connector/board setup and the [openFPGALoader installation guide](https://trabucayre.github.io/openFPGALoader/guide/install.html) for USB/runtime installation.

Official firmware sources: [StrLrTdc](https://github.com/AMANEQ-official/StrLrTdc), [StrHrTdcBase](https://github.com/AMANEQ-official/StrHrTdcBase), [StrLrTdc-10G](https://github.com/AMANEQ-official/StrLrTdc-10G), [MikuClockHub](https://github.com/AMANEQ-official/MikuClockHub), [MznStrHrTdc](https://github.com/AMANEQ-official/MznStrHrTdc), [AMANEQ-Skeleton](https://github.com/spadi-alliance/AMANEQ-Skeleton).

See [FOR_DEVELOPERS.md](FOR_DEVELOPERS.md) for architecture, testing and the distinction between measured hardware results and implementation assumptions. [AGENTS.md](AGENTS.md) records constraints for future changes.

```bash
python3 -m unittest test_amaneq_firmware_programer -v
```
