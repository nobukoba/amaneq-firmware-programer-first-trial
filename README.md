# AMANEQ Firmware Programer (first trial)

**Language: English | [譌･譛ｬ隱枉(README.ja.md)**

Download and program AMANEQ firmware through openFPGALoader: persistent MCS and temporary SRAM BIT loading for all supported families.

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

## macOS desktop app

Download the Apple Silicon (arm64) or Intel (x86_64) ZIP from [Releases](https://github.com/nobukoba/amaneq-firmware-programer-first-trial/releases). Expand Assets on the newest macOS desktop preview. Extract the ZIP and move amaneq-firmware-programer.app into Applications. macOS 15+ is required. Python, Tk, openFPGALoader and HTTPS CA certificates are bundled; no Homebrew setup is needed to run it.

Version 0.15.2 has four tabs beneath the AMANEQ / CIRASAME / STAG selector: Firmware, Jitter Cleaner, MPC / MPCX, IP addr. (left to right). Firmware scans cables automatically, filters the GitHub list by Target and Firmware, sorts newest first and selects the first image. Choose GitHub list or Local file and use the single normal-size bold Program image button. The GitHub repository URL is editable and remembered per profile during the session; the list includes current files plus matching images recovered from tags and firmware-directory commits. History limit defaults to 5 total images and accepts 1..1000; change it and press Enter or Refresh list for more. Repeated identical path/blob images are collapsed; distinct contents with the same filename remain separate. Tag / commit identifies each revision. Current-branch images remain first and the newest is selected. Refresh list forces acquisition. History traversal is bounded; increasing the limit searches further, while API/rate-limit failures are reported as incomplete history. Loader selection and the separate latest-MCS button are removed. A single known cable is automatic; multiple cables still require a serial selection, and unidentified FT232H still requires physical HS3 confirmation. Cached/offline results are labeled. Files remain pinned to the displayed commit/path; BIT and MCS are available for all supported families.

For optional DAQ Ethernet access, choose an Ethernet adapter, enter the host IPv4 address/mask and press Apply temporarily. This adds an IPv4 alias, preserving DHCP, DNS and gateway configuration. It does not set the board's address and is unnecessary for USB/JTAG flashing. macOS requests administrator approval. Restore network or normal exit removes only the app's alias; a separate helper also watches application exit/crash. Existing addresses and overlapping subnets on other interfaces are rejected. If cleanup fails, the app reports it and preserves the lease record; aliases are also cleared by reboot. Network changes are not performed at startup. The temporary host address defaults to 192.168.10.20 with mask 255.255.255.0 and remains editable.

Downloads, logs and lease records are under ~/Library/Application Support/AMANEQ/. The app is ad-hoc signed, not Apple-notarized, so the initial Privacy & Security / Open Anyway approval may still be required. USB-driver simplicity does not remove Apple's app-distribution check. No system-wide protection is disabled. Physical HS3 programming and temporary IP changes on a user's adapter remain unverified; the new network lifecycle has offline tests.

Firmware includes an explicit Format selector. All supported families offer MCS or BIT. Both online history and local programming respect the selected format; local contents are validated in a worker before programming. HR-TDC mezzanine fixes the firmware to HR-TDC and hides the redundant Firmware selector. MPC / MPCX file uses a single row for label, path and chooser. Long file paths and GitHub URLs scroll horizontally with the mouse wheel; read-only path fields also support Left/Right and Home/End.

### Firmware, clock and license/IP tabs

Choose the board, then Firmware, MPC / MPCX, IP or Jitter Cleaner. The upstream clock command is set_cdce62002. CIRASAME uses its official lrtdc, lrtdc-10g and Skeleton repositories, excluding AMANEQ images. Its clock default is in_125_out_500_125. STAG is selectable for standard SiTCP operations, but firmware/clock writes stop until its official hardware/register reference is supplied.

Target IP is a single row with 192.168.10.10 / 192.168.10.16 / Custom and a Ping button. It has no mask display. Ping sends two ICMP requests asynchronously, reports the result beside the button and puts details in the log; no reply alone does not establish that RBCP is unavailable. Jitter Cleaner configures CDCE62002 without a device-mode selector. MPC / MPCX starts with a file chooser and detected type: normal MPC selects .16 and MPCX/SiTCP-XG selects .10. The labels now match the upstream classifier and independent official synthetic fixtures; extensions do not determine type. IP is a separate tab for address-only reading/writing and never needs a license file. All three network tabs share optional temporary host controls, hidden until Temporary static host IP address (DHCP preserved, restored on exit) is checked. Host defaults are 192.168.10.20 / 255.255.255.0; explicit Apply temporarily performs macOS setup. Disabling an active alias requests restoration and keeps controls visible if cleanup fails.

Choose one of the six hul-common-lib clock presets, then Apply. Register readback must match before copying to EEPROM. Save clock settings for the next power-on means copying verified clock registers to the chip’s EEPROM; it defaults on as upstream. Uncheck it for runtime-only changes. Acknowledging the copy does not prove power-cycle persistence.

For licenses choose a file in MPC / MPCX, then Check (read-only), Read or Write MPC/MPCX. Initialize XG EEPROM defaults off. Use the IP tab's Read IP / Write IP for address-only operations. New device IP is required for writing. Saved EEPROM IP is the default; explicitly select current/runtime IP to migrate the active endpoint and verify through the new address. IP changes preserve license data. Clear/reset are not exposed. Writes require confirmation and retain upstream generation checks, settling and readback verification.

The Mac ZIP includes the pinned native SiTCP commands and needs no compiler at runtime. For Linux/WSL source use, install Tk and a C++ compiler, then run:

```bash
python3 build-network-tools.py
python3 amaneq-firmware-app.py
```

Temporary-IP automation is currently macOS-only. On Linux/WSL configure host Ethernet to 192.168.10.20/24; setting only a WSL guest IP does not configure Windows Ethernet. Actual clock/license writes and adapter changes in the new GUI remain physically unverified.

## Windows desktop app: USB setup in the app

The native Windows x64 desktop preview adds explicit Use WinUSB and Restore Vivado driver buttons in the same window. A local desktop bundle can include Python, openFPGALoader, libwdi and cygpath, so WSL/usbipd and a separate Zadig window are unnecessary. Source users can start the window with the command below; driver switching requires the matching x64 `runtime/libwdi.dll` built as described in FOR_DEVELOPERS. Binaries are not tracked in this repository.

Cables are scanned automatically. Select the displayed serial and confirm the physical cable is an HS3. For driver changes, connect exactly one HS3/FT232H and close Vivado/cable applications. Press the explicit driver button, confirm the operation and approve Windows UAC. The app exports the original FTDIBUS package and hashes it before switching. Restore uses that saved package with Windows' device-installation API; it does not delete a shared driver package. Preserve `%LOCALAPPDATA%/AMANEQ/usb-drivers/`, including recovery information and operation results. A driver INF matches hardware IDs, so another FT232H may be affected when reconnected; serial selection alone cannot isolate a package binding.

Firmware programming remains a separate explicit action. The GUI currently presets HS3 and offers latest MCS or a local BIT/MCS; all supported families permit BIT. The existing CLI retains all repository/history/URL options and Xilinx cable paths. Linux/macOS do not use these Windows driver buttons. Driver operations are mock-tested, DLL resources and device matching were checked read-only, and the GUI was started. Switching and restoring through this new app have not yet been exercised on hardware.

```powershell
python amaneq-firmware-app.py
```

## Windows: copy and paste setup for WSL2

Use an existing Ubuntu WSL2 distribution. If absent, run `wsl --install -d Ubuntu` in Administrator PowerShell, reboot if requested, launch Ubuntu and finish its initial user setup. Then open Administrator PowerShell and paste the first block below. Review the downloaded script before running it. Setup installs usbipd-win on Windows and git/Python/openFPGALoader/usbutils in Ubuntu, reloads packaged udev rules, adds the default Linux user to plugdev, and clones the repository under the WSL user's home. It never programs the board. Installer dialogs may appear; handle a requested reboot and rerun Setup. `-Distribution` defaults to `Ubuntu`; another existing apt-based WSL2 distribution can be specified. No automatic WSL1 conversion or reboot is performed.

Next open Ubuntu using the second block and leave that terminal open. In the Administrator PowerShell run List and Attach using the exact BUSID printed by List. FT232H IDs alone do not prove an HS3 model. Attach explicitly binds/shares that device, then forwards it; no cable is chosen automatically. Run the Bash commands in Ubuntu. If multiple cables are attached, add `--serial` to the programming command. Detach returns the device to Windows; persistent sharing remains until `usbipd unbind --busid 4-4` is run as administrator. Repeat Attach after unplugging/reconnecting. ExecutionPolicy Bypass applies only to the launched process. For script help use `Get-Help .\setup-windows-wsl.ps1 -Full`.

```powershell
New-Item -ItemType Directory -Force "$HOME/amaneq-wsl-setup" | Out-Null
Set-Location "$HOME/amaneq-wsl-setup"
Invoke-WebRequest https://raw.githubusercontent.com/nobukoba/amaneq-firmware-programer-first-trial/main/setup-windows-wsl.ps1 -OutFile setup-windows-wsl.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-windows-wsl.ps1 -Action Setup
```

```powershell
wsl -d Ubuntu
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-windows-wsl.ps1 -Action List
# Replace 4-4 with the cable BUSID printed by List.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-windows-wsl.ps1 -Action Attach -BusId 4-4
```

```bash
cd ~/amaneq-firmware-programer-first-trial
./amaneq-firmware-programer.py scan
# This command writes firmware to the connected board:
./program-latest-mcs-amaneq-v4-lrtdc.sh --cable hs3
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-windows-wsl.ps1 -Action Detach -BusId 4-4
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

All supported families support BIT and MCS. `mikumari` means MikuClockHub, not MikuClockPrim.

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

History shows at most 5 total choices by default, including the current branch. Tags and commits pointing to the same revision are merged; historical revisions are sorted by commit date. Increase the total with `--history-limit` (maximum 1000), or specify a known tag/commit with `--ref`.

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

## Windows WSL2, Linux and macOS setup

The supported execution environments are Windows WSL2, native Linux and native macOS. Use Python 3.10+ and the matching OS build of openFPGALoader. Windows runs the Linux program and `.sh` shortcuts inside WSL2. Native Windows `.cmd` files remain legacy helpers outside this target scope.

For WSL2, install WSL2/Ubuntu and [usbipd-win](https://learn.microsoft.com/en-us/windows/wsl/connect-usb), keep a WSL terminal open, then forward the selected cable from Windows PowerShell. Binding requires Administrator rights; attaching does not. While attached, the cable is unavailable to Windows applications. Repeat attach after disconnect/reconnect. Install openFPGALoader and apply the Linux USB permissions above inside WSL. A Windows WinUSB replacement is not a prerequisite of this path.

```powershell
usbipd list
# Replace 4-4 with the cable BUSID printed above.
# Run bind in an Administrator PowerShell.
usbipd bind --busid 4-4
usbipd attach --wsl --busid 4-4
```

```bash
# Inside WSL2 (Ubuntu) or native Ubuntu/Debian:
sudo apt update
sudo apt install python3 git openfpgaloader
# On native macOS with Homebrew:
brew install python openfpgaloader
```

macOS uses `ioreg` to enumerate USB devices and selects FTDI cables by serial. It does not use Linux sysfs, udev or Windows cygpath. If access fails, close applications using the cable and inspect the openFPGALoader error; this program never changes drivers automatically. All three environments use the same Python commands and `.sh` shortcuts shown above.

## Platform and container status

macOS enumeration/serial selection has offline mock tests. WSL2, native Linux/macOS programming, Xilinx cables and mezzanine probing remain physically unverified. Earlier native Windows openFPGALoader/HS3 tests are historical evidence, not verification of these three environments.

Linux containers require host USB access and device permissions. Docker Engine requires `/dev/bus/usb` exposure. Apptainer usually exposes `/dev` and `/sys`, while retaining host user permissions. WSL requires USB forwarding before running a container. No Docker image or SIF is supplied.

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

New device IP uses a single row with its input and the Change current (runtime) IP instead of saved EEPROM IP checkbox.

The input/output frequency label and preset are on one row. Program image, Write MPC/MPCX, Write IP and Apply are bold at the normal button size.

Resize the window normally, or choose UI size (75–150%) to scale text and controls. Drag the divider above Messages to change the log height. Scroll up to read earlier messages from this run: automatic following pauses, so new output does not move your position. First goes to the beginning; Latest resumes following. Follow latest can also be toggled explicitly. Tab changes schedule layout and redraw immediately and after 25 ms, including scrollable canvases; mouse movement is no longer used to trigger their layout. Mac build/startup checks do not replace visual confirmation on the user’s Mac.

Jitter Cleaner displays Select input / output frequencies of CDCE62002 chip (MHz): beside the preset. The implementation-specific HUL register-map explanation is removed; the STAG unsupported-clock notice remains when applicable. CDCE62002 is the correct chip spelling.

Desktop 0.12: Target IP presets display 192.168.10.16 (SiTCP default) and 192.168.10.10 (SiTCP-XG default). These labels are presentation only: use the bare validated IPv4 address for Ping/RBCP and restore the correct label when selecting a detected MPC/MPCX file. Custom remains available.

Desktop 0.13 firmware display names: lrtdc → LR-TDC; hrtdc → HR-TDC; lrtdc-10g → LR-TDC 10GbE; mikumari → MIKUMARI Hub; skeleton → Skelton (user-requested spelling). This is a UI mapping only. CLI options, repository paths, artifact filenames, cache identities keep their existing internal identifiers.

Desktop 0.14 supersedes the former Skeleton-only BIT restriction: all supported firmware families offer MCS / BIT, with existing FPGA/target/cable checks retained. BIT loads SRAM temporarily; MCS writes persistent flash. Remove Messages Expand/Restore; resize the log by dragging its divider. MPC/MPCX path caret movement (Left/Right, Home/End or clicking) reveals that position horizontally. Keep the temporary-IP enable checkbox on one line with the exact text Temporary static host IP address (DHCP preserved, restored on exit), without a duplicate frame heading. Remove the explanatory line below Write IP. These UI checks do not perform hardware writes or host-IP changes.

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
