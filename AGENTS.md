# AGENTS.md

**Language: English | [日本語](AGENTS.ja.md)**

## Current handoff

Read [HANDOFF.md](HANDOFF.md) first when resuming in another chat. Its Windows D2XX and measured MCS results supersede historical WSL/WinUSB-only assumptions.

## Purpose and public interface

Maintain a small Python 3.10+ firmware acquisition/programming tool that calls openFPGALoader. The firmware CLI stays scoped to flashing; the user-requested desktop also configures CDCE62002 and SiTCP MPC/MPCX/IP. Use only Python standard-library dependencies at runtime unless the user requests otherwise.

Preserve the requested spelling and names:

- `amaneq-firmware-programer.py`, with `#!/usr/bin/env python3`, UTF-8 without BOM and LF endings.
- Subcommands `scan`, `inspect`, `local`, `versions`, `download`, `program`, `wizard`.
- `program-latest-mcs-amaneq-*` shortcuts for all supported families.
- `program-latest-bit-amaneq-v4-skeleton` as the only BIT shortcut.
- `firmware-latest-amaneq-common.sh` / `.cmd` as shared helpers.

All supported families permit BIT and MCS, including local and direct-URL inputs. Mikumari means MikuClockHub. Do not silently reintroduce other BIT shortcuts or rename `programer` to `programmer`.

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
- History defaults to 5 total choices, including current branch; deduplicate tag/commit identities and honor `--history-limit` up to 1000.
- For automatic GitHub MCS mezzanine programming, probe before selecting/downloading the variant. The probe loads an SPI bridge into SRAM and interrupts the prior FPGA application, but does not erase flash.
- Validate JEDEC ID, model alias, capacity and target. Recheck before erase. MT25QU256 may appear as N25Q256A; JEDEC `20bb19` and 32 MiB are the verified source-level signature mapping. Old N25Q128 uses a 16 MiB variant. Unknown/contradictory parts must stop.
- Back up the full flash before programming. Verify the complete MCS image using an independent flash dump and byte comparison. The tested Windows build's `--verify` did not implement this mode; do not assume exit 0 proves verification.
- No automatic destructive-write retries, reset/power control, license EEPROM modification or driver changes. Preserve backups on failures.
- Byte equality is not proof of power-cycle boot, network access, DAQ validity or license compatibility. Never report those as tested without evidence.

## Runtime/platform boundary

Windows FTDI/WinUSB setup, Linux USB permissions, WSL usbipd and container USB exposure are host requirements, not solved by bundling a binary. Keep capability detection tied to the chosen executable's `--list-cables` output. The tested Windows build lacks Xilinx Platform Cable support. The upstream Xilinx adapter path does not accept unique bus/serial selection, so the Linux path requires exactly one Xilinx candidate; its physical behavior remains unverified.

Target native Windows D2XX desktop, native Linux and native macOS; retain WSL2 as an alternative. macOS parses ioreg plist output and selects FTDI by serial; Linux/WSL uses sysfs and bus/device. WSL requires usbipd-win forwarding and Linux USB permissions. macOS/Linux hardware programming remains unverified. Windows D2XX MCS programming and readback were verified as recorded in HANDOFF.md; older native libusb code remains legacy support.

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

The latest user request supersedes the 0.2 single-page layout with three tabs beneath shared board selection; keep startup scanning, latest images and selectable Ethernet. Never reintroduce an empty Windows tab on Mac. Automatically select only a single discovered cable; multiple devices require explicit serial selection. Catalog rows are pinned to their displayed commit/path, with five-minute caching and explicit stale/offline labeling. Startup reads must not mutate USB drivers, network addresses or flash.

macos_network.py adds a temporary IPv4 alias only after explicit confirmation and administrator authorization. Preserve DHCP/DNS/gateway configuration; never replace network services. The user now specifies editable host default 192.168.10.20/24; application remains explicit. Validate Ethernet identity, host address, mask and other-interface overlap. Do not adopt/remove a pre-existing address. Store a user-owned nonce lease outside the app; the privileged helper accepts only narrowly validated interface/address operations and reads records in the expected per-user directory. The guardian watches parent process identity and release requests, removing only its matching alias. Roll back if the guardian cannot start. Report cleanup failures; a reboot clears the nonpersistent alias. Actual user-adapter mutations are not covered by mocks. JTAG programming does not require Ethernet setup.

Bundle certifi CA data and its license on macOS, selecting SSL_CERT_FILE only when the user did not override it. Never disable TLS verification. Ad-hoc signing still requires initial macOS user approval and is not notarization. Current Mac builds publish versioned Release assets after both architectures succeed; Actions artifacts remain an intermediate transport. Avoid pointing users only to Actions or expired temporary links.

