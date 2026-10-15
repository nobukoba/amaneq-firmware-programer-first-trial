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

The explicit setup-windows-wsl.ps1 host installer may install usbipd-win and WSL apt packages when Setup is requested. Attach/Detach require BUSID; never automatically choose a cable, flash or reboot. This authorization is scoped to explicit setup, not normal Python execution. Distinguish parser/mock checks from an actual host installation test.

## Explicit native Windows desktop USB operations

The user explicitly requested in-app driver switching in addition to the earlier WSL deployment. amaneq-firmware-app.py is a desktop UI, not another general CLI wrapper. windows_usb.py is used only after an explicit USB button and confirmation; ordinary CLI/programming must never switch drivers. Elevate only the driver worker with UAC. Support native Windows x64 HS3/FT232H, require physical HS3 confirmation and exactly one connected FT232H during driver changes, and recheck identity immediately before mutation. VID/PID is not proof of model.

Export the original FTDIBUS OEM package using pnputil before WinUSB. Preserve and hash all backup files under LOCALAPPDATA/AMANEQ/usb-drivers; never overwrite an original backup or restore from missing/modified/wrong-device files. libwdi calls must match the official v1.5.1 ABI. Keep catalog/signature checks enabled. Restore through UpdateDriverForPlugAndPlayDevicesW with the backed-up INF, not a global pnputil delete/uninstall. Package matching can affect other FT232H instances; do not promise isolation by serial. No blind retries or automatic restore after failed writes. Verify the observed driver after each operation and retain error/result information.

The local build uses unmodified libwdi v1.5.1 commit 9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602 and WDK 8 redistributable coinstallers from https://go.microsoft.com/fwlink/p/?LinkID=253170. Cross-build with MinGW x64, CC_FOR_BUILD=gcc, --disable-32bit and --with-wdkdir pointing at the extracted Windows Kits/8.0 prefix. WinUSB resources and current device identity were read-only checked. Driver replacement/restoration in the new app remains physically unverified. The previous direct Zadig/FTDI restoration observations do not prove this backend.

Build locally with Python and PyInstaller using build-windows-app.py --help. It accepts explicit UCRT64, libwdi DLL/source and Cygwin-bin inputs, includes the matching libwdi source/license, and produces an onedir EXE plus ZIP. Do not publish local backups, matching source with local build logs, or workstation paths. Keep third-party notices and review distribution terms for bundled dependencies before external binary distribution. Source publishing and local executable tests do not authorize changing a connected device.

## macOS application bundles

build-macos-app.py must run natively on macOS. Build Apple Silicon arm64 and Intel x86_64 separately with the matching Python architecture. macos-app.yml targets macos-15 and macos-15-intel. Include openFPGALoader as a PyInstaller binary so its dylib dependencies are collected and relocated; audit Mach-O links and fail on non-system absolute dependencies. Bundle the uncompressed XC7K160T SPI bridge. Ship verified source archives, notices and Homebrew recipes for openFPGALoader/libftdi/libusb; do not silently accept source/version/checksum mismatches.

Do not write inside an installed .app or create __pycache__ there. Desktop CLI children use an application-data ROOT and restore standard streams if windowed mode started with None. macOS data is ~/Library/Application Support/AMANEQ. The physical HS3 checkbox is shared across tabs; Windows USB mutation controls stay disabled on macOS. Ad-hoc signature validation, GUI startup, loader/list/scan checks and dependency auditing are build checks, not hardware programming evidence. Apple Developer ID signing/notarization is not configured. Preserve application symlinks, modes and resource forks using ditto for ZIP packaging. Artifact retention is 30 days; success does not imply a permanent Release download.

## Desktop 0.2 corrections

The user requires a single window, startup cable scanning, startup latest-image list and a selectable Ethernet adapter. Never reintroduce an empty Windows tab on Mac. Automatically select only a single discovered cable; multiple devices require explicit serial selection. Catalog rows are pinned to their displayed commit/path, with five-minute caching and explicit stale/offline labeling. Startup reads must not mutate USB drivers, network addresses or flash.

macos_network.py adds a temporary IPv4 alias only after explicit confirmation and administrator authorization. Preserve DHCP/DNS/gateway configuration; never replace network services or auto-pick a PC address. Validate Ethernet identity, host address, mask and other-interface overlap. Do not adopt/remove a pre-existing address. Store a user-owned nonce lease outside the app; the privileged helper accepts only narrowly validated interface/address operations and reads records in the expected per-user directory. The guardian watches parent process identity and release requests, removing only its matching alias. Roll back if the guardian cannot start. Report cleanup failures; a reboot clears the nonpersistent alias. Actual user-adapter mutations are not covered by mocks. JTAG programming does not require Ethernet setup.

Bundle certifi CA data and its license on macOS, selecting SSL_CERT_FILE only when the user did not override it. Never disable TLS verification. Ad-hoc signing still requires initial macOS user approval and is not notarization. Current Mac builds publish versioned Release assets after both architectures succeed; Actions artifacts remain an intermediate transport. Avoid pointing users only to Actions or expired temporary links.
