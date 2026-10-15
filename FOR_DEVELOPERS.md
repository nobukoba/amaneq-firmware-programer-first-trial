# Developer notes

**Language: English | [日本語](FOR_DEVELOPERS.ja.md)**

## Layout and runtime

`amaneq-firmware-programer.py` is the only main Python entry point. The hyphenated filename is deliberate. Tests load it with importlib and register the module before executing dataclass declarations. Shortcuts are thin argument presets; shared helpers select Python and invoke the same `program` implementation. No second programming implementation exists.

Runtime: Python 3.10+ standard library and an external openFPGALoader executable. Linux discovery checks PATH; Windows can use `--loader`, a locally provided `installed/ucrt64` layout, or PATH. SPI bridge search checks the repository's optional installation, the executable's installation prefix, `/usr/share/openFPGALoader`, and `/usr/local/share/openFPGALoader`; `--bridge` overrides it. The binary and bridge are third-party resources, not tracked here.

Windows scripts honor AMANEQ_PYTHON, otherwise py -3 then python. The Python program searches cygpath via PATH, AMANEQ_CYGPATH_DIR, an explicit --cygpath-dir, Git for Windows, or an optional local tools directory. Do not embed one workstation's dependency directory. AMANEQ_HS3_SERIALS is an optional comma-separated list of user-confirmed HS3 serials.

## Acquisition and history

Firmware defaults map LRTDC/HRTDC/LRTDC-10G/Mikumari/mezzanine to the AMANEQ-official repositories; Skeleton maps to spadi-alliance/AMANEQ-Skeleton. Generic Skeleton filenames are permitted for v1/v4 only because the DAQ manual expressly documents that compatibility.

Resolve branch/tag/SHA to a commit before listing its tree and fetching raw content. Check size and SHA1 of the Git blob framing (`blob <length>\0` plus bytes), then inspect the firmware. Save SHA256 and provenance. Raw URL mode has no Git identity guarantee unless the user supplies an expected SHA256; content validation still applies.

Version components use hexadecimal ordering in these upstream filenames. Latest selection is by matching filename version in the default branch; tags can lag current firmware. Historical choices combine tags and commits, sort by commit date, and cap the total including current branch. Annotated-tag edge cases and very large histories should be checked against actual API responses if behavior is extended.

Network reads have an inactivity timeout, response-size caps and Content-Length checks. English errors distinguish DNS/offline, timeout, HTTP statuses, TLS, interrupted transfer, invalid JSON/HTML and hash/format errors. No destructive retry follows a communication failure.

## Target/file validation

A BIT header provides part/package, design, date/time, and configuration payload. Intel HEX parsing checks records, checksums, extended addresses, EOF, overlap and the 32 MiB maximum decoded image. The configuration sync word and IDCODE packet identify the FPGA; revision bits are masked for comparison. The allowed device is XC7K160T, matching 0x0364c093 after masking.

All board targets share that FPGA identity. Filename target/family evidence is checked when recognized; arbitrary renaming removes that evidence and does not prove a board revision. The physical target remains user intent, not automatic hardware identity. Skeleton BIT only; other families' BIT files are intentionally rejected even if technically loadable.

## Programming sequence

1. Enumerate/select cable before file choice or download. Multiple candidates without serial stop and list their serials; model-ambiguous FT232H requires an explicit declaration/evidence.
2. Automatic GitHub MCS mezzanine path probes the flash first and uses the detected variant to filter downloadable files. That probe changes SRAM only.
3. Validate selected/downloaded file, family, target, FPGA part and one-device JTAG chain.
4. BIT: invoke SRAM loading and require observed DONE=1.
5. MCS: load the SPI bridge, read JEDEC/model/capacity, validate target and recheck the selected variant, dump the complete flash to a backup, program, dump the image-length range, compare every byte, write result JSON.

MCS sparse holes are represented as FF in the comparison image. Full backup size must match capacity before erase. Failed reports preserve paths and error text; no automatic recovery write or destructive retry is attempted. Users must manually power-cycle/check boot after flash programming; the SPI bridge can remain in SRAM.

Flash signatures: 012018 -> S25FL128S/16MiB; 20bb19 -> 256Mbit Micron family used for MT25QU256/32MiB; 20bb18/20ba18 -> N25Q128-family/16MiB. MT25/N25Q aliases cannot establish an exact marketing part number beyond the shared JEDEC family signature. A contradictory model/capacity stops before erase. These mappings are source/documentation evidence; neither mezzanine variant has been physically exercised here.