## Desktop 0.3 superseding workflow

Use AMANEQ/CIRASAME/STAG selection above Firmware, set_cdce62002 and MPC/MPCX/IP tabs. CIRASAME spelling was accepted. Both network tabs share selectable Ethernet and editable host 192.168.10.20/24; MPCX target .10, MPC .16, Custom editable. Selecting tabs/presets never applies settings. Update the connection only after verified runtime-IP success.

Clock source: spadi-alliance/hul-common-lib commit 65476509aa401aad10148ec7c2d2a50ba7d2db3e, CDCE62002RegMap.hh/CDCE62002Funcs.cc/FPGAModule.cc. Preserve reversed SPI words and little-endian byte lanes spaced 0x10000, not contiguous. TX B0000000; RX B0100000; write B1000000; read B2000000. Read back registers 0/1 before optional EEPROM copy 0x1F (on by default as upstream). No power-cycle persistence claim. CIRASAME manual hardware/cirasame/cirasame.md identifies XC7K160T/FFG676 and S25FL128S; practical/practical.md specifies in_125_out_500_125. Isolate CIRASAME firmware repositories from AMANEQ. STAG maps are unknown: stop firmware/clock writes rather than guessing.

SiTCP helpers are pinned, unmodified user-repository source; vendor/sitcp-utility/UPSTREAM.json records provenance. build-network-tools.py compiles native Linux/WSL/macOS binaries; the Mac build bundles four under runtime/network/bin plus matching source. Preserve generation checks, 500 ms write settling, readback and upstream error exits. No automatic Clear/reset/write retry. Native Windows desktop bundles now include Cygwin-built network helpers; see the native desktop packaging section. Temporary alias automation is macOS-only; Linux/WSL host Ethernet needs manual configuration. Keep compiled vendor binaries/proprietary license files out of Git. New GUI hardware writes remain unverified.

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

Keep the version in build-macos-app.py and the macos-app.yml Release tag/title synchronized before publishing.

Desktop 0.14.1 displays firmware formats as .mcs file and .bit file in the selector and image list. Map these labels explicitly to internal mcs/bit values; preserve CLI options, content validation and programming behavior.

Desktop 0.14.2 restores format labels BIT / MCS. Strip the .bit / .mcs extension before hexadecimal version parsing: v2.A.bit means v2.A, not v2.A.B; preserve real third components such as v2.A.B.bit. Invalidate cached image sorting. Under temporary host IP, show NIC:, adapter selection, Refresh, Host IP: and Mask: on one row; explicit Apply/Restore remain below.

Desktop 0.14.4: place Cable (automatically detected), the cable selector and Rescan on one row, using an inline label instead of a group heading. Retain scan details and the conditional physical HS3 confirmation below; preserve multiple-cable serial and model guards.

Desktop 0.14.5: MPC/MPCX paths accept typing and paste, including quoted paths and ~ expansion. Debounced/Enter/focus-out content detection updates the file type and default target once per changed valid file; invalid input stays visible inline and blocks file-based writes. Keep the chooser and horizontal caret scrolling. Messages has a visible 12-pixel drag bar with a vertical resize cursor and explicit mouse handlers using root coordinates, independent of the native ttk sash hit area. Verify actual synthetic press/motion/release and increased log height, not only sashpos calls. Preserve log history and do not reintroduce Expand.

Desktop 0.14.6: Image source comes first in Firmware. GitHub list reveals Target / Firmware / Format followed by repository/history controls and image list. Local file hides these GitHub filters and retains its own explicit Target selector: infer format from validated file contents and recognized firmware family from filename, never silently infer board revision from FPGA ID. Shared cable controls follow the source-specific area before Program image. Switching source preserves selections and cancels stale catalog results.

Desktop 0.14.7 supersedes local Target selection: Local file has only file selection; infer target and family from recognized official filenames and format from validated contents. Reject unidentified or cross-board filenames before programming. The documented common AMANEQ Skelton image uses a compatible v1/v4 profile, without claiming that JTAG identifies the board revision. GitHub controls remain unchanged. Exact cable label: JTAG cable:.

