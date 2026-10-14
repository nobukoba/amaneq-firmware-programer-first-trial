# AGENTS.md

**Language: English | [日本語](AGENTS.ja.md)**

## Purpose and public interface

Maintain a small Python 3.10+ firmware acquisition/programming tool that calls openFPGALoader. This is not an AMANEQ register configurator or a SiTCP license writer. Use only Python standard-library dependencies at runtime unless the user requests otherwise.

Preserve the requested spelling and names:

- `amaneq-firmware-programer.py`, with `#!/usr/bin/env python3`, UTF-8 without BOM and LF endings.
- Subcommands `scan`, `inspect`, `local`, `versions`, `download`, `program`, `wizard`.
- `program-latest-mcs-amaneq-*` shortcuts for all supported families.
- `program-latest-bit-amaneq-v4-skeleton` as the only BIT shortcut.
- `firmware-latest-amaneq-common.sh` / `.cmd` as shared helpers.

Skeleton permits BIT and MCS. Other families permit MCS only, including local and direct-URL inputs. Mikumari means MikuClockHub. Do not silently reintroduce other BIT shortcuts or rename `programer` to `programmer`.

All source, comments, CLI help, prompts and error messages must be English. User documentation must have synchronized English/Japanese versions with identical command examples and language navigation. Every defaulted option must show its actual default in `--help`.

## Read before editing documentation

Follow Nobuyuki Kobayashi's [README style](https://github.com/nobukoba/nobuyuki-kobayashi-instructions-for-ai/blob/main/styles/nobuyuki-kobayashi-github-readme.md) and [CLI tool preferences](https://github.com/nobukoba/nobuyuki-kobayashi-instructions-for-ai/blob/main/styles/nobuyuki-kobayashi-cli-tools.md).

Use the SiTCP writer's practical order: purpose, quick installation, actual writer commands, reader/inspection commands, then an appendix. Adapt paths to this Python repository; do not invent a Makefile or `./bin/` installation. Keep technical algorithms/evidence in `FOR_DEVELOPERS.md`, not at the beginning of README. Preserve user-visible setup requirements and failure behavior.

## Target and cable selection

- Multiple connected candidate cables without `--serial`: print serial numbers and stop with exit 1 before firmware choice, downloading, JTAG initialization or programming. No interactive cable-selection menu, with or without `--yes`.
- Duplicate matching serials must also stop. Never default to the first of several devices.
- `0403:6014` is shared by HS3/HS2/other FT232H devices. Require model evidence, explicit `--cable hs3`, or a user-supplied known serial. Do not hardcode workstation serials in public code.
- AMANEQ v1/v4 and HR-TDC mezzanine share XC7K160T. JTAG ID cannot prove revision or board role. Require explicit target/intent and validate exactly one matching device.
- Skeleton v1/v4 common files are expressly documented by the DAQ manual; do not apply this exception to other families or mezzanines.
- Never modify USB drivers, user PATH, `.py` associations or system settings automatically. Python invocation is cross-platform; shebang direct execution is POSIX behavior.

## Flash programming

- Decode and validate file contents, not extensions. Check MCS record lengths/checksums/EOF/overlap and BIT header/FPGA identity. Pass the detected format explicitly to openFPGALoader.
- Pin GitHub downloads to a resolved commit; verify file size and Git blob hash. Direct URLs require validated firmware; optional expected SHA256 must match before saving/programming. Never treat HTML as firmware.
- `latest` means the newest matching named image in the default branch; it does not mean the most recent Release tag. Versions in these repositories use hexadecimal components such as `v2.A`.
- History defaults to 10 total choices, including current branch; deduplicate tag/commit identities and honor `--history-limit` up to 1000.
- For automatic GitHub MCS mezzanine programming, probe before selecting/downloading the variant. The probe loads an SPI bridge into SRAM and interrupts the prior FPGA application, but does not erase flash.
- Validate JEDEC ID, model alias, capacity and target. Recheck before erase. MT25QU256 may appear as N25Q256A; JEDEC `20bb19` and 32 MiB are the verified source-level signature mapping. Old N25Q128 uses a 16 MiB variant. Unknown/contradictory parts must stop.
- Back up the full flash before programming. Verify the complete MCS image using an independent flash dump and byte comparison. The tested Windows build's `--verify` did not implement this mode; do not assume exit 0 proves verification.
- No automatic destructive-write retries, reset/power control, license EEPROM modification or driver changes. Preserve backups on failures.
- Byte equality is not proof of power-cycle boot, network access, DAQ validity or license compatibility. Never report those as tested without evidence.

## Runtime/platform boundary

Windows FTDI/WinUSB setup, Linux USB permissions, WSL usbipd and container USB exposure are host requirements, not solved by bundling a binary. Keep capability detection tied to the chosen executable's `--list-cables` output. The tested Windows build lacks Xilinx Platform Cable support. The upstream Xilinx adapter path does not accept unique bus/serial selection, so the Linux path requires exactly one Xilinx candidate; its physical behavior remains unverified.

Target Windows WSL2, native Linux and native macOS. macOS parses ioreg plist output and selects FTDI by serial; Linux/WSL uses sysfs and bus/device. WSL requires usbipd-win forwarding and Linux USB permissions. macOS enumeration is mock-tested; programming on all three environments remains physically unverified. Native Windows code/evidence is retained as legacy support.

## Verification and publication

Run offline tests and inspect both language documents after changes:

```bash
python3 -m unittest test_amaneq_firmware_programer -v
python3 amaneq-firmware-programer.py --help
```

Use synthetic fixtures in tracked tests. Keep actual firmware, flash dumps, credentials, proprietary MPC/MPCX license files, USB driver backups and local runtimes out of Git. Never execute a programming shortcut as a test without a separate current authorization to modify the connected hardware. `--help` is a safe launcher check.

Keep source readable: normal blocks, descriptive names, no compressed multiple statements. Preserve comments and guards during formatting. Keep executable Git modes for `.py` and `.sh`, and CRLF checkout settings for `.cmd`.

Maintain `README.md`, `README.ja.md`, `FOR_DEVELOPERS.md`, `FOR_DEVELOPERS.ja.md`, and both AGENTS documents together. Update the user-authorized AI instruction repository with durable corrections and project-specific facts; do not turn one project's facts into universal rules.