## USB and platform limits

HS3 VID/PID 0403:6014 overlaps HS2 and other FT232H devices. Linux enumeration uses sysfs serial/bus/device/product fields; Windows uses a fixed read-only PnP query. No user input is interpolated into that PowerShell query. Linux FTDI selection uses bus/device; Windows FTDI selection uses serial. Xilinx candidates use known 03fd Platform Cable product IDs and the chosen binary's cable list. The upstream Xilinx constructor does not receive bus/serial, so do not claim unique selection among several Xilinx cables.

Target Windows WSL2, native Linux and native macOS. macOS parses ioreg plist output and selects FTDI by serial; Linux/WSL uses sysfs and bus/device. WSL requires usbipd-win forwarding and Linux USB permissions. macOS enumeration is mock-tested; programming on all three environments remains physically unverified. Native Windows code/evidence is retained as legacy support.

## Physical evidence: 2026-10-14

On the local Windows machine, direct openFPGALoader v1.1.1 calls with an HS3 reached XC7K160T after switching FTDIBUS to WinUSB. Before the switch, USB opening failed with -4. BIT SRAM loading reached DONE=1. MCS programming recognized S25FL128S (JEDEC 012018) and completed.

The same run printed `Verify not supported in this mode` despite exit 0. A separate flash dump matched all 6,692,572 MCS payload bytes. Payload SHA256: `15c99849279621b90f74c9ffac898fe234698204b7c51a1e5a09aac068bfa32b`. The MCS file SHA256: `8d7d8029b183090b16364dd1668e3d6c04523a0384318dc25180929ca47ea9f2`.

The Windows bridge-loading path needed cygpath. A JTAG reset attempt did not establish flash boot: DONE remained 0. Reloading the matching BIT restored DONE=1. This does not establish successful persistent boot. The final Python orchestration, full-backup sequence, both mezzanine variants, Linux, macOS programming and containers were not physically verified. Later tests use mocks and synthetic fixtures; do not describe them as hardware tests.

No proprietary SiTCP licenses, actual flash backups, packet captures or third-party binaries are included. SiTCP and SiTCP-XG licenses remain a separate EEPROM concern.

## Tests and maintenance

```bash
python3 -m unittest test_amaneq_firmware_programer -v
python3 -m compileall -q amaneq-firmware-programer.py test_amaneq_firmware_programer.py
```

The tracked suite is offline and self-contained: synthetic BIT/MCS parsing, checksum/EOF/overlap rejection, content-vs-extension, serial/ambiguity stops, flash backup/write/readback ordering, mismatch failure, network errors, direct URL validation, history ordering/limits, Skeleton compatibility and mezzanine pre-download selection. The initial public import has 36 tests. A passing mock is not proof of physical behavior.

GitHub Actions runs the same offline tests on Ubuntu, Windows and macOS with Python 3.10/3.12. A green macOS test runner does not mean macOS USB programming is implemented. Inspect shortcut --help, not their normal programming operation, during routine validation.

Use Black with the repository configuration for readable formatting. Keep code/comments/errors English and bilingual examples synchronized. Preserve shebang, LF script data, executable Git modes, and CRLF Windows checkouts. Do not publish firmware/cache/log directories. Review secret/host-path exclusions before pushing.

The explicit setup-windows-wsl.ps1 host installer may install usbipd-win and WSL apt packages when Setup is requested. Attach/Detach require BUSID; never automatically choose a cable, flash or reboot. This authorization is scoped to explicit setup, not normal Python execution. Distinguish parser/mock checks from an actual host installation test.

## Explicit native Windows desktop USB operations

The user explicitly requested in-app driver switching in addition to the earlier WSL deployment. amaneq-firmware-app.py is a desktop UI, not another general CLI wrapper. windows_usb.py is used only after an explicit USB button and confirmation; ordinary CLI/programming must never switch drivers. Elevate only the driver worker with UAC. Support native Windows x64 HS3/FT232H, require physical HS3 confirmation and exactly one connected FT232H during driver changes, and recheck identity immediately before mutation. VID/PID is not proof of model.

