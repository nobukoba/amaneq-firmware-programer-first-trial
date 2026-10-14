# AMANEQ Firmware Programer (first trial)

**Language: [English](README.md) | 日本語**

openFPGALoaderでAMANEQファームウェアを取得・書き込みます。対応する各種類はMCS、Skeletonは一時ロード用BITにも対応します。

## まず準備する

Python 3.10以上とopenFPGALoaderが必要です。Pythonプログラムは標準ライブラリだけを使うため、このリポジトリ自体の`pip install`は不要です。openFPGALoader本体、USBドライバー、ファームウェアは同梱していません。

Ubuntu/Debianでは、ツールをインストールしてからリポジトリを取得します。

```bash
sudo apt update
sudo apt install git python3 openfpgaloader
git clone https://github.com/nobukoba/amaneq-firmware-programer-first-trial.git
cd amaneq-firmware-programer-first-trial
./amaneq-firmware-programer.py --help
```

## 先にケーブルを確認する

ケーブルを対象のJTAGコネクターへ接続して基板の電源を入れます。付録の手順でLinuxのUSBアクセス権限を設定してから、接続ケーブルを表示します。

複数ケーブルが接続され、`--serial`が未指定なら、シリアル番号を表示して終了コード1で停止します。ケーブル選択の対話には入りません。`--cable hs3`は、実物がHS3であることを利用者が指定するオプションです。USB IDだけでは他のFT232H機器と区別できません。

```bash
./amaneq-firmware-programer.py scan
```

## v4に最新版LRTDCのMCSを書き込む

次のコマンドは公式の既定ブランチから最新版v4用MCSを取得し、ファイル名を表示して、対象確認・フラッシュのバックアップ・書き込み・全書き込みバイトの読み戻し照合を行います。専用スクリプトは最終確認を省略し、すぐに書き込みを開始します。

複数ケーブルなら、`scan`に表示された対象のシリアルを指定してください。例のシリアル値は実際の対象に置き換えます。MCS照合に成功した後は、基板の電源を入れ直してフラッシュからの起動を確認します。

```bash
./program-latest-mcs-amaneq-v4-lrtdc.sh --cable hs3
./program-latest-mcs-amaneq-v4-lrtdc.sh --cable hs3 --serial SERIAL_FROM_SCAN
```

## ファームウェアを選ぶ

専用スクリプトは`.sh`版とWindows用`.cmd`版があります。共通の`firmware-latest-amaneq-common.sh` / `.cmd`も同じフォルダーに置きます。

| ファームウェア | 対象 | スクリプト名（拡張子なし） |
|---|---|---|
| LRTDC・1GbE | AMANEQ v4 | `program-latest-mcs-amaneq-v4-lrtdc` |
| HRTDC Base・10GbE | AMANEQ v4 | `program-latest-mcs-amaneq-v4-hrtdc` |
| LRTDC-10G | AMANEQ v4 | `program-latest-mcs-amaneq-v4-lrtdc-10g` |
| Mikumari Clock Hub | AMANEQ v4 | `program-latest-mcs-amaneq-v4-mikumari` |
| Skeleton・永続MCS | AMANEQ v4 | `program-latest-mcs-amaneq-v4-skeleton` |
| Skeleton・一時BIT | AMANEQ v4 | `program-latest-bit-amaneq-v4-skeleton` |
| HRTDCメザニン | HR-TDCメザニン | `program-latest-mcs-amaneq-hrtdc-mzn` |

SkeletonはBIT/MCS、他の種類はMCSのみ対応します。`mikumari`はMikuClockHubを指し、MikuClockPrimではありません。

v1基板ではPythonコマンドに`--target amaneq-v1`を指定します。SkeletonはDAQマニュアルに記載されたv1/v4共通ファイルを使います。共通のFPGA IDだけでは、リビジョンや本体・メザニンを確定できません。

```bash
./amaneq-firmware-programer.py program --latest --firmware skeleton --target amaneq-v1 --format bit --cable hs3
./program-latest-bit-amaneq-v4-skeleton.sh --cable hs3
./program-latest-mcs-amaneq-hrtdc-mzn.sh --cable hs3
```

## 手元のファイルを使う

`program --file`は拡張子によらず内容を読み、Intel HEXのMCSとXilinx BITを判別します。認識できるファイル名やFPGA情報が、指定したファームウェア・対象基板と矛盾する場合は停止します。通常のPythonコマンドには最終確認があり、無人実行する場合だけ`--yes`を指定します。

