# SiTCP / SiTCP-XG MPC / MPCX / IP Utility (first trial)

**Language: English | [日本語](README.ja.md)**

Experimental C++11 utilities for SiTCP and SiTCP-XG configuration over RBCP.

## Commands

The installed command set contains five commands:

- `mpc-mpcx-ip-writer` — write MPC/MPCX EEPROM data and optionally change EEPROM/current IP addresses.
- `mpc-mpcx-ip-reader` — read MPC/MPCX information and always display current/EEPROM MAC and IP addresses.
- `mpc-mpcx-ip-command` — advanced MPC/MPCX, IP, and low-level RBCP operations.
- `sitcp-sitcpxg-ip-writer` — configure IP addresses for SiTCP / SiTCP-XG.
- `sitcp-sitcpxg-ip-reader` — IP-only reader for SiTCP / SiTCP-XG.

## Quick installation

```bash
git clone https://github.com/nobukoba/sitcp-sitcpxg-mpc-mpcx-ip-utility-first-trial.git
cd sitcp-sitcpxg-mpc-mpcx-ip-utility-first-trial
make
make install
```

`make install` copies the executables into `./bin/`.

## How to use the writer

Write an MPC/MPCX file to the device:

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx
```

Write the file and set the saved EEPROM IP address:

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx \
  --set-eeprom-ip 192.168.2.170
```

Clear the EEPROM only, without writing a file:

```bash
./bin/mpc-mpcx-ip-writer 192.168.10.10 --clear
```

`--clear` erases the saved license and settings. Use it on its own, without a
file or IP-change options. Reprogram the appropriate license before normal use.

## How to use the reader

```bash
./bin/mpc-mpcx-ip-reader 192.168.2.161
```

