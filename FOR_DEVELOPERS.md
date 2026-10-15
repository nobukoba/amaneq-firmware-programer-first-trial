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

All board targets share that FPGA identity. Filename target/family evidence is checked when recognized; arbitrary renaming removes that evidence and does not prove a board revision. The physical target remains user intent, not automatic hardware identity. All supported families permit temporary SRAM BIT loading and persistent MCS programming.

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

The latest user request supersedes the 0.2 single-page layout with three tabs beneath shared board selection; keep startup scanning, latest images and selectable Ethernet. Never reintroduce an empty Windows tab on Mac. Automatically select only a single discovered cable; multiple devices require explicit serial selection. Catalog rows are pinned to their displayed commit/path, with five-minute caching and explicit stale/offline labeling. Startup reads must not mutate USB drivers, network addresses or flash.

macos_network.py adds a temporary IPv4 alias only after explicit confirmation and administrator authorization. Preserve DHCP/DNS/gateway configuration; never replace network services. The user now specifies editable host default 192.168.10.20/24; application remains explicit. Validate Ethernet identity, host address, mask and other-interface overlap. Do not adopt/remove a pre-existing address. Store a user-owned nonce lease outside the app; the privileged helper accepts only narrowly validated interface/address operations and reads records in the expected per-user directory. The guardian watches parent process identity and release requests, removing only its matching alias. Roll back if the guardian cannot start. Report cleanup failures; a reboot clears the nonpersistent alias. Actual user-adapter mutations are not covered by mocks. JTAG programming does not require Ethernet setup.

Bundle certifi CA data and its license on macOS, selecting SSL_CERT_FILE only when the user did not override it. Never disable TLS verification. Ad-hoc signing still requires initial macOS user approval and is not notarization. Current Mac builds publish versioned Release assets after both architectures succeed; Actions artifacts remain an intermediate transport. Avoid pointing users only to Actions or expired temporary links.

## Desktop 0.3 superseding workflow

Use AMANEQ/CIRASAME/STAG selection above Firmware, set_cdce62002 and MPC/MPCX/IP tabs. CIRASAME spelling was accepted. Both network tabs share selectable Ethernet and editable host 192.168.10.20/24; MPCX target .10, MPC .16, Custom editable. Selecting tabs/presets never applies settings. Update the connection only after verified runtime-IP success.

Clock source: spadi-alliance/hul-common-lib commit 65476509aa401aad10148ec7c2d2a50ba7d2db3e, CDCE62002RegMap.hh/CDCE62002Funcs.cc/FPGAModule.cc. Preserve reversed SPI words and little-endian byte lanes spaced 0x10000, not contiguous. TX B0000000; RX B0100000; write B1000000; read B2000000. Read back registers 0/1 before optional EEPROM copy 0x1F (on by default as upstream). No power-cycle persistence claim. CIRASAME manual hardware/cirasame/cirasame.md identifies XC7K160T/FFG676 and S25FL128S; practical/practical.md specifies in_125_out_500_125. Isolate CIRASAME firmware repositories from AMANEQ. STAG maps are unknown: stop firmware/clock writes rather than guessing.

SiTCP helpers are pinned, unmodified user-repository source; vendor/sitcp-utility/UPSTREAM.json records provenance. build-network-tools.py compiles native Linux/WSL/macOS binaries; the Mac build bundles three under runtime/network/bin plus matching source. Preserve generation checks, 500 ms write settling, readback and upstream error exits. No automatic Clear/reset/write retry. Native Windows network commands are unsupported. Temporary alias automation is macOS-only; Linux/WSL host Ethernet needs manual configuration. Keep compiled vendor binaries/proprietary license files out of Git. New GUI hardware writes remain unverified.

## Desktop 0.4 simplified selection

Superseding user request: no Device mode in clock tab. Each network tab has literal Target IP presets .10/.16/Custom. License/IP order is file selection, detected MPC/MPCX contents, Target IP, then optional temporary host controls. Enable only reveals controls; explicit Apply changes the host. Default disabled/hidden. Unchecking an active alias must restore it, and failure must leave controls visible. Clock EEPROM checkbox is labeled Save clock settings for the next power-on; it refers only to CDCE62002 clock persistence.

Firmware uses automatic cable/model discovery (retain multi-cable/unknown-model guards), selected Target+Firmware filtering, newest-first list/automatic first selection, editable per-profile GitHub repository URL, explicit GitHub/Local source selection and ONE large Program image button. No Loader field or separate latest-MCS button. Repository/target/family changes invalidate selection immediately; ignore stale async completions and validate selected-row provenance again before programming. Cache acquisition by repository/target/family and use unique temporary cache filenames for concurrent readers. Default-branch file list is at most ten rows; historical CLI behavior remains unchanged.