Export the original FTDIBUS OEM package using pnputil before WinUSB. Preserve and hash all backup files under LOCALAPPDATA/AMANEQ/usb-drivers; never overwrite an original backup or restore from missing/modified/wrong-device files. libwdi calls must match the official v1.5.1 ABI. Keep catalog/signature checks enabled. Restore through UpdateDriverForPlugAndPlayDevicesW with the backed-up INF, not a global pnputil delete/uninstall. Package matching can affect other FT232H instances; do not promise isolation by serial. No blind retries or automatic restore after failed writes. Verify the observed driver after each operation and retain error/result information.

The local build uses unmodified libwdi v1.5.1 commit 9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602 and WDK 8 redistributable coinstallers from https://go.microsoft.com/fwlink/p/?LinkID=253170. Cross-build with MinGW x64, CC_FOR_BUILD=gcc, --disable-32bit and --with-wdkdir pointing at the extracted Windows Kits/8.0 prefix. WinUSB resources and current device identity were read-only checked. Driver replacement/restoration in the new app remains physically unverified. The previous direct Zadig/FTDI restoration observations do not prove this backend.

Build locally with Python and PyInstaller using build-windows-app.py --help. It accepts explicit UCRT64, libwdi DLL/source and Cygwin-bin inputs, includes the matching libwdi source/license, and produces an onedir EXE plus ZIP. Do not publish local backups, matching source with local build logs, or workstation paths. Keep third-party notices and review distribution terms for bundled dependencies before external binary distribution. Source publishing and local executable tests do not authorize changing a connected device.

## macOS application bundles

build-macos-app.py must run natively on macOS. Build Apple Silicon arm64 and Intel x86_64 separately with the matching Python architecture. macos-app.yml targets macos-15 and macos-15-intel. Include openFPGALoader as a PyInstaller binary so its dylib dependencies are collected and relocated; audit Mach-O links and fail on non-system absolute dependencies. Bundle the uncompressed XC7K160T SPI bridge. Ship verified source archives, notices and Homebrew recipes for openFPGALoader/libftdi/libusb; do not silently accept source/version/checksum mismatches.

Do not write inside an installed .app or create __pycache__ there. Desktop CLI children use an application-data ROOT and restore standard streams if windowed mode started with None. macOS data is ~/Library/Application Support/AMANEQ. The physical HS3 checkbox is shared across tabs; Windows USB mutation controls stay disabled on macOS. Ad-hoc signature validation, GUI startup, loader/list/scan checks and dependency auditing are build checks, not hardware programming evidence. Apple Developer ID signing/notarization is not configured. Preserve application symlinks, modes and resource forks using ditto for ZIP packaging. Artifact retention is 30 days; success does not imply a permanent Release download.

On 2026-10-15, Actions run 38740982476 passed both arm64 and x86_64 builds, signature/dependency auditing, GUI startup, bundled loader execution and scan without attached hardware. All 47 offline tests and the six normal CI configurations passed. Physical HS3 programming remains unverified.

## Desktop 0.2 corrections

The user requires a single window, startup cable scanning, startup latest-image list and a selectable Ethernet adapter. Never reintroduce an empty Windows tab on Mac. Automatically select only a single discovered cable; multiple devices require explicit serial selection. Catalog rows are pinned to their displayed commit/path, with five-minute caching and explicit stale/offline labeling. Startup reads must not mutate USB drivers, network addresses or flash.

macos_network.py adds a temporary IPv4 alias only after explicit confirmation and administrator authorization. Preserve DHCP/DNS/gateway configuration; never replace network services or auto-pick a PC address. Validate Ethernet identity, host address, mask and other-interface overlap. Do not adopt/remove a pre-existing address. Store a user-owned nonce lease outside the app; the privileged helper accepts only narrowly validated interface/address operations and reads records in the expected per-user directory. The guardian watches parent process identity and release requests, removing only its matching alias. Roll back if the guardian cannot start. Report cleanup failures; a reboot clears the nonpersistent alias. Actual user-adapter mutations are not covered by mocks. JTAG programming does not require Ethernet setup.

Bundle certifi CA data and its license on macOS, selecting SSL_CERT_FILE only when the user did not override it. Never disable TLS verification. Ad-hoc signing still requires initial macOS user approval and is not notarization. Current Mac builds publish versioned Release assets after both architectures succeed; Actions artifacts remain an intermediate transport. Avoid pointing users only to Actions or expired temporary links.
