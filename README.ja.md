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

## macOSデスクトップ版

[Releases](https://github.com/nobukoba/amaneq-firmware-programer-first-trial/releases)の最新macOS desktop previewでAssetsを開き、Apple Silicon（arm64）用かIntel（x86_64）用のZIPを取得してください。ZIPを展開し、amaneq-firmware-programer.appをApplicationsへ移します。macOS 15以降が対象です。Python・Tk・openFPGALoader・HTTPS用CA証明書を同梱し、利用時のHomebrew導入は不要です。

0.4版はAMANEQ / CIRASAME / STAG選択の下に3タブを配置します。Firmwareはケーブルを自動検出し、TargetとFirmwareに一致するGitHub一覧を新しい順で表示し、先頭を自動選択します。GitHub listかLocal fileを選び、大きなProgram imageボタンひとつで書き込みます。GitHubリポジトリURLは編集でき、セッション中は対象ごとの編集値を保持します。既定ブランチの一致するファイルを最大10件表示し、Refresh listで再取得します。Loader欄と別のlatest-MCSボタンは廃止しました。既知のケーブルが1本なら自動選択し、複数ならシリアル選択、機種不明のFT232Hなら実物がHS3であることの確認が必要です。キャッシュ・通信失敗を明示し、表示したコミットとパスを固定して取得します。BITはSkeletonだけです。

必要に応じてEthernetアダプターを選び、Mac側のIPv4アドレスとマスクを入力してApply temporarilyを押します。DHCP・DNS・ゲートウェイの設定を保持し、固定IPを一時追加します。基板側のIP変更ではなく、USB/JTAG書き込みにも不要です。macOSの管理者許可が必要です。Restore networkか通常終了で追加IPだけを解除し、別プロセスも終了・クラッシュを監視します。既存IPの流用や他インターフェースとのサブネット重複は拒否します。解除に失敗したらエラーと記録を残し、追加IPは再起動でも消えます。起動時にネットワーク設定は変更しません。PC側の一時IPは192.168.10.20/24を初期値とし、編集できます。

取得物・ログ・一時設定の記録は~/Library/Application Support/AMANEQ/へ保存します。Apple公証のないアドホック署名版なので、初回はプライバシーとセキュリティの「このまま開く」が必要な場合があります。USBドライバー設定が不要なことと、Appleの配布時検査は別です。OS全体の保護は無効化しません。利用者のアダプターでの一時IP設定とHS3実機書き込みは未確認で、新しいネットワーク処理は模擬テストで確認します。

### Firmware・クロック・ライセンス/IPのタブ

上部で基板を選び、Firmware、set_cdce62002、MPC / MPCX / IPを切り替えます。上流の正式コマンド名はset_cdce62002です。CIRASAMEは専用の公式lrtdc・lrtdc-10g・Skeletonから取得し、AMANEQのイメージを除外します。クロック初期値はin_125_out_500_125です。STAGも標準SiTCP操作向けに選択できますが、公式の基板・レジスタ資料が提示されるまでファームウェアとクロックの書き込みを止めます。

クロックのタブにデバイスモード欄はありません。Target IPは192.168.10.10、192.168.10.16、Customから選びます。ライセンス/IPのタブは最上部でファイルを選び、内容からMPC/MPCXを判別・表示してTarget IPをそれぞれ.16/.10へ設定します。その下にTarget IP、一時IPの順で配置します。Enable temporary host IPをチェックすると、共通のEthernet・PC側IP欄が表示されます。初期状態は無効・非表示で、PC側初期値は192.168.10.20、マスク255.255.255.0です。チェックだけでは設定せず、macOSでApply temporarilyを押して一時追加します。追加中にチェックを外すと解除し、失敗した場合は欄を残します。Target IPの選択だけでは基板へ書き込みません。

クロックはhul-common-libの6プリセットから選び、Apply clock settingを押します。レジスタの読み戻し一致後にEEPROMへコピーします。Save clock settings for the next power-onは、確認したクロック設定をチップ内EEPROMへ保存して次回電源投入時に使う設定です。上流と同様初期状態で有効で、一時変更だけなら外します。保存コマンドへの応答は電源再投入後の保持確認とは区別してください。

ライセンスはファイルを選び、読み取り専用のCheckかWrite MPC/MPCXを使います。Readで現在値と保存値を表示します。New device IPはライセンス書き込み時は任意、Write IP onlyでは必須です。IPのみの変更はライセンスを保持します。初期状態はEEPROM IPの変更で、current/runtime IPを明示選択すると動作中IPを変更します。動作中IPの変更成功時だけ接続先も更新します。Initialize XG EEPROMは初期状態で無効です。Clear/resetは設けていません。書き込みは確認後に行い、参照元の世代照合・書き込み待機・読み戻し検証を保持します。

Mac版ZIPには固定した版のSiTCPコマンドを同梱し、利用時のコンパイラーは不要です。Linux/WSLのソース利用ではTkとC++コンパイラーを導入して実行します。

```bash
python3 build-network-tools.py
python3 amaneq-firmware-app.py
```

一時IPの自動設定は現時点ではmacOSのみです。Linux/WSLではホスト側Ethernetを192.168.10.20/24に設定します。WSL内のIP設定だけではWindowsのEthernetを設定できません。新GUIでのクロック・ライセンス書き込みとアダプター変更は実機未確認です。

## Windowsデスクトップ版：アプリ内でUSBを設定する

Windows x64向けの試作画面に、1画面にケーブル自動検出とUse WinUSB（切り替え）、Restore Vivado driver（元に戻す）ボタンを配置しました。ローカルのデスクトップ版にはPython・openFPGALoader・libwdi・cygpathを同梱でき、WSL・usbipdやZadigの別画面での手作業を省けます。ソース版は下記で起動します。ドライバー変更にはFOR_DEVELOPERSの手順でビルドしたx64版`runtime/libwdi.dll`が必要です。バイナリはGit管理しません。

表示されたシリアルを選び、実物がHS3であることをチェックします。ドライバー変更時はHS3/FT232Hを1本だけ接続し、Vivadoなどケーブルを使うアプリを閉じてください。変更ボタンを押して確認し、Windowsの管理者許可に応答します。切り替え前に元のFTDIBUSパッケージをエクスポートし、ハッシュ付きで保存します。復元は保存済みパッケージとWindowsのデバイス導入APIを使い、共有ドライバーパッケージは削除しません。復旧情報と処理結果を含む`%LOCALAPPDATA%/AMANEQ/usb-drivers/`を保管してください。INFはハードウェアIDで一致するため、後から接続した別のFT232Hにも影響する可能性があります。シリアル指定だけではパッケージの割り当てを分離できません。

ファームウェアの書き込みは別の明示操作です。GUIはHS3を指定し、最新版MCSかローカルBIT/MCSを扱います。BITはSkeletonのみです。既存CLIの履歴・URL・リポジトリ指定やXilinx経路も残っています。Linux/macOSはWindows用ドライバーボタンを使いません。変更処理の模擬テスト、DLL内の資源・実機との照合の読み取り確認、GUI起動を確認しました。新しいアプリを通じた実際の切り替え・復元は未確認です。

```powershell
python amaneq-firmware-app.py
```

## Windows：コピペでWSL2を準備する

既存のUbuntu WSL2を使います。未導入なら管理者PowerShellで`wsl --install -d Ubuntu`を実行し、要求されたら再起動して、Ubuntuの初回ユーザー設定を完了してください。その後、管理者PowerShellで最初のブロックを貼り付けます。ダウンロードしたスクリプトは実行前に確認してください。SetupはWindowsにusbipd-win、Ubuntuにgit・Python・openFPGALoader・usbutilsを導入し、同梱udevルールを再読み込みし、既定のLinuxユーザーをplugdevグループに追加して、WSLユーザーのホームへリポジトリを取得します。基板への書き込みはしません。インストーラーの画面や再起動要求が出たら対応し、Setupを再実行してください。`-Distribution`の既定値は`Ubuntu`で、他の既存apt系WSL2環境も指定できます。WSL1の変換や再起動は自動実行しません。

次のブロックでUbuntuを開き、その端末を開いたまま、管理者PowerShellでListとAttachを実行します。BUSIDはListの実際の表示に置き換えてください。FT232HのUSB IDだけではHS3とは断定できません。Attachは明示した機器を共有して転送し、ケーブルを自動選択しません。BashのコマンドはUbuntu内で実行します。複数ケーブルなら書き込みコマンドに`--serial`を追加してください。DetachでWindowsへ戻りますが、共有設定は残るため、解除するには管理者で`usbipd unbind --busid 4-4`を実行します。抜き差し後はAttachを再実行します。ExecutionPolicy Bypassは起動したプロセスだけに適用されます。ヘルプは`Get-Help .\setup-windows-wsl.ps1 -Full`で表示します。

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