## Desktop 0.5 tab order and classifier correction

Latest order: Firmware, MPC / MPCX, IP, Jitter Cleaner. IP-only read/write is a separate tab with its own Target IP; license writes no longer carry IP options. Bundle sitcp-sitcpxg-ip-reader as a fourth native helper. All three network tabs share opt-in temporary host setup. Target IP is ONE row (label, preset/custom address, Ping, result), no mask/UDP metadata. Ping is asynchronous, two requests, bounded 8 s total; macOS -W is milliseconds, Linux -W seconds. Prevent duplicate pings per field and ignore stale endpoint results. ICMP response is not an RBCP validity test.

Critical classifier fix: upstream type 2, tag offset 6 / delta 0x34, is normal SiTCP MPC; type 1, offset 0 / delta 0x2C, is SiTCP-XG MPCX. Preserve upstream classifier precedence (normal/type 2 tested first); the previous Python labels were reversed. Add regression tests with checked-in official_mpc_erased and official_mpcx_erased synthetic payloads. MPC maps to target .16, MPCX to .10; do not infer from filename extensions or alter the validated C++ writer.

## Desktop 0.6 historical firmware

The GUI must include replaced/deleted historical firmware, not only files still in the default branch. Start with the default branch, traverse tags and commits affecting the selected mcs or bit directory, and pin each row to its source commit/path. Deduplicate by format/path/Git blob SHA, preserving distinct contents with the same filename. Default History limit is 10 total images, editable 1..1000. Current-branch images remain first, newest semantic hexadecimal version selected; historical rows include tag/date/commit identity. Cache keys include history mode/limit and retain explicit stale/incomplete labels. Traverse at most min(1000,max(20,limit*3)) commits per firmware directory plus bounded tags; report API/rate-limit failures rather than claiming a complete history. CLI history behavior is unchanged. A live read-only official StrLrTdc v4 query recovered v2.A, v2.9, v2.8.1, v2.8 and earlier files; no programming was performed.

## Desktop 0.7 format and path controls

Add explicit Format selection, filtering BEFORE history traversal/limits and including format in the cache identity. All supported families offer MCS and BIT. HR-TDC mezzanine has fixed hrtdc firmware and hides both the redundant label and selector; restore them when leaving that target. Keep one Program image button. Local selected-format/content checking runs outside the Tk thread before programming. MPC/MPCX file is one row, with read-only horizontally scrollable path. Bind wheel and read-only navigation; do not override ordinary caret navigation in editable URL entries. GUI smoke checks cover format transition, hidden/restored selectors and a very long path.

Desktop 0.8: keep New device IP label/input/runtime checkbox on one row. Exact labels: Change current (runtime) IP instead of saved EEPROM IP; Temporary static host IP address (DHCP preserved, restored on exit). Behavior is unchanged.

Desktop 0.9: frequency label and preset share one row. The clock action label is Apply. Use the shared Action.TButton style for Program image, Write MPC/MPCX, Write IP and Apply: default button font size/padding, bold weight only. Do not stretch Program image across the page or enlarge it.

Desktop 0.10: the user clarified history means earlier messages, not navigation history. Preserve all current-run log text and pause automatic see(end) when wheel/scrollbar/history keys are used. First/Latest and Follow latest control the viewport; new queued output must not snap an old viewport to the end. Messages is a vertical Panedwindow pane with a draggable sash and no Expand button. Window resizing is explicit, minimum 720x480; UI size scales existing named fonts and the shared bold-action font from immutable base sizes. Tab changes schedule idle/25ms layout and Expose for mapped scrollable canvases, with Map hooks to size previously hidden embedded frames. Do not claim the user-reported Mac repaint issue is visually verified merely from startup tests. No navigation-state history was requested.

Desktop 0.11: remove implementation-specific HUL register-map prose from normal clock UI. Exact label: Select input / output frequencies of CDCE62002 chip (MHz):. Preserve the conditional STAG unsupported notice and chip spelling CDCE62002. Previous tab-order request repeated Jitter Cleaner; absent clarification, interpret the final duplicate as IP, yielding Firmware / Jitter Cleaner / MPC/MPCX / IP, and state that assumption. HUL means Hadron Universal Logic per https://hul-official.gitlab.io/hul-ug-en/hardware/main/; keep library provenance in developer documentation rather than routine product controls.

