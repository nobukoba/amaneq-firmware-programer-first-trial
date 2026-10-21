# Development handoff — 2026-10-21

**Language: English | [日本語](HANDOFF.ja.md)**

Read this file and [AGENTS.md](AGENTS.md) before continuing. This is the current state; it supersedes older WSL-first/WinUSB-only notes. Preserve the spelling `programer`.

## Current implementation

- macOS keeps its existing Apple Silicon/Intel application builder.
- `build-desktop-app.py` builds native Windows x64 ZIPs and Linux x86_64 tar.gz archives, including Python/Tk, CA data, openFPGALoader, an uncompressed XC7K160T bridge and four SiTCP helpers.
- `.github/workflows/desktop-app.yml` builds both new platforms. It uploads 30-day Actions artifacts, not Releases. [Run 39468344602](https://github.com/nobukoba/amaneq-firmware-programer-first-trial/actions/runs/39468344602), commit `6cdc836`, passed Windows/Linux builds, 112 tests, GUI startup/CLI/loader/helper checks and artifact uploads. Download via README links after GitHub sign-in.
- Windows must use `nobukoba/openFPGALoader` branch `windows-hs3-d2xx`, commit `3e5727bc1126307a0838d62f21971a2fa8f6a12f`, with `USE_FTDI_D2XX=ON`, `ENABLE_USB_SCAN=OFF`, `ENABLE_UDEV=OFF`. Do not substitute that fork's `master` branch.
- Windows uses the installed FTDI CDM/System32 `ftd2xx.dll`. No WinUSB replacement or libwdi is required. Normal desktop bundles omit driver-switching buttons. Vivado and this application must release the cable before the other uses it.
- Windows still bundles Cygwin/cygpath for MCS paths and Cygwin-built SiTCP helpers. Those helpers need `cygwin1.dll`, `cygiconv-2.dll`, `cygintl-8.dll`. Matching package sources are version/size/SHA512 checked and shipped with notices. Do not describe the whole application as using only Windows system libraries.
- Linux keeps loader commit `bf2b52916e7b6216ba1cc0b30933827d7735b05d` and libftdi/libusb. The local archive targets Ubuntu 26.04; CI targets Ubuntu 24.04. USB permissions/udev rules remain host requirements. macOS also uses libftdi/libusb.

## Verified evidence

111 offline tests passed on native Windows/Python 3.12 and Linux/WSL/Python 3.14. Extracted Windows/Linux bundles passed GUI startup, CLI help, loader capability listing and all four helper help checks with system-only PATH. These are not visual-layout or board-network tests.

With explicit user authorization and physical HS3 confirmation, the native Windows D2XX application programmed:

- Target: AMANEQ v4, LR-TDC v2.A, MCS.
- Firmware: `AMANEQ-official/StrLrTdc`, commit `d1b625988b5d0d243be0e725e56dd4ded6b89d7b`, `mcs/amaneq-4-strlrtdc-v2.A.mcs`; Git blob/size and contents validated.
- Hardware: one XC7K160T, IDCODE `0x0364c093`; S25FL128S, JEDEC `0x012018`, 16 MiB; existing FTDIBUS driver retained.
- Complete 16 MiB backup and its SHA256 saved before erase. Flash identity rechecked after backup. All 6,692,572 MCS payload bytes matched an independent flash dump. Operation exited 0.
- `--skip-reset` left the SPI bridge in SRAM. No driver replacement, separate FPGA reset or power cycle was requested. The user was told to power-cycle manually to check boot.

Do not infer the board's present state from this last observation. No later power-cycle/boot confirmation has been reported. The user authorized that specific write, not future unattended writes.

## Safety behavior that must remain

- Check cable uniqueness and physical model. FT232H VID/PID alone does not identify HS3.
- On Windows, use the selected loader's read-only D2XX scan to validate serial availability; reject busy/duplicate/unavailable serials. Physical HS3 confirmation must not override driver readiness.
- For MCS, explicitly use `--skip-reset`, require a complete capacity-sized backup, save its SHA256, reprobe flash identity before `-f`, and compare every image byte against a separate readback. Stop on any failure; no destructive retries.
- Never auto-switch USB drivers, change host IP or power-cycle/reset hardware. Keep actual firmware, backups, license data, logs and local runtimes out of Git.

## Resume development

```bash
git status --short
python -m unittest discover -v
python amaneq-firmware-programer.py --help
python build-desktop-app.py --help
```

Use Python with Tk installed. For full compiler/dependency commands, see `.github/workflows/desktop-app.yml` and [FOR_DEVELOPERS.md](FOR_DEVELOPERS.md). These commands do not write hardware; do not run programming shortcuts as tests.

On the original development checkout, ignored local artifacts are under `dist/windows-d2xx/`, `dist/windows/` and `dist/linux/`. Private evidence/backups are under `logs/windows-d2xx-mcs-*/` (`*result.json`, `console.log`, full backup and readback); firmware provenance is under `firmware/downloads/`. They are not available from a fresh clone. Portable build tools were placed in a sibling `.amaneq-build-tools` directory. Do not upload these directories to make a handoff.

## Remaining work and user context

1. Hosted Windows/Linux CI succeeded in the run above. Actions artifacts last 30 days; recheck the target OS job and artifact when updating or after expiration.
2. Power-cycle boot/DAQ/network validation, BIT loading and macOS/Linux hardware writes remain unverified.
3. Vivado compatibility is the purpose of retaining FTDI/D2XX. The fork documents earlier coexistence evidence, but reconnecting Vivado after this session's MCS write was not tested. Do not claim it was.
4. The Windows desktop application was launched for the user. Its current startup screen has not been visually inspected. Computer Use instructions exist, but this session lacked the required `node_repl` runtime; do not claim to see the live desktop. User-provided screenshots can be inspected.
5. The user reads this chat on a phone. PC-local file links did not open there. After push, use HTTPS GitHub links for README/handoff, or show relevant text in chat.

## UI update 2026-10-22

Added AMANEQ-only selection, default tabless Simple mode and existing Expert mode, latest filename/version/commit display, adjacent firmware Help and copy menus. XG initialization defaults ON. Simple configures and reads back default clock/optional license/EEPROM IP before the final MCS write/readback; HR-TDC skips Simple network operations. DIP1=0 means default IP; saved custom IP uses DIP1=1. The new combined hardware workflow remains physically unverified.

Final verification: code be2ce6c passed 115 tests across all OS/Python 3.10/3.12 jobs. Both Mac architectures built, smoke-tested and published in run 39669574244; Windows/Linux built, smoke-tested and uploaded in run 39669574336. Current Mac preview is macos-preview-v0.15.9-be2ce6c (not notarized). README links for all platforms point to this code snapshot.


## Automatic public desktop downloads

This supersedes earlier Actions-only distribution instructions. `publish-desktop.yml` accepts successful same-repository main builds, verifies SHA256, and publishes Windows/Linux at `desktop-preview` and unnotarized Mac at `macos-preview`. Ordinary users need no GitHub sign-in. Keep the fixed Release URLs in README; do not edit links per build. Failed, PR, fork or older builds cannot replace the successful download. Preserve commit-specific releases and `build-info.json`. Publication is independent of notarization and never submits to Apple. Test with `python -m unittest discover -s .github/scripts -p 'test_*.py' -v`.