```bash
./amaneq-firmware-programer.py inspect --file firmware/amaneq-4-strlrtdc-v2.A.mcs
./amaneq-firmware-programer.py program --file firmware/amaneq-4-strlrtdc-v2.A.mcs --firmware lrtdc --target amaneq-v4 --cable hs3
```

## 書き込まずに取得する

`download`は実機にアクセスしません。GitHubからの取得は解決したコミットに固定し、Git blobハッシュと照合します。ファイルと`.source.json`は`firmware/downloads/`以下に保存します。実機判定なしのメザニン取得ではフラッシュ種類を指定するか、`--flash auto`で複数候補があればファイルを対話選択します。

```bash
./amaneq-firmware-programer.py download --latest --firmware lrtdc --target amaneq-v4 --format mcs
./amaneq-firmware-programer.py download --latest --firmware hrtdc --target hrtdc-mezzanine --format mcs --flash mt25qu256
```

## 過去版・別のURLを選ぶ

履歴は既定で現在のブランチを含む合計10件です。同じリビジョンのタグ・コミットをまとめ、過去のリビジョンをコミット日時の新しい順に表示します。合計件数は`--history-limit`で増やせます（最大1000）。タグ・コミットが分かっている場合は`--ref`で直接指定できます。

GitHubリポジトリURLは`--repo`、HTTP(S)のファイル直接URLは`--url`で指定します。GitHubの`blob`閲覧ページは直接ファイルではありません。直接URLでも内容を検査し、`--sha256`で既知の期待ハッシュも照合できます。`--url`は`--repo`・`--latest`・`--ref`と併用しません。

```bash
./amaneq-firmware-programer.py versions --firmware lrtdc --history-limit 30
./amaneq-firmware-programer.py download --choose-version --firmware lrtdc --target amaneq-v4 --format mcs --history-limit 30
./amaneq-firmware-programer.py download --repo https://github.com/AMANEQ-official/StrLrTdc --target amaneq-v4 --format mcs --ref v2.8
./amaneq-firmware-programer.py download --url "https://raw.githubusercontent.com/spadi-alliance/AMANEQ-Skeleton/main/bit/amaneq-skeleton-v2.2.bit" --firmware skeleton --target amaneq-v4
```

## 付録

以下に設定と操作の補足をまとめます。

## LinuxのUSBアクセス権限

HS3 / FT232H機器に対する次のルールをホスト側に設定し、グループへ加入してからログアウト・ログインとケーブルの抜き差しを行います。同じVID/PIDの他のFT232H機器にも適用されます。パッケージ導入時に適切なudevルールが既に入る場合もあります。

```bash
sudo groupadd -f plugdev
sudo tee /etc/udev/rules.d/99-amaneq-hs3.rules >/dev/null <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", ATTR{idProduct}=="6014", MODE="0660", GROUP="plugdev"
EOF
sudo usermod -aG plugdev "$USER"
sudo udevadm control --reload-rules
```

## Windows WSL2・Linux・macOSの準備

対象はWindowsのWSL2、Linuxネイティブ、macOSネイティブです。Python 3.10以降と、それぞれのOS用openFPGALoaderを使用します。WindowsではWSL2内でLinux版と`.sh`を実行します。Windowsネイティブ用`.cmd`は従来の補助ファイルとして残しますが、今回の対象には含めません。

WSL2/Ubuntuと[usbipd-win](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)を導入し、WSLの端末を開いた状態で、WindowsのPowerShellから対象ケーブルを転送します。bindは管理者権限、attachは通常権限で実行できます。転送中はWindowsのアプリからケーブルを使えません。抜き差し後はattachをやり直します。WSL内にopenFPGALoaderを導入し、上記のLinux用USBアクセス権限も設定してください。この経路ではWindows側のWinUSBへの置き換えは前提ではありません。

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

macOSは`ioreg`でUSBを検出し、FTDIケーブルをシリアル番号で指定します。Linuxのsysfs・udevやWindowsのcygpathは使いません。アクセスに失敗したら、ケーブルを使用するアプリを閉じ、openFPGALoaderのエラーを確認してください。プログラムがドライバーを自動変更することはありません。3環境とも上記のPythonコマンドと`.sh`を使います。

## 各環境とコンテナの確認状況