Desktop 0.12: Target IP presets display 192.168.10.16 (SiTCP default) and 192.168.10.10 (SiTCP-XG default). These labels are presentation only: use the bare validated IPv4 address for Ping/RBCP and restore the correct label when selecting a detected MPC/MPCX file. Custom remains available.

Desktop 0.13 firmware display names: lrtdc → LR-TDC; hrtdc → HR-TDC; lrtdc-10g → LR-TDC 10GbE; mikumari → MIKUMARI Hub; skeleton → Skelton (user-requested spelling). This is a UI mapping only. CLI options, repository paths, artifact filenames, cache identities keep their existing internal identifiers.

Desktop 0.14 supersedes the former Skeleton-only BIT restriction: all supported firmware families offer MCS / BIT, with existing FPGA/target/cable checks retained. BIT loads SRAM temporarily; MCS writes persistent flash. Remove Messages Expand/Restore; resize the log by dragging its divider. MPC/MPCX path caret movement (Left/Right, Home/End or clicking) reveals that position horizontally. Keep the temporary-IP enable checkbox on one line with the exact text Temporary static host IP address (DHCP preserved, restored on exit), without a duplicate frame heading. Remove the explanatory line below Write IP. These UI checks do not perform hardware writes or host-IP changes.

Desktop 0.14.1 displays firmware formats as .mcs file and .bit file in the selector and image list. Map these labels explicitly to internal mcs/bit values; preserve CLI options, content validation and programming behavior.

Desktop 0.14.2 restores format labels BIT / MCS. Strip the .bit / .mcs extension before hexadecimal version parsing: v2.A.bit means v2.A, not v2.A.B; preserve real third components such as v2.A.B.bit. Invalidate cached image sorting. Under temporary host IP, show NIC:, adapter selection, Refresh, Host IP: and Mask: on one row; explicit Apply/Restore remain below.

Desktop 0.14.4: place Cable (automatically detected), the cable selector and Rescan on one row, using an inline label instead of a group heading. Retain scan details and the conditional physical HS3 confirmation below; preserve multiple-cable serial and model guards.

Desktop 0.14.5: MPC/MPCX paths accept typing and paste, including quoted paths and ~ expansion. Debounced/Enter/focus-out content detection updates the file type and default target once per changed valid file; invalid input stays visible inline and blocks file-based writes. Keep the chooser and horizontal caret scrolling. Messages has a visible 12-pixel drag bar with a vertical resize cursor and explicit mouse handlers using root coordinates, independent of the native ttk sash hit area. Verify actual synthetic press/motion/release and increased log height, not only sashpos calls. Preserve log history and do not reintroduce Expand.

Desktop 0.14.6: Image source comes first in Firmware. GitHub list reveals Target / Firmware / Format followed by repository/history controls and image list. Local file hides these GitHub filters and retains its own explicit Target selector: infer format from validated file contents and recognized firmware family from filename, never silently infer board revision from FPGA ID. Shared cable controls follow the source-specific area before Program image. Switching source preserves selections and cancels stale catalog results.

Desktop 0.14.7 supersedes local Target selection: Local file has only file selection; infer target and family from recognized official filenames and format from validated contents. Reject unidentified or cross-board filenames before programming. The documented common AMANEQ Skelton image uses a compatible v1/v4 profile, without claiming that JTAG identifies the board revision. GitHub controls remain unchanged. Exact cable label: Cable (automatically detected):.

Desktop 0.15: shorten the CDCE62002 preset selector to 20 characters and remove Files are validated prose. Rename the IP tab IP addr.; use EEPROM IP / Current IP radio buttons sharing the existing boolean backend, EEPROM default. Add colons to field labels (not action buttons or tab names). Serialize firmware list acquisition and cancel superseded refresh timers; ignore stale errors. Cache GitHub metadata across profiles/formats (mutable 5 minutes, immutable commit metadata 24 hours); explicit refresh bypasses mutable cache. Stop requests on HTTP 403/429 until Retry-After / primary reset or at least 60 seconds; do not auto-retry. Keep stale catalog labels truthful. Optional masked GitHub token is session-only, never saved/logged or passed in argv; use it for API metadata and only the firmware child environment. Clear to return to inherited GITHUB_TOKEN / unauthenticated access. Open GitHub provides browser/manual download then Local file as a fallback. A 403 can mean permission denial, not just rate limiting; actual recovery on the user's network is not proven by mocks. GitHub rate-limit reference: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api.