Desktop 0.15: shorten the CDCE62002 preset selector to 20 characters and remove Files are validated prose. Rename the IP tab IP addr.; use EEPROM IP / Current IP radio buttons sharing the existing boolean backend, EEPROM default. Add colons to field labels (not action buttons or tab names). Serialize firmware list acquisition and cancel superseded refresh timers; ignore stale errors. Cache GitHub metadata across profiles/formats (mutable 5 minutes, immutable commit metadata 24 hours); explicit refresh bypasses mutable cache. Stop requests on HTTP 403/429 until Retry-After / primary reset or at least 60 seconds; do not auto-retry. Keep stale catalog labels truthful. During access restrictions, wait until the displayed time or download from the repository in a browser and use Local file. A 403 can mean permission denial, not just rate limiting; actual recovery on the user's network is not proven by mocks. GitHub rate-limit reference: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api.

Firmware is vertically scrollable so connection controls, Cable and Program image remain reachable in small windows or enlarged UI. Colons belong to field labels, not tab names.

Desktop 0.15.1 removes the initial Choose Ethernet explanatory row. Temporary-network status rows stay hidden when empty; actual operation results and errors remain visible.

Desktop 0.15.2 fixes the user screenshot with Messages filling the window and macOS USB Invalid file. Use tk.PanedWindow with explicit 180-pixel notebook / 80-pixel Messages minima; initialize the divider only after Map/Configure reports a usable mapped height, once, without resetting user resizing. Startup checks must assert both panes visible BEFORE tests move the divider, plus extreme divider positions and minimum window size. macOS USB enumeration queries ioreg -a -l -p IOUSB, accepts BOM/leading whitespace and valid empty archives, and falls back on malformed/empty/error output to system_profiler. Discover SPUSBHostDataType / SPUSBDataType with -listDataTypes rather than assuming an OS version; validate JSON, preserve serial/model ambiguity guards, and report both backend errors if enumeration fails. A successful parse is not a hardware programming test. Bundled read-only scan remains a required build check, with a 120-second timeout covering the bounded fallback.

Desktop 0.15.3 removes the entire GitHub token row, including its input, Apply and Open GitHub buttons. Keep the editable GitHub URL, Refresh list, caching and rate-limit backoff.

Desktop 0.15.4: default to 5 history choices in GUI and CLI. Preserve History limit / --history-limit overrides (1..1000), caching, deduplication and rate-limit backoff. A smaller list does not guarantee halving API requests.

Desktop 0.15.5: after initial selection, the fourth GitHub category change (Board / Target / Firmware / Format) enforces a 60-second cooldown with a warning and remaining seconds. Block additional list acquisition, including Refresh list, URL and history-limit refreshes, during the pause. Further selection changes do not extend it; acquire the final selection on expiry and reset the change count. Repeated refresh of the same category and Local file do not count. Already running requests finish with stale results ignored. This does not guarantee recovery from GitHub 403/429 limits.

Desktop 0.15.6 supersedes the previous reset cycle: count category changes throughout the app session, allow only the first three without waiting, and wait 60 seconds for every change from the fourth onward. Changes during the pause restart it for the final selection; same-category refreshes do not extend it. Display total changes and no-wait changes left, distinguished from GitHub request quota. Why? explains the policy. English Help popups explain EEPROM IP versus Current IP, Target IP/Ping, BIT/MCS/JTAG, MPC/MPCX, temporary host IP/NIC/mask/DHCP and clock/persistent settings. Keep ordinary UI compact and links keyboard accessible. Opening help performs no network requests or mutations.

Desktop 0.15.7: show only the custom Messages drag bar. Hide the native PanedWindow sash with zero width/padding, flat relief and no handle, removing the duplicate divider. Preserve custom drag handlers, 180/80-pixel pane minima, mapped startup positioning and message history.

Desktop 0.15.8: label the cable row JTAG cable: and place Help on the same row. Explain JTAG, automatic startup detection, Rescan, explicit serial selection with multiple cables, and FT232H/HS3 ambiguity in the popup. Distinguish the programmer from an Ethernet adapter; preserve selection guards and programming behavior.

Desktop 0.15.9: use the top Language selector to switch English / Japanese during the session (English default). Translate labels, buttons, tabs, cooldown counters and Help/Why? explanations. Keep firmware names, repositories, paths, IPs, diagnostic logs and backend errors unchanged. Presentation-only language changes must not change selections, start requests or alter the cooldown count. Keep source identifiers/comments English and isolate Japanese translation strings in ui_language.py; this explicitly supersedes English-only GUI text. Keep help topics synchronized and use display-only StringVar proxies rather than changing backend variables. Language preference is session-only; CLI remains English.


