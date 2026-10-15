# For developers

Use [current implementation status](#current-implementation-and-verification-status-2026-10-15),
[the option reference](#additional-options-reference) and
[current native differences](#official-versus-custom-comparison-current-conclusions-2026-10-15)
for present behavior. Dated hardware and investigation sections retain the
tested revision's observations; later fixes do not retroactively change them.
Actual license files, packet captures and device backups are private; external
session reports mentioned here are not included in an ordinary source checkout.

## Check and forced initialization options

Latest pacing update: MPC and MPCX file programming now wait 500 ms after
each enable, data-chunk, optional-extension and protection ACK. Failed
enable/data transactions wait 500 ms before cleanup protection; data is never
retried. This supersedes the older ACK-paced XG timing observations below.
The wait is after ACK, so the time between write starts can exceed 500 ms.
Reads, standalone IP writing and Clear retain their separate timing policies.
A fresh real-XG capture measured enable-to-data 502.312 ms and data-to-protect
1765.535 ms, with successful image verification and restoration of the original
EEPROM. This establishes the measured case, not identical native elapsed time
or a guarantee about every OS/device. Private capture is in
`work/sitcp-debug/physical-192-168-10-10-xg/pacing-recheck/modes.pcapng`;
external summary is `outputs/sitcp-writer-debug/xg10-pacing-recheck.json`.
Validation stages and the final 55-test result are centralized in
[Testing](#testing); physical mode and pacing evidence is recorded separately.

`mpc-mpcx-ip-writer IP [FILE] --check [--port N] [--timeout SEC]` is a read-only
mode (default off). Before network access an optional file is validated as a
known 22-byte MPC/MPCX payload. It reads the independent generation identifier
at FF08/4 and the EEPROM FC10/1 status flag, then prints target type, status
flag and, if supplied, decoded file tag and Matched/Mismatch. No MAC/IP snapshots,
license programming, Clear, protect command or full EEPROM verification occurs.
No file is required in either the CLI or the tested native GUI.
Exit 0 means successful reads and optional generation match, 7 means mismatch,
1 means a file/read/option error; missing required CLI arguments use exit 2.
This does not establish cryptographic license validity or byte-for-byte equality
with the installed license. A mismatch still causes zero writes.

Native Check was observed on both synthetic generations: exactly FF08/4 and
FC10/1 requests, no writes. It classified the selected file (Other), displayed
the interface generation and match, and reported initialization from FC10 bit7.
For normal SiTCP a valid saved IP with FC10=80 was reported as needing
initialization, even though the normal writer uses its separate IP endpoint
rule. The EEPROM message describes this status flag, not the automatic
normal-MPC programming decision. Native Check
also describes a checked Initialize box as forced; that wording alone does
not establish the subsequent normal-MPC write behavior.

`--initialize-eeprom` is a programming option (default off), requires a file,
and maps the native checkbox on the tested XG path. It forces the 80-byte
RAM-derived image even with FC10 bit7 clear. It does not Clear first. Shared
preparation still validates the entire RAM identifier/control image, then overlays
the file, writes/verifies 80 bytes and handles optional FF50/60/70 blocks as
before. Read failures remain fatal on XG, regardless of --no-fallback. Runtime
settings remain unchanged until an explicitly requested current-IP operation.
Existing transfer sizing and saved/current IP overrides remain available.
Mandatory protection cleanup and no destructive retry are unchanged.

The native checkbox was also exercised on normal SiTCP with saved IP 192.0.2.10
and FC10=80. Despite Check's forced wording, the actual write read no FF18/40,
preserved FC11 and saved settings, set FC10=01 and overlaid only the MPC data.
The CLI matches that observed behavior: --initialize-eeprom is accepted but has
no additional effect on normal MPC. Its IP endpoint automatic rule and normal
fallback/--no-fallback remain unchanged. Do not describe this option as forcing
normal-MPC RAM copies or factory defaults.

Independent synthetic native fixtures are
`tests/reference/official_xg_forced.json` and
`tests/reference/official_normal_forced.json`; they start with different RAM and
EEPROM settings, with EEPROM already initialized for XG. Tests compare full
128-byte results and exact base writes. The original trace includes native
Check plus the write operation; it is not a claim that all CLI read packets
or native GUI delays are identical. These fixtures are loopback-only; the
real-board recheck below separately verifies XG forced programming.

--check rejects Clear and all programming/IP options, including
--initialize-eeprom, --no-fallback and explicit chunk sizing. --clear rejects
--check and --initialize-eeprom. All these conflicts are rejected before access.
Standalone IP commands and advanced mpcx-plan gain neither new flag. Ordinary
file programming output remains compact; Check prints a distinct read-only report
and does not print the writer's success message. No extra CLI confirmation
prompt is introduced by the force option.

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP --check
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --check
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --initialize-eeprom
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --initialize-eeprom \
  --write-chunk-size official --set-eeprom-ip 192.168.10.11
```

## Native Check display and new-mode hardware recheck (2026-10-15)

After adding the options, a fresh five-case capture on AMANEQ XG at
192.168.10.10 compared native forced initialization, CLI forced initialization,
native file Check, CLI file Check and CLI fileless Check. The previous 19-case
hardware suite remains separate evidence: its Clear, IP migration, port,
reboot and injected-fault cases were not all physically repeated in this pass.
The then-current 54-test simulator suite reran normal/XG programming,
native reference image and write equality, Clear, IP/port changes, fallback,
partial reads, unreachable devices, protection cleanup and lost-ACK handling.
No access was made to 192.168.2.187. Normal SiTCP is synthetic/reference-only
in this pass because the current AMANEQ firmware identifies as XG.

| Fresh physical comparison | Result |
| --- | --- |
| Forced initialization from the same initialized EEPROM | Native and CLI both enable FCFF/1, write FC00/80, then protect FCFF/1; every payload identical |
| Full results | All 128 EEPROM bytes identical; 80 runtime bytes unchanged |
| Optional extension reads | FF50, FF60, FF70 rejected by this board; no tail copies |
| Check with a file, native and CLI | Exactly FF08/4 and FC10/1; zero writes; complete RAM/EEPROM snapshots unchanged |
| CLI Check without file | Same two reads and no writes; the captured version omitted file/match fields; later native fileless inspection corrected display as described below |
| Restoration | Exact original 128-byte EEPROM and 80-byte runtime images verified |

Capture: private `work/sitcp-debug/physical-192-168-10-10-xg/modes-recheck/modes.pcapng`.
Machine-readable summary: external `outputs/sitcp-writer-debug/xg10-modes-recheck.json`.
Licensed images and packet payloads are excluded from the repository. Final
runtime IP was 192.168.10.10; saved EEPROM IP was restored to 192.168.10.17.
No power cycle was needed or performed for this recheck.

Before the subsequent 500 ms pacing update, native force enable-to-data/data-to-protect
intervals were 0.509634/2.537685 seconds; CLI intervals were 0.000727/1.265474
seconds. Reads, verification, delays, dialogs and error/protection behavior are
not claimed packet-for-packet equivalent merely because data writes match.
The earlier Clear pacing qualification still applies. Native GUI prompts before
programming; CLI execution is explicit and has no additional confirmation dialog.

Native Check dialogs were inspected on real XG and synthetic normal/mismatched
targets. The CLI now reproduces their successful report text and line order:

```text
MPC(X) File : Other
  Interface : 10GbE
Device 192.168.10.10 : SiTCP XG - Matched
EEPROM was already initialized
```

The tag is decoded from the file, not hard-coded to Other. Interface follows
the file (10GbE or 100/1000MbE), even for mismatched devices. Device reports
SiTCP XG or SiTCP 100/1000M and Matched/Mismatch. Native uninitialized text is
`EEOROM needs to be inbitialized.`; the CLI intentionally preserves those typos.
An additional native GUI check with an empty file field on real XG confirmed
that it still reads device generation and EEPROM state. It displays
`MPC(X) File : Not Selected.`, omits Interface and the match suffix, and uses a
red error icon despite displaying the successfully read device/status data.
The CLI now matches those three text lines; its exit code remains 0 on
successful fileless reads because no generation mismatch can be evaluated.
This corrects the earlier claim that fileless Check was a CLI-only extension.
The CLI keeps textual error diagnostics and process exit codes rather
than reproducing GUI error icons, modal framing or every error dialog. Exact
line tests cover both generations, both FC10 states and matching/mismatched
files. A decoded tag is classification, not license verification.

## Updated AMANEQ SiTCP-XG comprehensive hardware comparison (2026-10-15)

The user replaced this AMANEQ's firmware/SiTCP, after which its runtime
Identifier read 58544350 (XG), default IP was 192.168.10.10 and configured rate
was 10000 Mbps. Only this board on the Ethernet network was tested;
192.168.2.187 was excluded. The selected file was SN_2F2C54AF2C.mpcx (22 bytes,
MAC 7C:F0:98:01:21:F0). Its contents, actual captures and backups remain private.
The exact firmware binary/version was not supplied, so these results identify
the observed board and register state, not every XG firmware revision.

The custom build included the current uncommitted validated changes after
0297c7f5c5a078a2705177e624b282bcfb098e9e. Source/binary hashes, native executable
hashes, 19 cases, eight completed boot observations and the final capture hash
are recorded in the external sanitized `xg10-comprehensive-test.json` report.
Official tools were Writer 0.4.1-2-gc782 and Utility 0.9.0. Npcap/dumpcap
captured the physical Ethernet interface throughout, including changed IPs and
ports. Full RAM/80 and EEPROM/128 images were privately saved per paired case.

| Paired operation | Write sequence | Result |
| --- | --- | --- |
| MPCX settings preservation | enable, FC00/24, protect | Same starting/final RAM and EEPROM; exact address/length/data equality |
| Clear | enable, eight 16-byte FF blocks FC00..FC7F, protect | Same starting images; all 128 EEPROM bytes FF; RAM unchanged; exact writes |
| MPCX initialization after Clear | enable, FC00/80, protect | Same starting/final images and exact writes; RAM settings plus selected license/MAC |
| Saved IP and ports | enable, FC00/17, FC18/40, protect | IP 10.10 to 10.11, TCP 24 to 25, UDP 4660 to 4661; exact writes and resulting full images |
| Active IP and ports | FF00/17, FF18/40 | Same changes in RAM, EEPROM unchanged; exact writes and final images |

Here 10.10/10.11 abbreviate 192.168.10.10/192.168.10.11. All five paired
comparisons began with identical RAM and EEPROM images. Test-setup restorations
were outside each comparison's capture interval and were independently verified.
Physical-capture timing is part of the comparison; only write addresses,
lengths/payloads and complete image equality are asserted as identical.

### Startup, extensions and additional CLI paths

For both native and custom saved-settings writes, relay ON plus power OFF/ON
loaded IP 192.168.10.11, TCP 25, UDP 4661 and MAC 7C:F0:98:01:21:F0. RBCP
read-back at the new endpoint and TCP 25 connections succeeded. Relay OFF
power cycles returned runtime to default IP 192.168.10.10 and MAC
02:00:C0:A8:0A:0A. Active-only changes disappeared after reboot, without EEPROM
changes. The eight recorded boot observations all completed without JTAG
recovery; these are successful endpoint reads, not exact readiness-time measures.

Native initialization attempted FF50/60/70 reads of 16 bytes each. All returned
C9 bus errors with zero reply length; native displayed three extension warnings.
The current CLI tried the same three reads, received the same errors, skipped
all three copies and left FC50..FC7F unchanged. The capture and independent
full-tail comparison verify that behavior on hardware. This supersedes the
earlier hardware limit where the CLI skipped optional reads entirely. Readable
extension hardware is still untested; its behavior has synthetic tests only.

Explicit 16-byte CLI mode was tested for both initial 80-byte and preserved
24-byte images. The 80-byte split case matched the native initial and final
images, while intentionally issuing five data writes instead of one. The
24-byte split used 16+8. The MPCX writer's combined --set-eeprom-ip and
--set-current-ip options were also tested with 192.168.10.11; both destinations
and read-back matched expectations while ports remained unchanged. The detailed
reader completed with no register changes. A silent local endpoint returned a
bounded error with zero writes; this case did not access the physical board.

### Packet timing and visible differences

Observed write-start gaps in milliseconds:

| Operation | Native | Custom |
| --- | --- | --- |
| MPCX preservation, enable to data / data to protect | 503.157 / 513.985 | 0.703 / 263.694 |
| MPCX initialization, enable to data / data to protect | 1.658 / 2544.574 | 0.872 / 1264.873 |
| EEPROM IP/ports, successive four-write gaps | 0.265 / 187.193 / 439.775 | 0.789 / 187.455 / 440.092 |
| Runtime IP/ports, gap between two writes | 0.365 | 0.628 |
| Clear, minimum to maximum of nine gaps | 503.057..511.120 | 501.973..508.951 |

Do not infer programming delays solely from these gaps: ACK latency, native
extension processing and GUI interaction can contribute. Native and custom XG
Writer pacing are not identical. The latest XG Clear sample exceeded 500 ms,
but it does not erase the earlier normal-SiTCP sample below 500 ms or prove a
strict guarantee on every host. Extra custom reads include generation checks,
snapshots and mandatory verification. Some native case windows also include
benchmark diagnostic reads, so their read totals are not pure GUI-only totals.

Native Utility successfully saved settings and logged success. For active
IP/UDP changes it showed a warning recommending EEPROM mode; continuation was
explicitly selected. The actual packets and independent full reads confirmed
the migration, but its target fields and completion log did not update during
observation. Final native Read was refreshed to show the restored runtime.
Its normal-style TCP Command Port/Re-Connect labels on XG do not validate XG
timer/register interpretation; the custom reader retains generation-specific
decoding, decimal/hex values and raw data.

### Real-board ACK-loss tests and limitations

A local proxy forwarded each selected transaction once to the actual board,
received its ACK, then suppressed delivery to the requesting client once.
Custom enable-ACK, MPCX-data-ACK and EEPROM-parameters-ACK loss all returned
nonzero, sent no duplicate data write and received an acknowledged FCFF=FF
cleanup command. Observed operation durations with a 0.3-second timeout were
0.542, 0.554 and 0.853 seconds. Independent full reads matched the expected
image after the single captured data request and confirmed unchanged RAM; the
saved image was restored after each case. The MPCX fault test reused the same
license already installed, so its capture/ACK proves one accepted request,
not an independently measured EEPROM cell-programming event.
An ACK on the physical wire does not mean the proxy delivered it to the client.

In the native XG enable-ACK-loss test, the GUI displayed
`Could not set EEPROM Write Enable.` No data write, retry or protection write
was observed during the roughly 68-second interval through inspection and
dialog dismissal. That interval is not the native timeout latency. Protection
was then explicitly restored with an acknowledged command. This result differs
from the earlier bounded normal-SiTCP observation with no visible error; do not
generalize either observation to every native generation/failure path.

One benchmark snapshot timed out after native fault cleanup. Subsequent ping,
complete reads and the detailed reader succeeded without power/JTAG recovery;
no destructive write was repeated. Its cause is undetermined. No throughput,
all timer/control combinations, arbitrary firmware versions, readable extensions,
or long-term stability claim is established by these 19 scoped cases. The
native GUI's forced Initialize checkbox on an already initialized record was
not a paired test at that hardware-test stage. The later new-option comparison
above adds the CLI switch and synthetic native references for this path.

The subsequent new-mode recheck also paired forced initialization on the real
XG board; its write packets and complete images agreed as recorded above.

### Final restoration

All 80 RAM and 128 EEPROM bytes were verified equal to the test-start backups.
Runtime is again 192.168.10.10, MAC 02:00:C0:A8:0A:0A, TCP 24, UDP 4660;
the original saved EEPROM IP 192.168.10.17 and MAC 7C:F0:98:01:20:17 remain.
The temporarily tested MPCX/10.11 image is not left installed. Power remains
ON and the relay OFF command was sent; the resulting default runtime confirms
the selected startup behavior, while the relay itself provides no state feedback.
Final ping was 30/30 with zero loss. Capture and test proxy were stopped;
native Writer target was reset to 192.168.10.10:4660. Firmware was not programmed
by this test. Licensed packets/images were not added to Git or public archives.

## Official-versus-custom comparison: current conclusions (2026-10-15)

The following summarizes current behavior and the scope of its evidence. The
19-case XG suite predates Check, forced initialization and the new programming
delay; the later mode and pacing rechecks cover those additions separately.
The earlier normal-SiTCP suite used revision
`0297c7f5c5a078a2705177e624b282bcfb098e9e`. Do not treat that physical suite as
a hardware test of the newer fallback implementation.

| Item | Official tools | Current custom tools | Evidence and limits |
| --- | --- | --- | --- |
| Normal MPC preservation/initialization, Clear, EEPROM and runtime settings | Reference write sequences | Same addresses, lengths, payloads and final images in five paired operations | Real normal-SiTCP board; full starting/final RAM 64 and EEPROM 128 bytes compared |
| Read-back | No equivalent complete post-write verification observed in the compared successful sequences | Mandatory read-back; extra generation/snapshot/verification reads | Write equality does not imply all packets are identical |
| Normal MPC fallback | Confirmed fixed table after short RAM reply, GUI confirmation before programming | Same fixed table by default; --no-fallback stops before writes | Native synthetic FF18/40 reply contained only 39 bytes; full FC10/64 and final EEPROM/128 used as regression reference |
| FC11 during fallback | 00 after zeroing prepared record | Corrected to 00; other normal paths retain EEPROM FC11 | First custom fallback implementation retained FF; discrepancy fixed and regression added |
| XG mandatory RAM read failure | Zero writes for bus-error and short FF00/80 replies; static failure branch has no fixed-table substitution | Stops; normal fallback table is never used for XG | Synthetic native execution and static analysis of Writer 0.4.1-2-gc782; no real-device RAM fault induced |
| Enable ACK loss | No data, retry, protection write or error dialog during roughly 108 seconds observed | Bounded failure; protection restoration attempted and acknowledged in tested cases | Normal real-device proxy test; no claim about all native failure paths |
| Transfer length | Normal MPC 64; preserved MPCX 24; initialized MPCX 80 | Same default; explicit --write-chunk-size official; optional numeric chunks | Matching write images; changing transfer size is not a claim of identical timing |
| Clear pacing | Captured gaps 501.569..516.942 ms | Captured gaps 492.171..514.823 ms despite monotonic 500 ms scheduling | Strict wire minimum remains unresolved; clocks/scheduling/capture effects not isolated |
| MPC/MPCX programming pacing | Native intervals vary by path, ACK latency and GUI interaction | Wait 500 ms after each enable/data/protect ACK and before failure cleanup | New XG force capture: 502.312 ms enable-to-data, 1765.535 ms data-to-protect; elapsed-time equivalence is not claimed |
| Check | File optional; fileless output says Not Selected. with no Interface or match suffix | Same report text/order; two read requests, no writes; meaningful CLI exit codes | Fileless native XG inspected on hardware; normal/mismatch reports also checked on synthetic devices |
| Forced initialization | XG checkbox copies RAM even when initialized; checked normal MPC retained its automatic rule | --initialize-eeprom follows those generation-specific paths | Synthetic references for both; real XG full 128-byte image and exact write comparison |
| Reader output | Native GUI settings | Detailed raw bytes, decimal/hex and settings retained | More detailed diagnostics are intentional; do not remove information for visual compatibility |
| Power-cycle outage | No controlled attribution established | One outage after runtime migration; recovered by existing-flash JTAG reload | Six follow-up cycles did not reproduce; cause remains undetermined |

At the FC11-correction stage, strict C++11 build/install and
all 46 integration tests passed in 80.405 seconds. Synthetic bus-error, timeout
and short-reply custom tests compare the entire fallback record, license/MAC
overlays and protection, while --no-fallback tests establish zero writes.
Native fallback execution covers the short-reply case; native bus-error/timeout
fallback behavior is not established by those custom tests.

### Evidence locations and unresolved work

- External `normal-comprehensive-test.json` report:
  17 cases, five paired comparisons, ACK-loss observations and recovery.
- External `boot-reproduction.json` report: three
  baseline and three runtime-migration power cycles, no reproduction.
- External `xg-fallback-investigation.json` report: installed
  official executable hash, two valid synthetic failure traces and static path.
- [Synthetic native MPC fallback reference](tests/reference/official_mpc_fallback.json):
  complete expected data write and EEPROM image; suitable for repository tests.

The first three reports are external session deliverables and may be absent
from an ordinary source checkout. Real licensed captures, proprietary native
binaries, disassembly and device backups remain outside Git in private work
storage. No actual license file or license-bearing capture belongs in a public
source archive. The fallback fixture contains synthetic data only.

Remaining investigations: reproduce the power-cycle outage while preserving
pre-recovery evidence; separate Clear client-clock timing from wire timing;
extend native failure testing; verify readable optional extensions and additional
XG firmware/boards. XG runtime migration and post-boot acceptance are now covered
by the updated AMANEQ comparison above, not by a new test on 192.168.2.187.
None of these unresolved items should be described as confirmed SiTCP bugs.

## Normal SiTCP comprehensive hardware comparison (2026-10-15)

Tested code revision: `0297c7f5c5a078a2705177e624b282bcfb098e9e`.
Strict C++11 build/install and 45 integration tests passed in 75.397 seconds.
This session tested only the normal SiTCP 1G AMANEQ on the 192.168.10 network;
192.168.2.187 and SiTCP-XG were excluded. The board's default address is
192.168.10.16, while its starting and restored EEPROM/runtime address was
192.168.10.17, MAC 7C:F0:98:01:20:17, TCP 24 and UDP 4660.

Official MPC Writer 0.4.1-2-gc782 and SiTCP Utility 0.9.0 were exercised against
the real board with Npcap/dumpcap capture. RAM (64 bytes) and EEPROM (128 bytes)
were saved before and after each paired operation. Real license files, raw
images and raw captures remain private. The sanitized session report is
`normal-comprehensive-test.json` in the external deliverables directory.

| Paired operation | Write address/length/data sequence | Starting and final RAM/EEPROM |
| --- | --- | --- |
| MPC preserving settings | identical; enable, FC10/64, protect | identical |
| MPC initialization after Clear | identical; RAM settings copied into MPC image | identical |
| Clear | identical; enable, eight 16-byte FF blocks, protect | identical |
| EEPROM IP/TCP/UDP settings | identical; enable, FC00/17, FC18/40, protect | identical |
| Runtime IP/TCP/UDP settings | identical; FF00/17, FF18/40 | identical |

The IP settings comparisons changed IP to 192.168.10.18, TCP to 25 and UDP to
4661. Both programs' EEPROM changes were accepted after power cycling; runtime
changes were read back at the new IP/UDP endpoint and TCP 25 accepted a
connection. Runtime changes preserved EEPROM. For the official runtime test,
packets and register read-back establish the result; the GUI did not produce
a new completion log or update its target fields during observation. Do not
describe that GUI completion behavior as verified. Alternate licensed MAC
programming and explicit 16-byte MPC chunks were also exercised. The complete
session report contains 17 cases, including failure and reader tests.

### Differences and timing limits

The custom tools issue additional reads for independent generation detection,
snapshots and mandatory verification. Write-data equality does not mean the
entire UDP traffic sequence or user interface is identical. Normal MPC data
ACK latency was about 732 ms for both programs. The native success dialog
delays its protection write until dismissal; the observed roughly 24-second
gap included operator interaction and is not an EEPROM programming requirement.

Native Clear write-start gaps measured 501.569..516.942 ms; custom Clear gaps
measured 492.171..514.823 ms in this Windows/Cygwin capture. Source scheduling
uses a monotonic 500 ms interval, but this capture does not establish a strict
500 ms minimum on the wire. Clock resolution, scheduling and capture timestamp
effects have not been separated. This is an unresolved timing qualification;
the existing simulator tolerance is not proof of the stricter wire guarantee.

### Lost ACK and unreachable-device tests

A local UDP proxy forwarded each selected command once to the real board and
suppressed one actual response. No writes were blindly retried. Custom enable,
MPC-data and EEPROM-IP-data ACK loss returned failure, attempted protection
restoration, and received its protection ACK. Data already accepted by the
board was independently read back and the complete baseline was restored.
An unreachable local endpoint caused a bounded failure with zero write requests.
Protection confirmation means an acknowledged FCFF=FF write, not a read of the
write-only control register.

With the official Writer's enable ACK suppressed, one enable write and no data
write, retry, protection write or error dialog were observed over approximately
108 seconds. The window was then closed and protection explicitly restored
with an acknowledged command. This bounded observation does not prove that
the official program would wait forever or characterize other timeout settings.

### Power-cycle outage and final state

After the custom runtime migration test, a power cycle intended to restore
EEPROM settings produced no ARP/RBCP response. Default-mode relay selection and
another power cycle did not recover communication. A longer power-off was
confirmed at zero measured volts. FPGA JTAG status nevertheless showed DONE,
PLL lock and no CRC error. Reloading the existing flash configuration using
Vivado `boot_hw_device` recovered communication; no firmware file was programmed.
After recovery all 64 RAM bytes and 128 EEPROM bytes matched the starting
baseline exactly. The outage cause remains undetermined: temporal proximity to
the runtime test does not establish an IP-writer defect or EEPROM corruption.

After fault-test cleanup, the final read confirmed IP 192.168.10.17, MAC
7C:F0:98:01:20:17, TCP 24 and UDP 4660 in RAM and EEPROM. Final ping was 30/30
with no loss. Power and relay were left ON. This establishes the final observed
state, not a guarantee of stability across every subsequent power cycle.

### Follow-up power-cycle reproduction (2026-10-15)

Six additional captured trials did not reproduce the outage: three baseline
power cycles, then three cycles following custom runtime migration to
192.168.10.18/TCP 25/UDP 4661 and a TCP connection. Each cycle held output OFF
for three seconds, turned it ON, and first tested RBCP twelve seconds after
the ON command completed. All six answered the first probe; full RAM/64 and
EEPROM/128 comparisons matched the original baseline after every cycle.
No EEPROM writes or JTAG recovery were needed in this follow-up. Final state
remained 192.168.10.17, TCP 24, UDP 4660 with power/relay ON.

The sanitized external `boot-reproduction.json` records all six trials and the
private capture hash. This small negative series does not exclude an intermittent
fault. It repeats the immediate runtime-change/TCP/power sequence, not the
entire preceding clear, license, settings and repeated-boot history. These
results cannot establish whether the earlier failure originated in SiTCP,
board reset/clock logic, PHY initialization or power sequencing. Further
isolation requires a reproduced failure with evidence preserved before recovery.

## Fallback and transfer-policy investigations (2026-10-15)

### Normal-MPC fallback and explicit official transfer lengths (2026-10-15)

The user's requested policy supersedes the earlier fail-closed default for
normal-MPC initialization only. After a failed mandatory FF18/40 read (including
bus error, timeout or short response), use the complete official 40-byte table
shown below; no partial settings are mixed into the image. The fallback zeroes
the full FC10..FC4F record before overlays, including FC11=00; other paths
preserve FC11. MAC/license overlays, protection cleanup, no destructive retry
and read-back remain.
`--no-fallback` restores the former stop-before-write behavior. Independent
generation detection, initial snapshots, EEPROM reads and IP-only paths still
fail on unreadable required data. XG has no verified fixed fallback and retains
its mandatory RAM-read checks with or without this option.

The normal table at official executable VA 0x417BC0 is:

```text
C0 A8 0A 10 00 18 00 17 05 B4 12 34 03 E8 EA 60
13 88 2B F2 01 F4 01 F4 30 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00
```

`--write-chunk-size official` explicitly selects the existing default:
normal MPC FC10/64, preserved MPCX FC00/24, initialized MPCX FC00/80.
`--write-chunk-size 16` continues to select split data writes. These options do
not change Clear or IP-only transfer lengths, timing or optional XG extensions.
Programming options are rejected with `--clear` before device access.
Earlier real-device comparisons describe the preceding revision; this policy
change is tested using synthetic fault injection, not forced real RAM failures.
Initial policy validation, before the later FC11 correction: strict C++11
build/install succeeded; all 46 integration tests passed in 78.957 seconds.
Fault tests cover bus errors, timeouts and short RAM replies,
exact fallback bytes and MAC/license overlays, stop-before-write with
--no-fallback, and default/official/16-byte modes for all three image lengths.

### Normal-MPC fallback: native execution recheck (2026-10-15)

Official Writer 0.4.1-2-gc782 was exercised on a loopback synthetic normal-SiTCP
device with erased EEPROM and Initialize EEPROM unchecked. The FF18/40 request
received only 39 payload bytes. The GUI explicitly offered initialization using
default values because RAM could not be read. After confirmation it sent enable,
FC10/64 and (after dismissal of its success dialog) protection. All ACKs were
recorded; the simulator ended protected. No physical device was accessed.

The complete synthetic native record is checked in as
`tests/reference/official_mpc_fallback.json`. Its 40 settings bytes match the
previous statically recovered table exactly. The new execution evidence also
revealed that native fallback zeroes the whole prepared record, so FC11 is 00,
whereas the first custom fallback implementation preserved FF from EEPROM.
That one-byte mismatch was corrected only for the fallback branch. Normal RAM
copy and initialized-EEPROM paths still preserve FC11. The fallback regression
now compares the full 64-byte data write and all 128 resulting EEPROM bytes
against the native fixture for bus-error, timeout and short-response custom
faults. Native execution here covers the short-response case; it does not
establish native behavior for every network failure.
After this correction, strict C++11 build/install and all 46 integration tests
passed in 80.405 seconds, including full native fallback record equality.

### Official XG RAM-failure investigation (2026-10-15)

The installed official Writer 0.4.1-2-gc782 was tested against a loopback-only
synthetic RBCP device at 127.0.0.1:24662. No physical board, including
192.168.2.187, was accessed. This investigation used the computer-use skill
for the existing native GUI, raw UDP transaction logs from the simulator and
read-only static analysis of the installed executable. The external sanitized
report is `xg-fallback-investigation.json`.

With the XG identifier valid and EEPROM erased, the GUI requested FF08/4,
FC10/1 and FF00/80. In one run the last read received a bus-error response;
in a second valid run it received only 79 payload bytes while the header still
declared 80. Both runs produced zero write commands: no enable, base image,
extension or protection write, and all 128 EEPROM bytes stayed FF/protected.
The main window remained open without a new error dialog during observation;
this does not establish an indefinite hang. A preliminary short-response run
after a simulator shutdown was excluded; the restarted valid run had all three
requests recorded and its short response confirmed. These are simulator UDP
logs, not a separate packet-capture recording.

Static analysis agrees: the XG setup path calls the FF00/80 read at 0x402FFF,
compares its result against 0x50 at 0x403007, and branches on mismatch at
0x40300A to 0x402D79, returning zero. There is no fixed-table substitution in
this examined failure path. By contrast the normal-SiTCP failure branch
explicitly references the fixed table at 0x417BC0 from 0x407CE2.
The earlier successful synthetic XG reference independently demonstrates
that copied settings are supplied by RAM, including deliberately unusual
values, rather than a fixed image.

Conclusion for this version/path: retain mandatory complete XG RAM reads and
stop on failure; do not invent a fallback image from the settings of one board.
The generic native initialization wording about defaults does not establish
a fixed XG table. This is not evidence about every official version, hardware
variant or other failure path; no real-device RAM fault was induced. The normal
MPC default fallback and --no-fallback policy are unchanged by this investigation.

## Additional options reference

This section describes the current CLI. Dated evidence sections describe the
version tested at that time. Sizes are bytes, not bits or 16-bit words.
Run `make install` after updating sources to refresh installed binaries.

### MPC/MPCX writer options

| Option | Default | Scope and behavior |
| --- | --- | --- |
| --check | Off | Read-only target/status flag check; optional file generation match; separate mode, no programming options |
| --initialize-eeprom | Off | Force XG RAM-to-EEPROM initialization even if already initialized; normal MPC behavior unchanged, matching the observed native checkbox |
| --no-fallback | Off: normal-MPC fixed fallback enabled | Stop before writes if the normal initialization FF18/40 read fails; no effect on successful reads or records needing no initialization |
| --write-chunk-size official | official, also when omitted | One complete prepared base image; native lengths below, not native GUI delays or all native packets |
| --write-chunk-size N | No numeric override | Complete decimal integer 1..255; data blocks of at most N bytes with a shorter final block; never pad the image |
| --set-eeprom-ip IP | No override | Change saved IP after file programming/verification; preserve ports |
| --set-current-ip IP | No override | Last operation; change active IP, reconnect and verify; preserve ports |
| --clear | Off | File-free erase/verify FC00..FC7F; never clear implicitly |
| --port N | 4660 | Current RBCP destination; does not rewrite a port |
| --timeout SEC | 3 seconds per transaction | Shared transport accepts finite (0,86400]; not a total operation deadline |
| -h, --help | Off | Show help; standalone --help exits 0 |

| Prepared base image | Address | official/default | N=16 |
| --- | --- | --- | --- |
| Normal MPC, including initialization/fallback | FC10 | 64 | 16+16+16+16 |
| MPCX, already initialized / preserve settings | FC00 | 24 | 16+8 |
| MPCX, initialization required | FC00 | 80 | 16+16+16+16+16 |

Normal fallback is considered only when saved IP endpoint octets FC18 and FC1B
are both FF. Complete RAM settings are tried first. Timeout reads use up to
three total attempts; bus errors/short replies are not retried by that helper.
On failure, default behavior uses the complete native 40-byte settings table
(saved IP 192.168.10.16, TCP 24, UDP 4660), zeroes FC11 and overlays the selected
MAC/license. A successful RAM read preserves FC11. --no-fallback stops instead.
This flag neither creates an XG fallback nor disables optional extension reads.
Generation detection, initial MAC/IP snapshots, EEPROM reads and final
verification remain mandatory. Fallback cannot make an unreachable board writable.

For XG initialization, optional FF50/60/70 source reads remain 16 bytes each.
The default writes each readable block as 16 bytes; numeric N may split that
block. Chunk size changes neither Clear's fixed 16-byte blocks nor IP writes'
17+40-byte blocks. MPC/MPCX file programming now waits 500 ms after each chunk
ACK, independently of chunk sizing. Every programmed base/extension byte is verified.

Either transfer mode and --no-fallback can be combined with IP overrides.
Order is file programming/verification, saved IP override, active IP override.
An explicit saved IP therefore replaces the fallback IP after programming.
These stages are not atomic: earlier writes remain applied if a later stage
fails. Cleanup is best effort if communication is lost; never retry data writes
blindly. Normal fallback runs without a separate CLI confirmation prompt.
--clear rejects a file, IP overrides, --no-fallback and any explicit chunk-size
option (including official) before device access. Invalid/missing chunk sizes
also fail before access.

```bash
# Explicit native-length default.
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpc --write-chunk-size official

# Forbid normal-MPC fallback; no effect on ordinary successful RAM reads.
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpc --no-fallback

# Optional split data writes with the same final image.
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --write-chunk-size 16

# Save a chosen IP after programming, including after normal fallback.
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpc \
  --write-chunk-size official --set-eeprom-ip 192.168.10.17
```

### Standalone IP writer options

| Option | Default | Scope and behavior |
| --- | --- | --- |
| --eeprom | Selected if neither mode is specified | Save settings; active endpoint unchanged |
| --current | Off | Change active settings; reconnect to NEW_IP and requested UDP port and verify |
| --tcp-port N | Preserve destination-image value | TCP data port; complete decimal integer 1..65535 |
| --udp-port N | Preserve destination-image value | UDP/RBCP port; complete decimal integer 1..65535 |
| --port N | 4660 | Existing communication port, independent of new --udp-port |
| --timeout SEC | 3 seconds per transaction | Same shared transport bounds; read retries extend total duration |
| -h, --help | Off | Show help |

--eeprom and --current are mutually exclusive. NEW_IP remains required for
port edits: specify the existing IP of the destination image to keep it.
Omitted port values come from EEPROM for --eeprom and RAM for --current.
Other settings and license bytes are preserved. Port-edit options belong only
to the standalone IP writer, not the MPC wrapper or advanced ip-write.
Neither --no-fallback nor --write-chunk-size is an IP-only option. EEPROM
read-back uses CURRENT_IP and --port; it alone does not prove post-boot loading.

```bash
# Keep the saved IP at 192.168.10.17 while changing saved ports.
./bin/sitcp-sitcpxg-ip-writer DEVICE_IP 192.168.10.17 \
  --eeprom --tcp-port 25 --udp-port 4661

# Reach UDP 4660, then verify at the new IP and UDP 4661.
./bin/sitcp-sitcpxg-ip-writer DEVICE_IP 192.168.10.18 \
  --current --port 4660 --tcp-port 25 --udp-port 4661
```

Readers and advanced read/ip-read retain their --port/--timeout options;
advanced raw writes do not gain automatic verification/protection. See the
[advanced syntax](#advanced-command-reference) and
[current comparison](#official-versus-custom-comparison-current-conclusions-2026-10-15)
for evidence limits and deliberate differences from the native tools.

## Documentation consistency audit (2026-10-15)

The English/Japanese READMEs, this guide and AGENTS.md were reread against the
writer parsers, shared initialization/transport helpers and installed help for
all five commands. The stale README instruction to stop by default on normal
RAM failure was corrected in both languages. The option reference now records
defaults, units, applicability, examples, Clear conflicts, IP override order,
non-atomic failure behavior and the distinction between current and saved ports.
Detailed chunk-size examples stay here and in CLI help; README omits them.
Historical RAM-failure, migration, boot and timing claims are marked by their
validation stage, with the FC11 fallback exception and current results explicit.

The initial audit checked 31 local links and followed the 46-test fallback
validation. Later audits include the new Check/initialization links and reports.
The final pre-push audit rechecks all five installed --help invocations, option
coverage, every local Markdown link, fence balance, matching README examples,
requested appendix placement and `git diff --check`. The external
`documentation-consistency-audit.json` records exact counts, help text and
document hashes. Current code-validation results are recorded in the status
section below. No hardware operations are part of this documentation audit.

## Scope

This repository contains two related but functionally separate C++11 utility groups for SiTCP / SiTCP-XG:

1. MPC/MPCX license/configuration utilities.
2. SiTCP Utility compatible IP-address utilities, with optional TCP/UDP port changes in the standalone writer.

They may share low-level RBCP transport code, but they must not share domain logic. Keep three evidence classes distinct when documenting behavior: public Bee Beans Technologies documentation, static analysis of official utilities, and controlled verification with real files/hardware.

## Current implementation and verification status (2026-10-15)

This summary describes the current source; dated comparisons below also retain
historical observations. Default MPC data writes are whole-image: normal 64,
MPCX preservation 24, MPCX initialization 80 bytes. Explicit chunks are optional.
XG initialization additionally attempts three optional 16-byte extension reads,
copies only complete readable blocks and verifies copied bytes. This extension
update has synthetic coverage plus a real-board inaccessible-extension comparison
on updated AMANEQ XG. Readable extension hardware remains untested; the older
XG physical comparison used the version without extension reads. Check supports
optional files with native-style reports. Forced XG initialization is selected
by --initialize-eeprom; normal MPC retains its separate automatic rule.
Both normal MPC and XG file programming now wait 500 ms after every write ACK;
Clear schedules a minimum 500 ms between
write starts using a monotonic clock. The normal-SiTCP Cygwin capture contains
shorter wire intervals; the newer AMANEQ XG Clear capture exceeded 500 ms.
See both timing qualifications above; neither proves an unconditional guarantee.

EEPROM IP and TCP/UDP port writes have native-versus-custom physical comparison
on both generations. Full 128-byte EEPROM comparisons preserve other settings;
all test images were restored. Earlier sessions ended with 100/100 pings and
the comprehensive AMANEQ session with 30/30; the latest mode/pacing rechecks
ended with 4/4. Runtime IP/UDP migration and EEPROM
power-cycle acceptance are physically verified on normal SiTCP and updated
AMANEQ XG, including changed TCP/UDP ports. Readable-extension hardware remains
untested. Both generations have ACK-loss comparisons; an unresolved normal-SiTCP
power-cycle network outage is documented below.
Final pre-push validation: strict C++11 build/install and all 55 tests passed
in 157.795 seconds. The fallback changes have synthetic/native-reference
validation; the normal
physical suite used the preceding revision. Updated AMANEQ XG exercised the
19-case build plus separate new-option and pacing builds with saved evidence.
Publication status and exact revision are recorded in Git history;
test records below describe the code at each validation stage. Raw licensed captures/backups are
private; sanitized JSON deliverables are separate from repository contents.

## Build and compatibility

Build requirements are a C++11 compiler (`g++` or `clang++`), POSIX sockets, and `make`.


```bash
make
make install
```

The default build uses `-std=c++11`. Do not introduce C++14/17/20-only features without explicitly raising the minimum requirement. In particular, avoid `std::optional`, `std::string_view`, `std::filesystem`, structured bindings, `if constexpr`, and assumptions that `std::string::data()` is writable.

The build produces `./src/`; developers can run those binaries directly.
`make install` depends on the build and copies the five programs into
`$(BINDIR)`, defaulting to `$(PREFIX)/bin`, with
`PREFIX=$(CURDIR)`. After source updates, run `make install` to
refresh installed copies; `make` alone only updates `./src/`.
README usage examples consistently use the installed copy.

Default installation is local to the checkout:

| Command | Output location | How to run |
| --- | --- | --- |
| `make` | `./src/` (build output) | `./src/mpc-mpcx-ip-reader DEVICE_IP` |
| `make install` | `./bin/` (installed copy) | `./bin/mpc-mpcx-ip-reader DEVICE_IP` |

Override with, for example:

```bash
make install PREFIX=$HOME/.local
sudo make install PREFIX=/usr/local
```

Targets are Linux, macOS, and WSL using POSIX sockets. Both `src/` and `bin/` contain the same five commands after successful installation. `make clean` removes generated executables from `src/` but retains source files and installed copies.

For development without installation, replace the README's `./bin/` prefix with
`./src/`, for example `./src/mpc-mpcx-ip-reader DEVICE_IP`.

## Current programs

- `mpc-mpcx-ip-writer` — file programming with optional saved/current IP changes;
  separate file-free `--clear` and optional-file read-only `--check` modes.
- `mpc-mpcx-ip-reader` — MPC/MPCX reader; also reports current/EEPROM MAC and IP values.
- `mpc-mpcx-ip-command` — advanced/diagnostic interface with MPC/MPCX, IP, and low-level RBCP operations.
- `sitcp-sitcpxg-ip-reader` — IP-only reader, independent of MPC/MPCX payload decoding.
- `sitcp-sitcpxg-ip-writer` — IP writer using the official Utility setting-block sequence; no license decoding; only IP and explicitly requested TCP/UDP ports change.

## Architectural boundary

```text
MPC/MPCX domain:
  payload classification
  license/MAC payload reconstruction
  MPC/MPCX EEPROM layout
  MPC/MPCX writer/read/verify/clear

IP utility domain:
  current/runtime IP read
  EEPROM/default IP read
  EEPROM IP write
  optional current/runtime IP write
  optional TCP data / UDP-RBCP port changes in the standalone writer
  reconnect/read-back after runtime IP or UDP-port change
```

A common RBCP transport helper may be shared, but MPC/MPCX payload logic must not leak into the standalone IP-only commands.

## Source formatting

See [AGENTS.md — Source formatting](AGENTS.md#source-formatting) for the complete formatting rules.

## Implementation notes

The public commands use shared transport/network/MPC-MPCX code in `src/sitcp-sitcpxg-rbcp.hpp`, `src/sitcp-sitcpxg-network-config.hpp`, and `src/sitcp-sitcpxg-mpc-mpcx.hpp`. MPC/MPCX payload handling and IP register handling remain logically separated internally even though some commands expose both functions. Do not create a generic abstraction that silently mixes MPC/MPCX license layout with IP configuration layout.

IP/MAC register addresses used by the implementation are:

```text
current MAC : 0xFFFFFF12..0xFFFFFF17
current IP  : 0xFFFFFF18..0xFFFFFF1B
EEPROM MAC  : 0xFFFFFC12..0xFFFFFC17
EEPROM IP   : 0xFFFFFC18..0xFFFFFC1B
EEPROM WE   : 0xFFFFFCFF
```

This is an experimental implementation and is not an official Bee Beans Technologies utility. Proprietary executables, libraries, and user-specific MPC/MPCX files are not included.


## Public references

For generation detection, the authoritative public reference is the Bee Beans Technologies SiTCP-XG manual, section 4.2.3. It defines the read-only SiTCP-XG Identifier register as `0x58544350`.

- Bee Beans Technologies SiTCP downloads: https://www.bbtech.co.jp/download-files/sitcp/index_en.html
- SiTCP MPC Writer XG guide: https://www.bbtech.co.jp/download-files/sitcp/SiTCP-MPC-Writer-XG-en.0.1.1.pdf
- Bee Beans Technologies `sitcpy`: https://github.com/BeeBeansTechnologies/sitcpy
- SiTCP Forum: https://sitcp.bbtech.co.jp/

## MPC/MPCX RBCP behavior

The implementation uses an 8-byte RBCP header:

```text
FF CMD ID LEN ADDR[31:24] ADDR[23:16] ADDR[15:8] ADDR[7:0]
```

Commands are `0xC0` for read and `0x80` for write. The reply packet ID must match; bit 0 in the reply command/status byte is treated as an RBCP bus error.

Static analysis of `SiTcpMpcWriteXG.exe 0.4.1-2-gc782` identified the RBCP write routine around `0x409960` and read routine around `0x409e50`.

Reads may retry after timeout. Destructive writes must not be blindly retried because a missing UDP ACK does not prove that the device failed to perform the write.

## MPC/MPCX EEPROM and write protection

The relevant EEPROM window begins at `0xFFFFFC00`. MPC/MPCX programming uses:

```text
0xFFFFFCFF = 0x00  enable writes
0xFFFFFCFF = 0xFF  disable writes
```

The official MPC Writer clear path was observed to fill `FC00..FC7F` with `FF` in 16-byte writes while EEPROM writing is enabled, then restore protection.

## MPC/MPCX payload classification

The selected payload must be exactly 22 (`0x16`) bytes. The filename extension is not authoritative.

Recovered classifier behavior:

```text
normal SiTCP candidate:
  payload[6:13]
  subtract 0x34 from every non-zero byte
  valid seven-byte tag -> internal type 2

SiTCP-XG candidate:
  payload[0:7]
  subtract 0x2C from every non-zero byte
  valid seven-byte tag -> internal type 1
```

The normal candidate is tested first. Valid tag characters include NUL, space, hyphen, digits, and ASCII letters. Known matching files decode to `Other  `.

Payload classification validates MPC/MPCX data; it does not determine the target hardware generation.

## MPC/MPCX device generation detection

Determine the target generation first and independently by reading:

```text
0xFFFFFF08..0xFFFFFF0B
```

Only an exact value of `0x58544350` identifies SiTCP-XG. A bus error or identifier mismatch selects normal SiTCP. A timeout leaves the generation unresolved.

Do not infer generation from FC00/FC40 payload-looking contents; verified hardware can contain stale or alternate-layout data that makes both reconstructed payloads look valid. The former experimental `0xFFFFFF50` probe must not be used.

## Verified MPC/MPCX EEPROM mappings

SiTCP-XG:

```text
payload[0:16]  -> FC00..FC0F
FC10..FC11     -> preserve EEPROM bytes unless initialization is required
payload[16:22] -> FC12..FC17
```

The final six payload bytes correspond to the target MAC in the verified pair.
FC10..FC11 are not fixed constants: preserve EEPROM for ordinary programming;
use runtime bytes for initialization (see the initialization section below).

Normal SiTCP:

```text
payload[0:6]  -> FC12..FC17
payload[6:22] -> FC40..FC4F
```

Hardware/file pairs verified on 2026-09-19:

```text
SiTCP-XG 192.168.2.187:
  .mpcx = FC00..FC0F + FC12..FC17

normal SiTCP 192.168.2.161:
  .mpc  = FC12..FC17 + FC40..FC4F
```

These mappings belong only to MPC/MPCX handling and must not be used as the basis of IP-only operations.

## SiTCP-XG EEPROM parameter area

The public SiTCP-XG manual documents `0xFFFFFC10..0xFFFFFC4F` as the
EEPROM initial values for runtime registers `0xFFFFFF10..0xFFFFFF4F`.
Therefore, bytes in this range are device/network configuration and must not
be normalized merely because two boards differ.

Relevant documented runtime fields include:

```text
FC18..FC1B  IP address
FC1C..FC1D  TCP port
FC20..FC21  TCP maximum segment size
FC22..FC23  UDP port
FC24..FC25  TCP keepalive time (buffer not empty)
FC26..FC27  TCP keepalive time (buffer empty)
FC28..FC29  TCP timeout (connecting)
FC2A..FC2B  TCP timeout (disconnect)
FC2C..FC2D  TCP maximum segment lifetime
FC2E..FC2F  TCP retransmission time
FC32..FC37  TCP server MAC address
FC38..FC3B  TCP server IP address
FC3C..FC3D  TCP server port
FC40..FC41  transmission rate
```

According to SiTCP-XG Manual 1.8.1, disconnect timeout value `N` represents
`(N + 1) * 256 ms`. The documented transmission-rate range is 1..10000
Mbps in 1-Mbps units. Values outside that range should be reported as such,
not interpreted as a normal configured rate.

For MPCX programming on an already initialized EEPROM, the verified 22-byte payload mapping changes only
the following bytes when --initialize-eeprom is absent:
`FC00..FC0F` and `FC12..FC17`; `FC10..FC11` are preserved. The writer
must also preserve `FC18` and later configuration bytes. In particular,
different values observed at FC20/FC2A/FC40 on different SiTCP-XG boards are
not evidence of a bad MPCX payload.

## Observed SiTCP-XG FC40..FC4F case

A SiTCP-XG target at `192.168.2.187` was observed with a valid XG
identifier (`0x58544350`) and an MPCX payload that reconstructs exactly
from `FC00..FC0F + FC12..FC17`.

A historical raw observation is retained privately rather than distributing
license-derived bytes in this guide. The leading rate field was `0x83A8`.

A non-destructive read of `0xFFFFFF40..0xFFFFFF4F` returned the same
16 bytes.  Therefore these bytes are not merely an unread EEPROM remnant;
they are also visible in the corresponding runtime register window.

The first 12 bytes matched the common part of multiple verified normal
SiTCP `.mpc` files, whose layout is `MAC[6] + common[12] + varying[4]`.
This is strong empirical evidence that the observed `FC40..FC4F` contents
have a normal-MPC-formatted origin.  It is not proof of the device's write
history, and the final four bytes have not been decoded.

In particular, this observation does **not** mean that the attached MPCX
file was accidentally interpreted as an MPC file.  If the verified MPCX
payload for this target were mapped using the normal-MPC layout,
`FC40..FC4F` would instead contain `payload[6..21]`, which does not match
the observed bytes.

The public XG register map documents `FC40..FC41` as the EEPROM initial
value for the transmission-rate register, with a documented range of
1..10000.  The observed raw value `0x83A8` is 33704 and is outside that
range. Do not report it as an effective rate of 33704 Mbps. Do not
normalize, clear, or replace `FC40..FC4F` during ordinary MPCX
programming. Initialization selected by FC10 bit7 or --initialize-eeprom is the exception:
it copies runtime settings through FC4F before overlaying the MPCX payload.

A plausible history is that normal-MPC-formatted data was written to this
area before a later MPCX programming operation.  This remains a hypothesis,
not a verified fact.

## MPC/MPCX write sequence

When both IP options are given, EEPROM IP is written first and current/runtime IP last, preserving reachability at the original IP until all earlier operations finish. After runtime IP changes, reconnect to the new IP and verify by read-back. A lost acknowledgement may mean the IP has already changed; do not blindly retry the write.


1. Independently detect the target generation, then read its EEPROM programming record.
2. For MPCX, prepare either the 24-byte preservation image or the complete
   80-byte RAM initialization image as described below. For normal MPC, prepare
   the separate 64-byte FC10 record described in the official-writer comparison.
3. Release EEPROM write protection.
4. By default write the complete MPC/MPCX image in one transfer. Explicit
   `--write-chunk-size 16` selects 16-byte blocks; image contents/ranges are unchanged.
5. For XG initialization only, read FF50/60/70 in 16-byte blocks and copy each
   complete readable block to FC50/60/70; skip unreadable source blocks. Restore
   protection, including error paths where possible.
6. Read the programmed base image and every copied extension block again.
7. Compare byte-for-byte and fail on mismatch.

## Advanced command reference

Important subcommands include (MPC_OR_MPCX_FILE means a `.mpc` or `.mpcx` license/configuration file):

```text
inspect MPC_OR_MPCX_FILE
mac MPC_OR_MPCX_FILE
read IP [--port N] [--timeout SEC]
verify IP FILE [--port N] [--timeout SEC]
mpcx-plan IP FILE [--port N] [--timeout SEC]
probe IP ADDRESS [LENGTH] [--port N] [--timeout SEC]
rbcp-read IP ADDRESS LENGTH [--port N] [--timeout SEC]
rbcp-write IP ADDRESS HEX-BYTES [--port N] [--timeout SEC]
clear IP --yes-really-clear [--port N] [--timeout SEC]
ip-read IP [--port N] [--timeout SEC]
ip-write CURRENT_IP NEW_IP [--eeprom|--current] [--port N] [--timeout SEC]
```

`read` and `ip-read` display the same full runtime/EEPROM report. `ip-write` and the standalone IP writer print before/after MAC/IP and result summaries. The standalone IP reader retains its compact MAC/IP view. `ip-write` defaults to EEPROM and accepts `--current` for the runtime/current address.

Raw `rbcp-write` is a single diagnostic write transaction, not a high-level
configuration operation: it does not automatically restore EEPROM protection
or perform read-back. The clear guard applies to advanced `clear`, not arbitrary
`rbcp-write`. High-level writers and clear retain their verification/cleanup.

## IP utility design

The standalone IP-only CLI is:

```text
sitcp-sitcpxg-ip-reader CURRENT_IP [options]
sitcp-sitcpxg-ip-writer CURRENT_IP NEW_IP [options]
```

The IP tools must not classify, reconstruct, or validate MPC/MPCX license payloads. Utility-compatible IP writes include an unchanged settings prefix; they must not alter the values of license bytes.

Requirements:

- reader reports current/runtime and EEPROM/default network configuration;
- writer changes IP and, only when explicitly requested in the standalone CLI, TCP/UDP ports;
- EEPROM is the default write target;
- changing current/runtime IP requires an explicit option;
- writer performs read-back verification;
- after changing current/runtime IP or UDP port, reconnect to the new endpoint and require complete read-back verification;
- normal SiTCP and SiTCP-XG behavior must be tested independently.

## Testing

At minimum, test:

- C++11 builds with GCC and Clang where available;
- all five executables are built and installed by `make install`;
- MPC/MPCX classifier and verified EEPROM mappings remain unchanged;
- generation detection uses the documented SiTCP-XG Identifier;
- `mpc-mpcx-ip-command` subcommands and safety guards;
- standalone IP reader/writer do not depend on an MPC/MPCX file;
- EEPROM IP write read-back;
- current/runtime IP change followed by reconnect/read-back;
- normal SiTCP and SiTCP-XG independently.

Hardware-destructive tests should only be run on a controlled target where recovery is possible.

### Validation stages for the current options

The final pre-push run passed all 55 tests in 157.795 seconds after a
warning-enabled C++11 build/install. It includes read-only Check with/without a
file, exact native-style reports, mismatches and conflicting options, native
normal/XG forced-mode reference equality, forced split writes with EEPROM IP
override, and successful/failing 500 ms programming intervals. Existing Clear,
fallback, IP/port, protection and diagnostic tests also pass.

| Earlier stage | Result |
| --- | --- |
| Initial Check/force options | 52 tests passed, 96.978 seconds |
| Native file-report update | 54 tests passed, 88.419 seconds |
| First pacing run | Existing 54 passed; new test's fault target was outside its preservation write range |
| Corrected pacing fixture: forced initialization with split writes | All 9 writer-mode tests passed, 24.641 seconds; no production fix needed |
| Fileless native-report correction | All 9 writer-mode tests passed, 26.468 seconds |

These are local UDP simulator/reference tests, not additional physical test
cases. The new-mode and pacing sections above separately identify real-device
captures and restoration checks. No proprietary license is needed for the tests.

## Evidence summary

| Item | Public docs | Utility/static analysis | Hardware verification |
| --- | --- | --- | --- |
| MPC/MPCX RBCP access | yes | yes | yes |
| MPC/MPCX EEPROM FC00..FCFF | yes | yes | yes |
| MPC/MPCX payload exactly 22 bytes | not found | yes | yes |
| MPC/MPCX content classifier | not found | yes | yes |
| XG 16 + preserve 2 + 6 mapping | not found | yes | yes |
| normal 6 + 16 mapping | not found in reviewed material | investigated | yes |
| SiTCP-XG Identifier generation detection | yes | implemented | verified on XG hardware |
| Current/runtime IP/MAC read | register map | implemented | both generations |
| EEPROM/default IP/MAC read | register map | implemented | both generations |
| EEPROM IP write | guide distinguishes EEPROM access | native 17+40 sequence | both generations; XG actual IP change |
| EEPROM TCP/UDP port write | General-tab settings | native 17+40 sequence | both generations; actual port change |
| Runtime IP/UDP write and reconnect | current access described | captured sequence; simulator migration | normal SiTCP and updated AMANEQ XG verified; other firmware untested |

## Remaining work

### MPC/MPCX

- verify exact semantic meaning of all license bytes;
- investigate remaining reserved FC11 semantics; FC10 bit7 initialization
  selection is now supported by static analysis;
- compare the C++ readers/command against known hardware and the previous Python implementation.

### IP utility

- expand XG runtime migration and post-boot settings tests beyond the updated AMANEQ;
- investigate the normal-SiTCP power-cycle network outage and wire timing;
- extend native failure characterization beyond the observed enable-ACK loss.

## MPC/MPCX file inspection and MAC extraction

`mpc-mpcx-ip-command` uses `MPC_OR_MPCX_FILE` in help text instead of the ambiguous `FILE`. It means a 22-byte `.mpc` or `.mpcx` license/configuration file.

```text
mpc-mpcx-ip-command inspect MPC_OR_MPCX_FILE
mpc-mpcx-ip-command mac MPC_OR_MPCX_FILE
```

For verified payload layouts, the embedded MAC address is `payload[0:6]` for normal SiTCP/MPC and `payload[16:22]` for SiTCP-XG/MPCX. `inspect` reports the detected payload type, embedded MAC, and payload; `mac` reports the detected type and embedded MAC.

## Runtime / EEPROM diagnostic reports

Compact writer labels use `before: ` and `after:  ` to align MAC/IP fields.


The report labels current MAC, current IP, EEPROM MAC, and EEPROM IP in separate Runtime and EEPROM sections, followed by MPC/MPCX information reconstructed from EEPROM. Raw dumps use 16 hexadecimal bytes per row: four runtime rows for normal SiTCP, five for XG, and five EEPROM rows for either generation. MAC addresses use colon-separated hexadecimal notation. Numeric examples include `10000 (0x2710) Mbps` and `4660 (0x1234)`; timeout conversions retain units alongside decimal/hexadecimal raw values. Missing fields are displayed as `unavailable`, never decoded using placeholder zeros.


`src/sitcp-sitcpxg-register-report.hpp` supplies the common report used by the
MPC/MPCX reader and advanced `read` / `ip-read`. It reads runtime `0xFFFFFF00..0xFFFFFF3F` (64 bytes) for normal SiTCP or `0xFFFFFF00..0xFFFFFF4F`
(80 bytes) for SiTCP-XG, plus EEPROM `0xFFFFFC00..0xFFFFFC4F` (80 bytes) for both. Reads use
8-byte RBCP chunks and separate hex dumps. Identifier timeout aborts range
selection. The display and completion check use
the selected runtime length. MAC/IP values come directly from their region's registers, never
from reconstructed payloads. Generation detection still uses only FF08..FF0B.
The XG parameter decoder is shared by the two regions. Numeric register values
are decimal plus uppercase zero-padded hex; converted timeout units remain
visible. Register IP fields use the shared network helper to append eight
uppercase hexadecimal digits in network byte order (including zero padding),
e.g. `192.168.10.10 (0xC0A80A0A)`; this includes server and standalone IP views.
Out-of-range rates retain their raw value without claiming Mbps.
Normal SiTCP uses its own parameter decoder and raw dumps, never the XG map.

A diagnostic block bus error triggers byte-by-byte reads of that block. Each
rejected byte is marked unreadable and printed as `??`, with its address on
stderr. Only complete fields/payloads are decoded. This supports maps with
unreadable bytes within the selected range without suppressing other bytes
or EEPROM output. Normal SiTCP runtime FF40..FF4F is not requested. Short replies
and timeouts remain fatal and include the request address.

Read views return 3 for PARTIAL, 0 for COMPLETE, or 1 for fatal errors. Writers
use shared compact network snapshots (two lines before, two after, a blank separator, then
`Success! All operations completed and verified.`, followed by a blank line) instead of full diagnostic reads. They retain mandatory
programming/read-back verification and write-protection handling. Required
MPCX initialization still reads the complete runtime image. No writes to the
runtime tail are introduced.

Validation:

```bash
make
python3 tests/test_register_report.py
```

The tests use a local UDP RBCP simulator with synthetic data, checking all dump
bytes and source separation, both generations, decimal/hex rate and timeout
values, invalid rates, short reads, byte recovery after block bus errors,
unreadable runtime/EEPROM bytes, missing rate bytes, read-only traffic, and both
writer before/after views with EEPROM protection restored. They do not replace
physical-device validation. Python is needed only for these tests, not the CLI.

## MPCX initialization: source and limits (2026-09-26)

### EEPROM image layout

| EEPROM range | Source when initialization is needed |
| --- | --- |
| `FC00..FC0F` | MPCX file, first 16 bytes |
| `FC10..FC11` | Runtime `FF10..FF11` |
| `FC12..FC17` | MPCX file, final 6 bytes (MAC) |
| `FC18..FC4F` | Runtime `FF18..FF4F`, including the transmission rate |

Explicit EEPROM IP overrides are applied after programming; current/runtime IP changes are last, followed by reconnect and read-back verification. Without an EEPROM IP override, initialization saves the current runtime IP, which may be the device's ForceDefault address. It copies runtime values without automatic rate repair. Diagnostic `??` bytes must never be used as programming data. Normal MPC programming is unchanged.

### Evidence and implementation


Public guide: [SiTCP MPC Writer XG User Guide, section 3.3](https://www.bbtech.co.jp/download-files/sitcp/SiTCP-MPC-Writer-XG-en.0.1.1.pdf)
reports RAM-based initialization or built-in defaults depending on RAM access.
It does not define byte ranges or distinguish all internal write paths.
[SiTCP-XG manual, sections 4.1 and 6](https://www.bbtech.co.jp/download-files/sitcp/SiTCPXG_Manual_1.2_E_20201228.pdf)
maps runtime FF10..FF4F to EEPROM FC10..FC4F.

Static analysis used the official distribution
`sitcpmpcwritexg.win.0.4.1-2-gc782.zip`, downloaded from the BBT download page.
The SHA-256 of `SiTcpMpcWriteXG.exe` is
`0c01fa932830f74fc996dda56f81cea8c3fa11cd222d1b6f8f6212c0294294a4`.
The executable and disassembly are not repository deliverables.

Observed x86 virtual addresses:

- `0x40a0a0..0x40a0e0`: reads FC10 and returns bit7 as initialization state.
- `0x402fe7..0x40304f`: reads 80 bytes at FF00; records FC10 bit7 and
  checks the XG identifier in that RAM image.
- `0x403180..0x403224`: retains RAM for initialization; otherwise loads the
  80-byte EEPROM image. RAM read failure returns failure on this XG path.
- `0x408f81..0x40903a`: overlays 16 payload bytes at offset 0 and 6 at
  offset 0x12, selects 80 bytes when initializing versus 24 when preserving,
  and writes to FC00.
- `0x40928f..0x4093a6`: also attempts optional extension reads FF50..FF7F
  in 16-byte blocks and writes corresponding EEPROM blocks if readable.
  This extension behavior is now implemented; see the 2026-10-14 update below.
- The fixed-default branch at `0x407c7f..0x407cef` is in the legacy normal
  SiTCP writer: it reads 40 bytes at FF18, or uses a table at `0x417bc0`.
  That is not evidence for a SiTCP-XG fallback table. The earlier broad claim
  that the MPCX path always has a built-in default fallback was unsupported.

Implemented policy: for XG with FC10 bit7 set or explicit --initialize-eeprom,
obtain all 80 RAM bytes before any write, verify its identifier/reset state,
overlay the supplied MPCX file,
and write/verify FC00..FC4F. This includes the rate and reserved bytes in the
verified 80-byte copy; no rate normalization occurs. A failure to obtain the
image aborts before enabling writes. XG with bit7 clear and no forced option
retains the 24-byte path, even if the rate looks invalid. The later normal-MPC compatibility
update below is separate and does not change this MPCX initialization policy.
The writer and `mpcx-plan` share mandatory base-image preparation. The read-only
plan has no force option and does not preview forced initialization of an
already initialized record. It does not probe or predict optional extension
copies; writer-time reads determine those separately. `verify` still checks the
license payload only, whereas the writer verifies every byte it programs.

Additional safety differences from the official GUI are exact independent XG
identifier validation, runtime RESET-bit rejection, optional 16-byte write chunks,
mandatory read-back verification, and protection restoration on error. The
write-enable operation itself is inside the cleanup scope so a lost enable ACK
still triggers a protection attempt. No destructive write is retried.

Tests in `tests/test_mpcx_initialization.py` use synthetic payloads and local
UDP emulation: clear-then-write restoration of every image byte (including
FC40), preservation without initialization, bit7 selection, missing RAM,
RESET-bit rejection, type mismatch, explicit IP override order, failed/lost
write ACKs, lost enable ACK, and read-back mismatch. These are not real-hardware
verification or proof of complete equivalence to all official-tool versions.

## Generation-specific diagnostic range

The [SiTCP Internal Register Manual 1.0.2, table 3-1 (printed p.2)](https://www.bbtech.co.jp/download-files/sitcp/SiTCP_Register_Manual_1.0.2.pdf#page=5)
labels runtime +0x40..+0xFF as Access prohibited area. It does not guarantee
that reads always return bus errors. User-provided hardware output showed
normal SiTCP returning bus errors for FF40..FF4F while reading EEPROM
FC40..FC4F successfully; XG returned all 80 runtime bytes. The report now
selects 64 versus 80 bytes from device generation before reading. Both retain
80 EEPROM bytes, including the normal MPC license tail. Explicit low-level
`rbcp-read` and `probe` retain their caller-specified ranges. MPCX initialization
still requires its complete 80-byte runtime image; programming maps are unchanged.

Simulator tests reject the entire normal-SiTCP runtime tail and verify that
reader/advanced read/ip-read and writer diagnostics never request those bytes,
retain EEPROM FC40..FC4F, and report COMPLETE without expected-tail warnings.

## Writer clear-only mode

`mpc-mpcx-ip-writer IP --clear [--port N] [--timeout SEC]` is an explicit
standalone erase operation (default off), not clear-before-programming.
It requires no license file and rejects file/IP-change combinations before
network access. No RAM restoration or subsequent file programming is performed.
For the compact output format, see [Runtime / EEPROM diagnostic reports](#runtime--eeprom-diagnostic-reports).

Both writer `--clear` and advanced `clear IP --yes-really-clear` call the shared
`src/sitcp-sitcpxg-eeprom-clear.hpp` helper. It enables EEPROM writes, writes FF
to `0xFFFFFC00..0xFFFFFC7F` in 16-byte blocks, restores protection, then verifies all 128
bytes in 8-byte reads. An enable/write failure triggers a protection attempt;
no destructive data write is retried. Verification failure must never print the success message.
The advanced command retains its existing guard; writer `--clear` itself is
the explicit clear-only selector. The operation does not write runtime space.

`tests/test_writer_clear.py` covers both generations, exact write ranges and
sequence, unchanged runtime, conflict rejection before device access, failed
or lost ACKs, read-back mismatch, protection cleanup, and the advanced guard.

## Normal MPC: official writer comparison (2026-10-13)

The comparison used the locally installed official MPC Writer XG
0.4.1-2-gc782 (SHA-256 above), synthetic 22-byte files, a loopback-only RBCP
simulator on UDP 24660, and Npcap/dumpcap. No physical board was written and no
user license file was copied into the repository. The checked-in independent
references are `tests/reference/official_mpc_erased.json` and
`tests/reference/official_mpc_preserved.json`.

For a normal-SiTCP target with erased EEPROM and the GUI initialization checkbox
off, the actual official request sequence was:

| Operation | Address | Length/data |
| --- | --- | --- |
| Target detection | FFFFFF08 | read 4 bytes |
| Initialization status | FFFFFC10 | read 1 byte |
| Load normal record | FFFFFC10 | read 64 bytes |
| Obtain current configuration | FFFFFF18 | read 40 bytes |
| Enable writing | FFFFFCFF | write 00 |
| Program normal record | FFFFFC10 | write 64 bytes |
| Restore protection | FFFFFCFF | write FF, after dismissing the success dialog |

The separate Check button added an earlier identifier/status pair. RBCP request
IDs, source ports, and GUI pauses are transport details, not part of the image.
The custom writer retains extra MAC/IP snapshots and byte-read verification;
it restores protection before verification rather than leaving it enabled while
the success dialog waits for the user.
The captured normal writer waits approximately 500 ms between RBCP operations.
The custom normal-MPC path now retains a 500 ms interval after enable and data
writing, before protection cleanup following an ambiguous ACK, and after
protection before read-back. At that stage MPCX pacing/chunking was unchanged. This is
observed software behavior, not a claim that physical EEPROM settling was tested.

The captured data and narrowly scoped static analysis establish this normal
record layout:

| EEPROM bytes | Source |
| --- | --- |
| FC00..FC0F | untouched: outside the normal programming record |
| FC10 | always 01 |
| FC11 | retained from EEPROM in these successful-RAM/preservation captures; 00 in fixed fallback |
| FC12..FC17 | MPC payload[0:6] |
| FC18..FC3F | retained EEPROM, or runtime FF18..FF3F when initializing |
| FC40..FC4F | MPC payload[6:22] |
| FC50..FC7F | untouched |

The initialized-record capture retained FC11 and the EEPROM IP/ports/settings,
did not read runtime FF18/40, and still programmed control 01 with the same
64-byte FC10 write. Both captured final EEPROM images are regression fixtures.

At executable VA `0x4076d0..0x407c7f`, the legacy normal branch initializes
when **both** IP endpoint bytes FC18 and FC1B equal FF; it does not test that
all four bytes are FF and does not use the MPCX FC10-bit7 rule. VA
`0x407887..0x407913` sets control 01, overlays the payload, enables writes,
and programs one 64-byte record at FC10. Erased and initialized normal records
were both captured from the actual GUI. Partially erased IP endpoint cases
remain static-analysis evidence plus simulator tests, not hardware verification.

The previous implementation preserved erased settings/control and programmed
80 bytes at FC00. The independent capture-based test failed against that
implementation and passes after this correction. Generation detection now
precedes selecting the normal 64-byte versus XG 80-byte EEPROM read window.
At that comparison stage MPCX image preparation and its 16-byte write chunks
were unchanged; the later transfer-size option below supersedes the chunk default.

### Explicit compatibility limits

The official legacy normal branch at `0x407cac..0x407cef` substitutes a fixed
40-byte table at `0x417bc0` if runtime reading fails, including default EEPROM
IP 192.168.10.16. At that historical stage this custom tool deliberately **failed before enabling writes**
when FF18..FF3F cannot be obtained. It did not automatically substitute that
table or claim identical error/fallback behavior. The forced-initialization GUI
checkbox and legacy fallback were not exercised by this synthetic capture.
At that historical stage, XG optional extension copying was not implemented;
the later update implements it with simulator coverage.
At that stage physical EEPROM timing was not checked. Later actual captures
measure write-start timing. Normal-SiTCP reboot acceptance was subsequently
tested on 2026-10-15; other firmware variants remain outside that evidence.

### Normal-SiTCP fixed fallback settings (static evidence)

The installed native Writer 0.4.1-2-gc782 table at VA 0x417BC0 contains 40
bytes used for FC18..FC3F if the normal initialization RAM read fails.
Decoded values below use the normal-SiTCP register map. This failure branch
has not been exercised on hardware; the current custom writer uses this table by default; --no-fallback stops instead.

| Setting | Native fixed value |
| --- | --- |
| IP | 192.168.10.16 |
| TCP data port / command port | 24 / 23 |
| UDP/RBCP port | 4660 |
| Maximum segment size | 1460 bytes |
| Keep Alive buffer nonempty / empty | 1000 / 60000 ms |
| Connect / disconnect timeout | 5000 / 2880000 ms |
| Reconnect / retransmission timer | 500 / 500 ms |

MAC/license overlays still come from the MPC file. This table is not evidence
of an XG fallback and is never reused for XG initialization.

### MPCX regression capture

The actual official XG erased-record branch read FF00/80, wrote FC00/80,
attempted the optional extension reads at FF50, FF60 and FF70 (16 bytes each),
and restored protection. The simulator rejected those extension reads; the
GUI reported that the extension areas could not be read. Its confirmation
message used the phrase "default values", but the actual captured FC10..FC11
and FC18..FC4F bytes came directly from the supplied runtime image, including
its unusual rate bytes. The protocol bytes, not that generic label, establish
the image behavior. `tests/reference/official_mpcx_erased.json` independently
checks the custom MPCX image against that capture. At that stage the custom
XG path used 16-byte chunks. The current default is a single 80-byte transfer
when initializing; see the later bulk-default update.

## Official SiTCP Utility 0.9.0 observation (2026-10-13)

The local `SiTCPUtility.exe` SHA-256 is
`1b50bddb09a84f3adeddd1ef26ac78b3f91a8ba2f1d014e661ab56562d197b72`.
The general tab was exercised against the same normal-SiTCP loopback simulator.
The official user guide distinguishes current-memory access (EEPROM checkbox
off) from EEPROM access (on), and recommends EEPROM programming followed by
reboot when changing the device's network settings:
[SiTCP Utility guide, sections 2.1.3–2.1.5](https://www.bbtech.co.jp/download-files/sitcp/SiTCPUtilityUserGuide.0.9.pdf).

Actual captured operations, with TCP/UDP values retained in the simulator:

| General-tab operation | Actual requests |
| --- | --- |
| Read current settings | read FF00, 64 bytes |
| Read EEPROM settings | read FC00, 64 bytes |
| Write EEPROM settings | read FC00/64; enable FCFF=00; write FC00/17; write FC18/40; protect FCFF=FF |
| Write current settings | two reads FF00/64; write FF00/17; write FF18/40; no EEPROM enable write |

The runtime GUI also changes its target UDP port to the newly selected UDP
setting. No real address transition was tested: the runtime comparison kept
127.0.0.1 and the simulator's existing settings, so it cannot establish physical
IP migration or lost-ACK behavior.

At the user's request, IP writing now follows these captured general-tab block
sequences: read the complete 64-byte settings image (twice for runtime), retain
all non-IP values, then write the 17-byte prefix and 40-byte parameter block.
FC11..FC17 / FF11..FF17 are not written. EEPROM FC00..FC0F is written back
unchanged, including any MPCX license bytes; no license parsing is performed.
EEPROM protection is restored before a complete 64-byte read-back comparison.
Runtime prefix failures stop immediately; only a timeout of the final, address-
changing block is followed by verification at the new IP, without retrying the
write. At that stage ports remained unchanged; standalone port options were added in the later update below.
The existing before/after snapshots and added read-back make the complete
CLI traffic longer than the GUI trace; the configuration-write sequence matches.
An enable-ACK timeout now triggers a protection-restoration attempt in the
EEPROM IP helper, matching the cleanup guarantee already used by the MPC writer.
The proprietary utility and disassembly are not repository deliverables.

### Validation environment

Baseline: 23 pre-existing tests passed under a private Cygwin GCC C++11 build.
The capture-based normal-MPC test failed before the fix. The expanded suite
covers the reference image, initialization/preservation conditions, no writes
after unreadable RAM, lost enable/data ACKs, read-back mismatch, write protection,
IP override order, and existing MPCX/reader/clear behavior. No proprietary data
is needed to run it:

```bash
make
python3 -m unittest discover -s tests -v
```

On the Windows validation host, Cygwin needs its POSIX declarations enabled in
strict C++11 mode. The build used the following override without changing the
Linux/macOS/WSL defaults:

```bash
make CXXFLAGS="-O2 -std=c++11 -D_POSIX_C_SOURCE=200112L -Wall -Wextra -Wpedantic"
```

Validation before the Utility-compatible IP update: GCC 14.4.0, strict C++11, all 32 integration tests passed.
`make install` rebuilt/copied all five public commands locally. Their help
startup checks passed after correcting the IP-only writer's pre-existing
`--help` exit-code error (help now exits 0; missing required arguments still
exit 2). The official GUI target/file settings were restored and all loopback
simulator/capture processes stopped. SiTCP Utility's on-screen result/log area
still contains the synthetic test results, not readings from a physical board.

### Utility-compatible IP update validation

The independent `tests/reference/official_utility_ip.json` fixture is extracted
from the previously captured official GUI synthetic-device trace. Tests compare
every configuration-write address and payload, including enable/protect, for
normal SiTCP and XG. They also check unchanged MAC, ports, control, license and
unwritten regions, complete-read failure before writes, protection restoration,
no destructive retry, and full-image mismatch detection. The runtime timeout
test retains localhost; it does not establish real-device address migration.
The shared helper also applies to IP overrides after MPC/MPCX programming and
the advanced IP-write command. Extra before/after reads and read-back remain.
GCC 14.4.0 strict C++11 build/install completed without warnings; all 36
integration tests passed (34.901 seconds). No physical device was written and
no GitHub commit or push was performed.

## Reader settings display (2026-10-13)

The MPC/MPCX reader and advanced `read` / `ip-read` share a generation-aware
settings display. General IP/TCP/UDP settings precede TCP timers, client/server
settings, control flags and transmission settings. This organization follows
the official Utility's general/settings conventions while retaining separate
runtime and EEPROM regions, decimal/hex values, raw dumps and bus-error markers.
It is a CLI presentation, not a reproduction of the graphical interface.

Normal decoding is based on [SiTCP Register Manual 1.0.2](https://www.bbtech.co.jp/download-files/sitcp/SiTCP_Register_Manual_1.0.2.pdf),
sections 3.7--3.19; XG decoding uses [SiTCP-XG Manual 1.8.1](https://www.bbtech.co.jp/download-files/sitcp/SiTCPXG_Manual_1.8.1.pdf),
sections 4.2.5--4.2.20. The [Utility guide](https://www.bbtech.co.jp/download-files/sitcp/SiTCPUtilityUserGuide.0.9.pdf)
provides the general IP/TCP/UDP terminology. Key generation differences:

| Field | Normal SiTCP | SiTCP-XG |
| --- | --- | --- |
| TCP sub port | +1E, displayed | Not defined, omitted |
| Disconnect timeout | N*256 ms | (N+1)*256 ms |
| +2C timer | Reconnect interval, N ms | MSL, N*0.5 ms |
| Server MAC/IP/port | +30/+36/+3A | +32/+38/+3C |
| Control flags | ARP, duplicate ACK, MIF, flow control, keepalive, fast retransmission, Nagle, reset | Window scaling, keepalive, fast retransmission, Nagle, reset |
| Transmission-rate setting | Unsupported; no FF40 access or FC40 license decoding | +40, configured line-rate limit in Mbps |

Both regions are decoded from their own readable bytes. An unsupported rate
setting does not establish the negotiated link speed; no PHY interrogation or
throughput benchmark was added. No device writes are performed by the reader.
Tests use known differing server addresses, timers and control values to catch
accidental reuse of the XG map, and an unreadable normal UDP byte to verify that
partial fields are not converted into invented values.

Validation: all 38 integration tests passed (37.564 s). After the final General
heading adjustment, build/install and all 13 register-report tests passed
(7.658 s). The two published reader examples are actual CLI output obtained
from synthetic localhost registers, explicitly labeled as such. Physical
hardware was not accessed; no GitHub changes were made.



### Official Utility parameter labels

Confirmed English label strings in the installed official SiTCP Utility 0.9.0
include TCP Keep Alive Enabled, TCP Keep Alive(buffer not empty), TCP Keep
Alive(buffer empty), TCP Max Segment Size, TCP Timeout(Connecting), TCP
Timeout(Disconnect), TCP Re-Connect Interval, TCP Re-Transmition Timer,
TCP Command Port, TCP Port and UDP Port. These labels are used in the reader;
the official spelling of Re-Transmition is retained. This is static label
evidence, not a new hardware measurement or proof of exact GUI layout.
Keep Alive Enabled precedes its two timer values in TCP settings, making the
switch and interval distinction explicit. Parameter columns allow 36 characters
to align the longer official labels. Decimal/hex, units, time conversions,
generation-specific decoding, raw dumps and partial-read handling are retained.
After this label update, the strict C++11 build/install and all 38 tests passed
(37.463 s). Synthetic reader examples were refreshed from the rebuilt reader.
The Utility-compatible parameter block has a blank line before its TCP Port
entry and after its final entry, separating it from MAC/IP and raw dumps in
both runtime and EEPROM displays. No fields or raw bytes were removed.

## Clear write pacing: official comparison and update

Official Writer 0.4.1-2-gc782 was exercised on normal SiTCP at 192.168.10.16.
Its captured clear sequence matches this repository's erase addresses, sizes
and values: FCFF=00, eight 16-byte FF writes over FC00..FC7F, then FCFF=FF.
All ten write ACKs succeeded, and an independent read confirmed 128 erased
bytes. The selected MPC and all 128 pre-clear bytes were restored afterward;
runtime stayed unchanged and 100 subsequent pings succeeded. License-bearing
backups and captures remain private and are not repository contents.

The official write-start gaps were 502.6--516.2 ms. The previous repository
clear immediately proceeded after ACKs: about 183--184 ms on that device.
Clear was changed to use steady_clock and sleep_until to schedule at least
500 ms between client write starts, including enable and protection writes.
The later 2026-10-15 capture measured shorter wire gaps, so this is not a verified
500 ms wire guarantee; see the current timing qualification above. Device ACK time
counts toward the 500 ms; slow ACKs do not cause an additional full 500 ms wait.
Failure cleanup uses the same pacing without retrying erase writes.
Mandatory 128-byte read-back remains; official read-back was not observed
during erase or within two seconds after protection in this successful capture.
Failure/lost-ACK behavior of the official GUI and power-cycle acceptance were
not tested. At that stage only the earlier version had been exercised on hardware; the new pacing
is checked by simulator timing assertions for both generations and failure paths.
Validation after the pacing update: strict C++11 build/install succeeded and
all 38 tests passed in 68.252 seconds. The installed local binaries include
the pacing update. No additional physical clear was performed at that stage; later XG comparison used the updated clear implementation.

## MPC/MPCX bulk default and explicit chunks

At the user's request, the programming transfer defaults to one complete
prepared image: normal MPC 64 bytes at FC10, preservation MPCX 24 bytes at
FC00, and initialization MPCX 80 bytes at FC00. The preservation MPCX image
is not enlarged merely to reach 80 bytes; unmodified configuration remains
outside its programming range. Existing generation/initialization validation
and byte construction are unchanged.

`--write-chunk-size official` explicitly selects the default whole-image lengths.
Otherwise `--write-chunk-size N` accepts a positive decimal integer, 1..255 bytes;
16 reproduces the previous MPCX split mode (24 bytes becomes 16+8, 80 bytes
becomes five 16-byte writes). Normal MPC 64 bytes becomes four 16-byte writes.
Both modes verify every programmed byte and restore protection after failures
without retrying data writes. The high-level wrapper forwards the value before
its IP overrides. Invalid options and clear/size combinations fail before
network reads. IP transfer sizes and fixed clear blocks/pacing are unaffected.

Tests compare bulk and split addresses, lengths, concatenated payloads and
final EEPROM images for all three image sizes. Bulk and split failures test
protection cleanup and no retries. The official erased-MPCX synthetic fixture
also checks the default FC00/80 transfer. No new physical-device writes are
performed as part of this option validation.
Strict C++11 build/install and all 41 tests passed (64.481 seconds). Both
bulk and split failures preserve the protection/no-retry guarantees.

## XG physical comparison: preservation and erased initialization (2026-10-14)

An XG device and its matching licensed MPCX file were tested using official
Writer 0.4.1-2-gc782 and the current bulk-default CLI. All 128 EEPROM bytes and
80 runtime bytes were backed up privately. The native preservation path and
the CLI both wrote FCFF=00, FC00/24, FCFF=FF, with identical data and unchanged
final EEPROM. This directly confirms that the initialized preservation image
is 24 bytes, not an unconditional 80-byte write.

For initialization, both runs began with all 128 EEPROM bytes erased. Native
Initialize EEPROM wrote FC00/80 containing RAM FF00..FF4F overlaid with the
MPCX payload at FC00..FC0F and MAC at FC12..FC17. The CLI's default FC00/80
write matched native addresses, lengths and payload exactly; all 128 resulting
EEPROM bytes matched. Control and settings were copied from RAM, including
the tested 10000-Mbps configured rate. Runtime remained unchanged.

Native initialization attempted three 16-byte reads at FF50, FF60 and FF70.
Each returned RBCP C9 bus error with zero length. The GUI reported successful
programming plus three extension-read warnings; no extension EEPROM write
occurred. The CLI used for this physical comparison skipped these optional reads. FC50..FC7F stayed FF after clear
in both runs. This establishes only the inaccessible-extension case; a device
with readable optional extensions was not covered by that CLI version; the current synthetic coverage is described below.

Pacing remains different: native preservation write-start intervals were
509.1 and 512.6 ms; CLI intervals were 3.3 and 265.2 ms. Native initialization
enable-to-data was 515.0 ms, versus CLI 2.3 ms. Data-to-protect was 2530.5 ms
native (including optional reads) and 881.9 ms CLI. Device ACK time accounts
for much of the CLI data interval. Do not claim packet-for-packet timing
equivalence or apply the measured clear pacing to XG programming implicitly.

Initialization completed with 100/100 successful pings. All 128 pre-test EEPROM
bytes and runtime were restored; final ping was also 100/100. No power cycle or
native failure/lost-ACK test was performed. UI initialization was disabled at
completion. Actual licensed payloads, captures and backup images remain in
private working storage, outside this repository. Capture selection was
corrected to the actual route before the successful packet comparison.


## Consolidated verification and optional-extension update (2026-10-14)

The following records the 2026-10-14 evidence stage, separating actual hardware
evidence from synthetic failure tests. Its limits are historical; the current
2026-10-15 summary above includes later boot/ACK-loss tests and wire timing.
Official versions: MPC Writer XG 0.4.1-2-gc782 and Utility 0.9.0.

| Operation | Evidence and result | Remaining limits |
| --- | --- | --- |
| Normal MPC | Actual device: full prepared FC10/64 record verified; native synthetic record agrees; control FF became 01, license preserved; ping 100/100 | No power-cycle test; previous ping instability was not reproduced |
| Normal clear | Both actual tools erase FC00..7F as eight 16-byte FF blocks; native gaps 502.6–516.2 ms; full restoration and ping 100/100 | Native failure/lost-ACK behavior untested |
| Clear pacing update | Monotonic minimum 500 ms between write starts; subsequently used during actual XG comparison | Simulated failures test cleanup pacing; no deliberate hardware communication failure |
| Utility EEPROM IP | Actual native and custom same-value write: enable, FC00/17, FC18/40, protect agree byte-for-byte; all 128 bytes preserved; ping 100/100 | Native/custom comparison did not migrate the active runtime IP |
| Custom EEPROM IP | Actual default IP changed to the runtime IP; only two differing IP bytes changed; RAM unchanged; ping 100/100 | No power-cycle verification |
| XG preservation | Actual native/custom FC00/24 data and final 128 EEPROM bytes agree | Native ~500-ms pacing differs from custom ACK-paced programming |
| XG initialization | Both begin erased; actual FC00/80 data and all final 128 bytes agree; RAM unchanged, configured rate 10000 retained; ping 100/100 and complete restoration | Additional FF50/60/70 reads all returned C9 with zero length; readable extension hardware untested |
| Reader | Synthetic register maps, decimal/hex, raw bytes, partial bus-error recovery and native label comparison | Reported transmission rate is a setting, not measured throughput |

Earlier EEPROM FF counts are recorded in the sanitized old-ff-summary.json.
Normal EEPROM had 54 FF bytes in its 80-byte view, including unset settings;
this is an observation, not proof of the cause of historical ping loss.
TCP Keep Alive affects TCP sessions and does not explain ICMP ping directly.
Actual licensed captures and backups are private and excluded from Git and
public archives. Sanitized summaries are delivered alongside this repository.
XG capture was repeated on the actual Wi-Fi route after an initial incorrect
interface selection; only the corrected capture supports packet comparisons.

### Current optional extension policy

Only XG initialization (FC10 bit7 set or explicit --initialize-eeprom) attempts
FF50, FF60, FF70, each 16 bytes,
after programming the mandatory 80-byte image, before restoring protection.
Each completely read block is copied to FC50, FC60, FC70 respectively. A bus
error, exhausted read timeout, short reply or other transport read failure
skips that source block; no fabricated bytes or erase is substituted. Other
blocks are still tried. Preservation MPCX and normal MPC never copy extensions.
The meanings of these optional registers remain unidentified; raw copying
follows observed native behavior, without decoding or assigning guessed names.
Success output remains unchanged. A destination write failure is fatal, causes
protection cleanup, and is never retried. Every copied block is read back after
protection; a mismatch or failed verification prevents success. Explicit chunk
size applies to extension data too, defaulting to a whole 16-byte block.
This new behavior is validated synthetically for readable, partially readable,
bus-error, short-reply and timeout sources, and ambiguous extension-write ACK.
At that update stage it had not been rerun on real hardware; prior real tests
used the version which skipped optional reads. The subsequent updated-AMANEQ
XG suite at the top verifies current inaccessible-extension behavior on hardware;
readable sources still have only synthetic coverage.

### Unreachable targets and ambiguous operations

Shared transport validates a finite timeout in (0, 86400] seconds. UDP sockets
are connected to the resolved peer, filtering responses from other endpoints
and allowing available network errors to be surfaced. Resolution, send and
receive failures identify the target; no response produces a bounded timeout.
Read timeouts may be retried up to three times per read, not indefinitely.
Initial snapshot or generation detection failure stops before enabling writes.
A successful snapshot does not guarantee the device stays reachable: later
write failures still require best-effort protection restoration, no destructive
retry, and no success message. Protection cannot be guaranteed if the network
remains down. Optional XG source failures are tolerated only for extension reads;
mandatory XG base-image reads and final verification remain fatal. Normal MPC
now has its separately documented initialization fallback unless --no-fallback
is supplied; it cannot bypass initial snapshots or generation/EEPROM reads. No-response
writer tests verify a nonzero exit, bounded completion and zero write packets.


Validation at the optional-extension/transport update stage: strict C++11 build/install passed; all 43 integration tests passed in 66.123 seconds. The subsequent port update passed 45 tests, as noted below. This records validation before the subsequent port update.

## Physical XG EEPROM IP rewrite comparison (2026-10-14)

Official SiTCP Utility 0.9.0 and the current standalone IP writer were tested
on the XG device at 192.168.2.187, MAC 7C:F0:98:01:21:F0. EEPROM IP was changed
to 192.168.2.188 while runtime remained at 192.168.2.187. TCP data port 24 and
UDP port 4660 were retained. This is an actual address change, not a same-value
write. Complete 128-byte EEPROM and 80-byte runtime backups were saved privately.

Native Utility changed only the requested IP in the expected full image.
The baseline was restored before repeating the change with the custom writer.
Native and custom resulting EEPROM images matched across all 128 bytes; all
runtime bytes remained unchanged. Captured write addresses, lengths and payloads
matched exactly: FCFF/1 enable=00, FC00/17, FC18/40, FCFF/1 protect=FF.
Native write-start gaps were 2.3, 188.5, 440.6 ms; custom gaps were 2.9, 192.8,
442.1 ms. This confirms the Utility-compatible sequence on this XG hardware;
it does not establish exact equality of all reads, GUI traffic or timing.

EEPROM was finally restored to 192.168.2.187, with all 128 bytes identical to
the original backup and all 80 runtime bytes unchanged. Final ping: 100 sent,
100 received, zero loss, maximum RTT 9 ms. The Utility write field and read
result were refreshed to the restored IP. No clear, license programming,
runtime IP migration, reset or power cycle was performed. Raw licensed captures
remain private. Sanitized evidence: ../xg-utility-ip-test.json.

Utility 0.9.0 displayed normal-style TCP Command Port and Re-Connect labels
on this XG device; successful write compatibility does not validate its XG
parameter decoding. Our generation-specific reader map remains separate.


## Closer standalone IP Utility behavior (2026-10-14)

The verified native IP-write sequence was already implemented for normal SiTCP
and XG. This update adds the native General tab's configurable TCP data port
and UDP port to the standalone CLI via --tcp-port / --udp-port. Existing calls
remain IP-only; omitted options preserve the read settings. --port still means
the current RBCP transport destination. MPC wrapper IP operations and advanced
ip-write continue to preserve ports through default helper arguments.

Only explicitly selected bytes are changed: IP 18..1B, TCP data port 1C..1D,
UDP/RBCP port 22..23. Shared helpers keep EEPROM FC00/64 read, enable, FC00/17,
FC18/40, protect, complete 64-byte verification; runtime retains two FF00/64
reads, FF00/17 and FF18/40 writes. There is no added 500-ms delay: actual native
Utility captures progress with ACKs, unlike native MPC Writer pacing.
Runtime UDP changes reconnect and verify at the new IP/UDP endpoint, then use
that endpoint for the compact after snapshot. EEPROM port changes verify via
the unchanged runtime endpoint. Invalid IP/port options fail before network
access. No default-address fallback is introduced: no such Utility failure
behavior has been established. Protection cleanup, no destructive retries and
mandatory verification remain intentional safeguards. Compact output unchanged.

Synthetic tests cover both generations and destinations, full preservation of
all nonselected bytes, native write lengths, and a mock device actually moving
its UDP socket after the runtime parameters write. Invalid port values and
malformed IPs are rejected without any device request. At this implementation stage, new port-changing paths were simulator-only.
The following physical comparison subsequently verified EEPROM port changes
on both generations. At that stage runtime endpoint migration remained
simulator-only; normal-SiTCP migration was subsequently verified on 2026-10-15.
Validation: strict C++11 build/install passed and all 45 integration tests passed in 73.342 seconds. Local installed binaries include the validated changes; publication revision is recorded in Git history.

## Physical EEPROM TCP/UDP port comparison on both generations (2026-10-14)

Official Utility 0.9.0 and the current standalone IP writer changed EEPROM
TCP data port 24 to 25 and UDP/RBCP port 4660 to 4661, with IP unchanged,
on normal SiTCP at 192.168.10.16 and SiTCP-XG at 192.168.2.187. Each device
had a private 128-byte EEPROM backup and a complete runtime backup (64 normal,
80 XG). Baseline was restored before the custom test, making the two starting
states identical. Only requested TCP/UDP bytes changed; MAC, IP, license and
all other settings were preserved. All 128 resulting bytes agreed between
native Utility and the custom writer on both devices.

Actual captures agree on all four write addresses, lengths and payloads:
FCFF/1=00, FC00/17, FC18/40, FCFF/1=FF. Write-start gaps in milliseconds:

| Device | Native | Custom |
| --- | --- | --- |
| Normal SiTCP | 0.4, 195.2, 457.1 | 1.8, 198.8, 462.3 |
| SiTCP-XG | 1.6, 188.6, 444.2 | 1.7, 188.7, 442.2 |

All runtime bytes remained unchanged. Both EEPROM images were fully restored
to their original 128 bytes, including TCP 24 and UDP 4660. Final ping was
100/100 on each device; maximum RTT was 14 ms normal and 5 ms XG. Captures
used the actual Ethernet/Wi-Fi routes and were stopped after comparison.
Sanitized summaries: ../normal-utility-port-test.json and
../xg-utility-port-test.json. Licensed capture bytes and backups remain private.

This verifies EEPROM port storage and native write compatibility. Runtime
port migration, TCP data transfer on the new port and power-cycle loading of
the changed EEPROM ports were not tested. Earlier statements that optional
port editing was only simulator-tested refer to the pre-test implementation;
EEPROM port changes now have direct hardware evidence on both generations.


## Documentation organization (2026-10-14)

README.md and README.ja.md contain installation, usage, CLI defaults, option
semantics, visible output and warnings needed to operate the tools. TCP/UDP port
examples are in the README appendix; transfer-size examples remain in CLI help
and this developer guide, not README. Protocol block sizes,
register maps, clear timing, optional extension rules, native comparisons,
failure semantics and test evidence remain in the technical sections above.
MPC/MPCX selection is based on the 22-byte payload, never its filename suffix.
The source and verified hardware behavior were not changed by this cleanup.


## Standalone IP writer usage reference

TCP/UDP port option descriptions and examples are in the README appendix
([English](README.md#tcpudp-port-options), [Japanese](README.ja.md#tcpudpポートの指定)).
Protocol sequences and verification evidence remain in the technical sections above.