macOSの検出・シリアル選択は模擬テストで確認しました。WSL2、Linux/macOSネイティブでの書き込み、Xilinxケーブル、メザニン判定は実機未確認です。以前のWindowsネイティブ版openFPGALoader/HS3の実機結果は、これら3環境の検証とは区別します。

LinuxコンテナではホストのUSBアクセス権限が必要です。Docker Engineは`/dev/bus/usb`の公開、Apptainerは通常見える`/dev`・`/sys`と実行ユーザーの権限を使います。WSLではコンテナ実行前にUSBを転送します。DockerイメージやSIFは同梱しません。

## 既定値・保存先・エラー

既定値は、種類`lrtdc`、基板`amaneq-v4`、取得形式`mcs`、ケーブル`auto`、フラッシュ`auto`、通信タイムアウト45秒、履歴合計10件です。各コマンドの`--help`にも表示します。

- 取得ファイルと出典情報：`firmware/downloads/`。
- SPIブリッジの生成キャッシュ：`firmware/cache/`。
- フラッシュ全体のバックアップ・読み戻し・結果JSON：`logs/`。
- `--timeout`は通信の無応答待ち時間であり、書き込み処理の総時間制限ではありません。
- DNS・ネットワーク未接続、タイムアウト、HTTP 401/403/404/429、TLS失敗、途中切断、HTMLや不正なファイル、ハッシュ不一致では英語の`ERROR:`を表示して停止します。
- 終了コード：完了0、操作・検証失敗1、引数構文エラー2、入力・操作中断130。
- `--yes`は最終確認を省略するだけで、不明な機器やファイル候補を推測して選びません。

バックアップは保存してください。MCS書き込みはフラッシュ全体を消去する場合があり、照合するのは書き込んだイメージのバイトです。バイト照合の成功だけでは、電源再投入での起動やDAQ・通信の動作は証明できません。

```bash
./amaneq-firmware-programer.py program --help
```

## メザニンとSiTCPライセンス

GitHubのMCSを書き込むメザニンコマンドは、`--flash auto`なら取得ファイル選択前にフラッシュを判定します。SPIブリッジをFPGAのSRAMへ一時ロードするため動作中のDAQ回路は置き換わりますが、判定だけではフラッシュを消去しません。JEDECシグネチャと容量でMT25QU256/N25Q128を選び、消去前にも再確認します。不明または矛盾する機器では停止します。

ファームウェア書き込みだけではSiTCPライセンスは導入されません。SiTCPとSiTCP-XGは別ライセンスであり、1GbE/10GbEファームウェアの切り替えでは、別のツールによる適切なEEPROMライセンス・設定が必要になる場合があります。このプログラムはライセンスEEPROMを書き換えません。

## 参照資料と開発

コネクター・基板設定は[DAQの書き込みマニュアル](https://www.rcnp.osaka-u.ac.jp/~spadi/wiki/?SPADI-A%20DAQ%20%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB/%E3%83%95%E3%82%A1%E3%83%BC%E3%83%A0%E3%82%A6%E3%82%A7%E3%82%A2/%E3%83%95%E3%82%A1%E3%83%BC%E3%83%A0%E3%82%A6%E3%82%A7%E3%82%A2%E3%81%AE%E6%9B%B8%E3%81%8D%E8%BE%BC%E3%81%BF%E6%96%B9%E6%B3%95)、USBと本体の導入は[openFPGALoaderのインストール資料](https://trabucayre.github.io/openFPGALoader/guide/install.html)を参照してください。

公式配布先：[StrLrTdc](https://github.com/AMANEQ-official/StrLrTdc)、[StrHrTdcBase](https://github.com/AMANEQ-official/StrHrTdcBase)、[StrLrTdc-10G](https://github.com/AMANEQ-official/StrLrTdc-10G)、[MikuClockHub](https://github.com/AMANEQ-official/MikuClockHub)、[MznStrHrTdc](https://github.com/AMANEQ-official/MznStrHrTdc)、[AMANEQ-Skeleton](https://github.com/spadi-alliance/AMANEQ-Skeleton)。

構造・テスト・実機で測った結果と実装上の仮定の区別は[FOR_DEVELOPERS.md](FOR_DEVELOPERS.md)、変更時に守る制約は[AGENTS.md](AGENTS.md)にまとめています。

```bash
python3 -m unittest test_amaneq_firmware_programer -v
```