Mac signing and notarization run on GitHub-hosted macOS runners; maintainers do not need to build or sign on their own Mac. The manual Sign and notarize macOS release workflow and macos_notarization.py support an App Store Connect team API key or Apple Account app-specific password; Actions secrets still need to be configured; do not claim certification until Apple Accepted, ticket validation and Gatekeeper assessment actually succeed. See [developer notes](FOR_DEVELOPERS.md) for the initial secret setup and browser-only release steps. Never post or commit private keys/passwords.

Notarization timeout recovery: run 39025172325 signed both architectures successfully, then notarytool submit --wait --timeout 30m exited 124. This is a wait timeout, not evidence of Apple rejection. Submit without --wait, immediately persist the UUID and exact signed submission.zip SHA256, then query/wait (default 90m). Save final/pending status, service stdout/stderr and the Apple log. Always retain per-architecture notary-state artifacts, including source-release provenance; never include certificates, keys or the keychain. Resume with the prior run ID and same source release: restore/checksum the exact signed archive, skip signing/uploading, recheck the same submission, and staple only after Accepted. Changing the signature/timestamp changes what was submitted; never resume an old ID against a newly signed app. Public notarized downloads still require both architectures, ticket validation, Gatekeeper and GUI smoke checks. main-branch changes to the notarization helper/workflow rerun using the latest tested preview; workflow_dispatch permits an explicit source and resume_run. The old timed-out run did not preserve its signed archives/IDs, so it cannot use this new artifact-resume path.

The Target IP row provides get_version beside Ping on all network tabs. Match hul-common-lib get_version: read BCT 0xe0100000 using four little-endian byte lanes spaced 0x10000, display upper 16-bit FW ID and decimal major/minor bytes. Run off the UI thread, report results/errors through Messages, never write registers or infer board revision from unknown IDs.

## Native Windows and Linux desktop builds

The current user request explicitly adds native Windows and Linux desktop bundles alongside macOS, superseding the earlier WSL-first Windows boundary. Use build-desktop-app.py and desktop-app.yml. Windows must use the user's windows-hs3-d2xx branch pinned at 3e5727bc1126307a0838d62f21971a2fa8f6a12f, built with USE_FTDI_D2XX=ON, ENABLE_USB_SCAN=OFF and ENABLE_UDEV=OFF. Linux retains bf2b52916e7b6216ba1cc0b30933827d7735b05d. Preserve exact commit/source provenance and the XC7K160T bridge. Linux loader lookup must use runtime/linux/bin; Windows helpers have .exe suffixes. Build unchanged pinned POSIX SiTCP helpers with Cygwin on Windows and ship the required runtime; do not rewrite validated EEPROM logic. Windows D2XX uses the existing FTDI CDM/System32 ftd2xx.dll and must not request WinUSB replacement. Omit libwdi and driver-switching buttons from this bundle. Validate serial availability through the chosen loader’s read-only --scan-usb; reject busy/duplicate serials and preserve readiness after physical HS3 confirmation. Temporary host-IP automation stays macOS-only. Require frozen GUI/CLI/loader/helper smoke checks; Local Windows and Linux builds and smoke checks passed; distinguish these from unexecuted hosted CI and hardware checks. Bundle the Cygwin/iconv/intl runtime dependencies and their version-matched SHA512-checked sources. Keep full bundle folders and SHA256 archives; Actions artifacts are retained for 30 days, not automatically released.

For MCS, explicitly pass --skip-reset on bridge dump/write commands; do not rely on loader defaults to leave SRAM unchanged after access. Save full-backup SHA256, reprobe model/JEDEC-derived identity/capacity after backup, and stop before -f on any change. Preserve the full backup on every failure.

Windows D2XX hardware validation: AMANEQ v4 LR-TDC v2.A MCS from AMANEQ-official/StrLrTdc commit d1b625988b5d0d243be0e725e56dd4ded6b89d7b was programmed through a physically confirmed HS3 using the existing FTDIBUS driver. JTAG identified one XC7K160T; flash was S25FL128S, JEDEC 012018, 16 MiB. The full backup and SHA256 were saved before erase, identity was rechecked, and all 6,692,572 MCS payload bytes matched a separate flash dump. --skip-reset left the SPI bridge in SRAM. Power-cycle boot, DAQ/network operation, BIT loading and macOS/Linux hardware programming remain unverified. No driver changes, separate FPGA reset or power cycle were requested. Keep private backups/logs out of Git.

Put OS/architecture download links and publication status near the start of README. Link directly to known assets; never describe unpublished, failed-build or expired artifacts as downloadable. For Actions artifacts, give the workflow URL, successful run, Artifacts location, sign-in requirement, extraction and launch steps. Save as UTF-8 and verify Japanese language labels, Markdown brackets and link targets.