Displays runtime and EEPROM contents separately, including MAC/IP addresses
and MPC/MPCX information. See the [output and exit codes](#reader-output-and-exit-codes) for report details.

## How to use the IP-only commands

Use these when only SiTCP / SiTCP-XG IP configuration is needed and no MPC/MPCX file should be involved:

```bash
./bin/sitcp-sitcpxg-ip-reader 192.168.2.161
./bin/sitcp-sitcpxg-ip-writer 192.168.2.161 192.168.2.170
```

No MPC/MPCX file is needed. The default changes EEPROM only; use `--current`
to change the active IP. Unspecified settings and license data are preserved.

## How to use the advanced command

```bash
./bin/mpc-mpcx-ip-command --help
```

For diagnostics and low-level operations, see the [developer command reference](FOR_DEVELOPERS.md#advanced-command-reference).

## Appendix

### Writer options and behavior

```text
mpc-mpcx-ip-writer CURRENT_IP MPC_OR_MPCX_FILE [options]
mpc-mpcx-ip-writer CURRENT_IP --clear [--port N] [--timeout SEC]
mpc-mpcx-ip-writer CURRENT_IP [MPC_OR_MPCX_FILE] --check [--port N] [--timeout SEC]
```

Write MPC/MPCX information and also set the current/runtime IP:

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx \
  --set-current-ip 192.168.2.170
```

Set both EEPROM/default and current/runtime IP addresses:

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx \
  --set-eeprom-ip 192.168.2.170 \
  --set-current-ip 192.168.2.170
```

Default RBCP UDP port is `4660`; default timeout is `3` seconds. These defaults are also shown by `--help`.

Common writer options (see `--help` for all options):

| Option | Behavior |
| --- | --- |
| `--clear` | Clear EEPROM only; no file/IP changes (default: off) |
| `--check` | Read-only device/status check; optional file type match (default: off) |
| `--initialize-eeprom` | Force XG initialization; normal MPC unchanged (default: off) |
| `--set-eeprom-ip IP` | Set EEPROM/default IP address |
| `--set-current-ip IP` | Set current/runtime IP address |
| `--no-fallback` | Stop on unreadable normal-MPC initialization RAM (default: off) |
| `--port N` | RBCP UDP port (default: 4660) |
| `--timeout SEC` | RBCP timeout in seconds (default: 3) |
| `-h, --help` | Show help |

When both IP options are given, EEPROM IP is set first and current IP last. The writer reconnects to the new IP and verifies the result.

Programming and Clear display runtime and EEPROM MAC/IP before and after the operation. Success is printed only after all requested operations and verification complete. Check has its own read-only report below. Use the reader for full register dumps.

### Check and Initialize EEPROM: official GUI correspondence

`--check` corresponds to the official Writer's **Check** button: it reads device
generation and the EEPROM status flag. With a file it also classifies the file
and checks that its MPC/MPCX generation matches the device. No write is sent.
A file is optional in both the CLI and the tested official GUI.
Successful output follows the GUI's wording and line order: `MPC(X) File`,
`Interface`, `Device`, then EEPROM initialization state. Without a file, it prints
`MPC(X) File : Not Selected.` and omits Interface and the match suffix.
This is not a license-content verification or a comparison of the complete
EEPROM. The reported flag is not the normal-MPC writer's automatic initialization
decision; see the technical guide for that distinction.

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP --check
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --check
```

Check exits 0 on successful reads and, when a file is supplied, a type match;
7 means file/device generation mismatch; 1 means a read/file/option error.
Do not combine it with Clear, initialization, IP changes or programming options.

`--initialize-eeprom` corresponds to checking **Initialize EEPROM** and then
clicking **Write MPC(X)** in the official GUI. A file is required. On XG it
replaces saved settings with current RAM settings and overlays the selected
MPCX license/MAC, even when EEPROM is already initialized. This can replace a
previously saved IP with the current IP. It is not Clear and does not erase the
entire EEPROM to FF or immediately change active RAM settings. An unreadable
required XG RAM image stops the operation; there is no fixed XG fallback.

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --initialize-eeprom
```

In the tested official version, the checked box did not force initialization
of an already initialized normal-SiTCP MPC record. The CLI preserves that
behavior: this flag has no additional effect on normal MPC; its automatic
initialization/fallback policy still applies. Neither new option is valid with
`--clear`. Initialization can use the existing IP override options after file
programming. There is no additional CLI confirmation dialog.
See [the detailed option reference](FOR_DEVELOPERS.md#check-and-forced-initialization-options)
for register evidence, failure behavior and validation scope.

### TCP/UDP port options

The standalone IP writer can set IP, TCP data port and UDP/RBCP port together:

```bash
./bin/sitcp-sitcpxg-ip-writer 192.168.2.187 192.168.2.188 --eeprom --tcp-port 24 --udp-port 4660
```

`--tcp-port N` and `--udp-port N` accept 1..65535; the default is to preserve
existing ports. `--port N` selects the current communication port (default:
4660). It does not change the stored port. For `--current`, the writer verifies
through the new IP and requested UDP port; EEPROM changes leave the current
endpoint in place. All other settings and license bytes are preserved. These
port options belong to the standalone writer. Output formatting is unchanged.

### Normal MPC writing

Normal SiTCP programming restores the current network settings when the EEPROM
IP indicates an uninitialized record. Otherwise it retains the EEPROM settings.
Initialization saves the current runtime IP when its settings can be read.
Otherwise the default uses the official fixed settings, including saved IP
`192.168.10.16`; `--no-fallback` stops before writing instead.
Use `--set-eeprom-ip` to save a different IP after successful MPC programming.
See the [detailed option reference](FOR_DEVELOPERS.md#additional-options-reference)
and [native comparison](FOR_DEVELOPERS.md#normal-mpc-fallback-native-execution-recheck-2026-10-15).

### MPCX writing after clearing EEPROM

Preview the base MPCX image without writing:

```bash
./bin/mpc-mpcx-ip-command mpcx-plan DEVICE_IP FILE.mpcx
```

Then program the device:

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx
```

Initialization saves the current runtime IP in EEPROM. Use `--set-eeprom-ip` to save a different IP. If the required configuration cannot be read completely, initialization stops before writing. See the [developer guide](FOR_DEVELOPERS.md#mpcx-initialization-source-and-limits-2026-09-26) for initialization conditions, byte ranges, and differences from the official tool.

### Reader output and exit codes

Runtime and EEPROM MAC/IP values and MPC/MPCX information are displayed separately. `??` marks unreadable bytes; `unavailable` marks fields with missing data.

| Exit code | Meaning |
| --- | --- |
| `0` | Complete read |
| `3` | Partial read |
| `1` | Fatal error, such as a timeout or short reply |

The same detailed report is available with:

```bash
./bin/mpc-mpcx-ip-command read 192.168.2.161
```

See the [developer guide](FOR_DEVELOPERS.md#runtime--eeprom-diagnostic-reports) for register ranges, formatting, generation detection, and bus-error handling.

### Build requirements

- C++11 compiler (`g++` or `clang++`)
- POSIX sockets
- `make`

The default build uses `-std=c++11`. Targets are Linux, macOS, and WSL.

### Installation options and updates

The default installation is `./bin/` in the checkout and needs no administrator privileges. Running `make` alone does not refresh installed copies.

After updating the source, rebuild and refresh the installation:

```bash
git pull --ff-only
make install
```

`make install` builds any outdated binaries before copying them.

To choose another installation prefix:

```bash
make install PREFIX="$HOME/.local"
"$HOME/.local/bin/mpc-mpcx-ip-reader" DEVICE_IP
```

If `$HOME/.local/bin` is on your `PATH`, you can also run the command by name.
With a custom prefix, replace `./bin/` in the examples with your
chosen `PREFIX/bin/`. For a system installation, use
`sudo make install PREFIX=/usr/local` (administrator privileges required).

### Official links and references

- [Bee Beans Technologies](https://www.bbtech.co.jp/)
- [SiTCP / SiTCP-XG software and manuals](https://www.bbtech.co.jp/download-files/sitcp/index_en.html)
- [SiTCP MPC Writer XG User Guide (English PDF)](https://www.bbtech.co.jp/download-files/sitcp/SiTCP-MPC-Writer-XG-en.0.1.1.pdf)
- [SiTCP Forum](https://sitcp.bbtech.co.jp/)

### Documentation

- [For developers](FOR_DEVELOPERS.md) — architecture, build/development notes, technical evidence, MPC/MPCX EEPROM mappings, device-generation detection, references, and testing.
- [Agent instructions](AGENTS.md) — constraints for automated development.
