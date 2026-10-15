# SiTCP / SiTCP-XG MPC / MPCX / IP Utility (first trial)

**Language: [English](README.md) | 日本語**

RBCPを使ってSiTCP / SiTCP-XGを設定する、試験的なC++11ユーティリティです。

## コマンド

インストールされるコマンドは次の5つです。

- `mpc-mpcx-ip-writer` — MPC/MPCXのEEPROMデータを書き込み、必要に応じてEEPROMと現在のIPアドレスを変更します。
- `mpc-mpcx-ip-reader` — MPC/MPCX情報を読み取り、現在とEEPROMのMAC/IPアドレスを表示します。
- `mpc-mpcx-ip-command` — MPC/MPCX、IP設定、低レベルRBCP操作の詳細コマンドです。
- `sitcp-sitcpxg-ip-writer` — SiTCP / SiTCP-XGのIPアドレスを設定します。
- `sitcp-sitcpxg-ip-reader` — SiTCP / SiTCP-XGのIP設定専用readerです。

## インストール

```bash
git clone https://github.com/nobukoba/sitcp-sitcpxg-mpc-mpcx-ip-utility-first-trial.git
cd sitcp-sitcpxg-mpc-mpcx-ip-utility-first-trial
make
make install
```

`make install`で実行ファイルが`./bin/`にコピーされます。

## writerの使い方

MPC/MPCXファイルを装置に書き込みます。

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx
```

ファイルを書き込み、EEPROMに保存するIPアドレスも設定します。

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx \
  --set-eeprom-ip 192.168.2.170
```

ファイルを書き込まず、EEPROMの消去だけを行います。

```bash
./bin/mpc-mpcx-ip-writer 192.168.10.10 --clear
```

`--clear`は保存されたライセンスと設定を消去します。ファイルやIP変更オプションと組み合わせず、単独で使用してください。通常の使用に戻す前に、適切なライセンスを再書き込みしてください。

## readerの使い方

```bash
./bin/mpc-mpcx-ip-reader 192.168.2.161
```

ランタイムとEEPROMの内容を分けて表示します。MAC/IPアドレスとMPC/MPCX情報を確認できます。表示の詳細は[表示と終了コード](#readerの表示と終了コード)を参照してください。

## IP設定専用コマンドの使い方

MPC/MPCXファイルを使用せず、SiTCP / SiTCP-XGのIP設定だけを扱う場合に使用します。

```bash
./bin/sitcp-sitcpxg-ip-reader 192.168.2.161
./bin/sitcp-sitcpxg-ip-writer 192.168.2.161 192.168.2.170
```

MPC/MPCXファイルは不要です。既定ではEEPROMだけを変更します。現在のIPを変更する場合は
`--current`を指定してください。指定していない設定とライセンスは保持します。

## 詳細コマンドの使い方

```bash
./bin/mpc-mpcx-ip-command --help
```

診断や低レベル操作については[開発者ガイドのコマンド一覧](FOR_DEVELOPERS.md#advanced-command-reference)を参照してください。

## 付録

### writerのオプションと動作

```text
mpc-mpcx-ip-writer CURRENT_IP MPC_OR_MPCX_FILE [options]
mpc-mpcx-ip-writer CURRENT_IP --clear [--port N] [--timeout SEC]
mpc-mpcx-ip-writer CURRENT_IP [MPC_OR_MPCX_FILE] --check [--port N] [--timeout SEC]
```

MPC/MPCX情報を書き込み、現在のランタイムIPも設定します。

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx \
  --set-current-ip 192.168.2.170
```

EEPROMの既定IPと現在のランタイムIPの両方を設定します。

```bash
./bin/mpc-mpcx-ip-writer 192.168.2.161 FILE.mpcx \
  --set-eeprom-ip 192.168.2.170 \
  --set-current-ip 192.168.2.170
```

RBCPの既定UDPポートは`4660`、タイムアウトは`3`秒です。`--help`にも既定値が表示されます。

主なオプションです。全オプションは`--help`で確認できます。

| オプション | 内容 |
| --- | --- |
| `--clear` | EEPROM消去のみ。ファイル書き込みやIP変更なし（既定: 無効） |
| `--check` | 読み取り専用の機器・状態確認。ファイル指定時は種類も照合（既定: 無効） |
| `--initialize-eeprom` | XGを強制初期化。通常MPCの動作は変更しない（既定: 無効） |
| `--set-eeprom-ip IP` | EEPROMの既定IPを設定 |
| `--set-current-ip IP` | 現在のランタイムIPを設定 |
| `--no-fallback` | 通常MPC初期化のRAM読み取り失敗時に停止（既定: 無効） |
| `--port N` | RBCP UDPポート（既定: 4660） |
| `--timeout SEC` | RBCPタイムアウト秒数（既定: 3） |
| `-h, --help` | ヘルプを表示 |

両方のIPオプションを指定すると、EEPROMのIPを先に設定し、現在のIPを最後に変更します。変更後のIPへ再接続して検証します。

ファイル書き込みとClearは変更前後のランタイム/EEPROMのMAC・IPを表示し、すべての操作と検証が完了すると成功を表示します。Checkは後述の読み取り専用表示を使います。全レジスタのダンプはreaderで確認してください。

### CheckとInitialize EEPROM：正規GUIとの対応

`--check`は正規Writerの**Check**ボタンに対応し、機器の世代とEEPROMの状態フラグを読み取ります。
ファイル指定時はファイルも分類し、MPC/MPCXの世代が機器と一致するか確認します。書き込みは送信しません。
CLIも検証した正規GUIも、ファイルを省略してCheckを実行できます。
正常時は正規GUIと同じ文言・行順で、`MPC(X) File`、`Interface`、`Device`、EEPROM初期化状態を表示します。
ファイルなしでは`MPC(X) File : Not Selected.`を表示し、Interfaceと一致判定は省略します。
ライセンス内容の検証やEEPROM全体の比較ではありません。表示する状態フラグは、通常MPCの
自動初期化判定そのものではありません。この違いは技術文書に記載しています。

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP --check
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --check
```

Checkの終了コードは、読み取り成功かつファイル指定時に種類が一致すれば0、ファイルと機器の世代が
不一致なら7、読み取り・ファイル・オプションのエラーは1です。
Clear、初期化、IP変更、書き込み用オプションとは併用できません。

`--initialize-eeprom`は、正規GUIの**Initialize EEPROM**にチェックを入れ、**Write MPC(X)**を
押す操作に対応します。ファイルが必要です。XGでは初期化済みでも、現在のRAM設定に選択した
MPCXライセンス・MACを重ねてEEPROMへ保存します。以前の保存IPが現在のIPに置き換わる場合があります。
ClearのようにEEPROM全体をFFで消去する操作ではなく、現在のRAM設定も直ちには変わりません。
必須のXG RAMを読めない場合は停止し、固定値にはフォールバックしません。

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx --initialize-eeprom
```

検証した正規版では、通常SiTCPの初期化済みMPCに対しては、チェックを入れても強制初期化されませんでした。
CLIもこれに合わせ、このフラグは通常MPCの動作を変更しません。従来の自動初期化・フォールバックが適用されます。
新しい2オプションは`--clear`と併用できません。初期化後の保存IP・現在IPには既存のIP変更オプションを
使用でき、ファイル書き込み後に実行されます。CLIに追加の確認ダイアログはありません。
レジスタ上の根拠、失敗時の動作、検証範囲は[オプションの詳細](FOR_DEVELOPERS.md#check-and-forced-initialization-options)を参照してください。

### TCP/UDPポートの指定

単独IPライターでIP、TCPデータポート、UDP/RBCPポートをまとめて設定できます。

```bash
./bin/sitcp-sitcpxg-ip-writer 192.168.2.187 192.168.2.188 --eeprom --tcp-port 24 --udp-port 4660
```

`--tcp-port N`と`--udp-port N`は1～65535を指定でき、省略時は既存値を保持します。
`--port N`は現在の通信先ポート（既定4660）で、保存するポートの変更指定ではありません。
`--current`では変更先IPと指定したUDPポートで検証します。EEPROM変更の場合は現在の
通信先を維持します。その他の設定とライセンスを保持し、出力書式も維持します。
これらのポート指定は単独IPライターのオプションです。

### 通常SiTCPのMPC書き込み

EEPROMのIPが未初期化レコードを示す場合は、現在のネットワーク設定を復元して
MPCを書き込みます。それ以外ではEEPROMの設定を維持します。初期化で保存される
IPは、設定を読み取れた場合は現在のランタイムIPです。読み取れない場合は既定で、
保存IPが`192.168.10.16`となる正規版の固定設定を使用します。`--no-fallback`を指定すると書き込み前に停止します。
別のIPを保存する場合は`--set-eeprom-ip`を指定してください。MPC書き込み成功後に自動で変更します。
[追加オプションの詳細](FOR_DEVELOPERS.md#additional-options-reference)と
[正規版との比較](FOR_DEVELOPERS.md#normal-mpc-fallback-native-execution-recheck-2026-10-15)を参照してください。

### EEPROM消去後のMPCX書き込み

書き込み前に、基本MPCXデータの変更予定を確認できます。

```bash
./bin/mpc-mpcx-ip-command mpcx-plan DEVICE_IP FILE.mpcx
```

確認後に書き込みます。

```bash
./bin/mpc-mpcx-ip-writer DEVICE_IP FILE.mpcx
```

初期化で保存されるEEPROM IPは現在のランタイムIPです。別のIPを保存する場合は`--set-eeprom-ip`を指定してください。必要な設定を完全に読み取れない場合は、書き込み前に停止します。初期化条件、コピー範囲、公式ツールとの差異は[開発者ガイド](FOR_DEVELOPERS.md#mpcx-initialization-source-and-limits-2026-09-26)を参照してください。

### readerの表示と終了コード

ランタイムとEEPROMのMAC/IP、MPC/MPCX情報を分けて表示します。`??`は読み取れなかったバイト、`unavailable`は必要なデータが揃わない項目です。

| 終了コード | 意味 |
| --- | --- |
| `0` | 完全な読み取り |
| `3` | 一部だけ読み取れた状態 |
| `1` | タイムアウトや短い応答などの致命的エラー |

同じ詳細表示は次のコマンドでも確認できます。

```bash
./bin/mpc-mpcx-ip-command read 192.168.2.161
```

レジスタ範囲、表示書式、世代判定、バスエラー時の処理は[開発者ガイド](FOR_DEVELOPERS.md#runtime--eeprom-diagnostic-reports)を参照してください。

### ビルド要件

- C++11対応コンパイラ（`g++`または`clang++`）
- POSIXソケット
- `make`

既定のビルドは`-std=c++11`を使います。対象環境はLinux、macOS、WSLです。

### インストール先と更新

既定のインストール先はリポジトリ内の`./bin/`で、管理者権限は不要です。`make`だけではインストール済みコピーは更新されません。

ソースを更新したら、再ビルドしてインストール済みコピーも更新します。

```bash
git pull --ff-only
make install
```

`make install`は古くなったバイナリをビルドしてからコピーします。

別のインストール先を選ぶ場合:

```bash
make install PREFIX="$HOME/.local"
"$HOME/.local/bin/mpc-mpcx-ip-reader" DEVICE_IP
```

`$HOME/.local/bin`にPATHを通せば、コマンド名だけで実行できます。独自のprefixを指定した場合、例の`./bin/`を選択した`PREFIX/bin/`に置き換えてください。システム全体へのインストールは`sudo make install PREFIX=/usr/local`で行えます（管理者権限が必要です）。

### 公式リンク・参考資料

- [Bee Beans Technologies](https://www.bbtech.co.jp/)
- [SiTCP / SiTCP-XG ソフトウェア・マニュアル](https://www.bbtech.co.jp/download-files/sitcp/index_en.html)
- [SiTCP MPC Writer XG ユーザーガイド（英語PDF）](https://www.bbtech.co.jp/download-files/sitcp/SiTCP-MPC-Writer-XG-en.0.1.1.pdf)
- [SiTCP Forum](https://sitcp.bbtech.co.jp/)

### 関連ドキュメント

- [開発者向けガイド（英語）](FOR_DEVELOPERS.md) — 構成、ビルド/開発、技術的根拠、MPC/MPCXのEEPROM配置、装置の世代判定、参考資料、テスト。
- [AIエージェント向け指示（英語）](AGENTS.md) — 自動開発で守る制約。
