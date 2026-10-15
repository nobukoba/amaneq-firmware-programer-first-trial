# AGENTS.ja.md

**Language: [English](AGENTS.md) | 日本語**

英語版AGENTS.mdが自動開発用の正本です。この文書は同じ制約の日本語版です。

## 目的と名前

Python 3.10以上・標準ライブラリのみで、openFPGALoaderを呼ぶ取得・書き込みツールを維持します。レジスタ設定やSiTCPライセンス書き込みのツールではありません。

- 本体名は `amaneq-firmware-programer.py`。指定されたprogramerの綴りを勝手に変えません。
- shebangは `#!/usr/bin/env python3`、BOMなしUTF-8、LF改行。
- コマンドは `scan/inspect/local/versions/download/program/wizard`。
- 専用スクリプトは `program-latest-mcs-amaneq-*` と、Skeletonだけの `program-latest-bit-amaneq-v4-skeleton`。
- 共通処理は `firmware-latest-amaneq-common.sh/.cmd`。

SkeletonはBIT/MCS、他はローカル・直接URLを含めてMCSのみ。MikumariはMikuClockHubです。コード・コメント・表示・ヘルプ・エラーはすべて英語にし、利用者文書は英語・日本語を同じ実行例とLanguageリンクで同期します。ヘルプでは既定値を明示します。

## 文書作成

ユーザーのAI向け指示リポジトリにあるREADMEスタイルとCLIツール指針を読みます。SiTCP writerの「目的・導入・実際の書き込み・検査・付録」の導線を参考にし、実在するPythonファイルのパスを使います。存在しないmakeやbin構成を作りません。アルゴリズム・実機証拠は開発者文書に分けます。

## ケーブルと対象

- 複数ケーブルでシリアル未指定なら、一覧を表示し、取得・対話・JTAG操作より前に終了コード1で停止。--yesの有無によらず対話ケーブル選択は禁止。
- 同一シリアルが複数一致しても停止。最初の機器を勝手に使いません。
- 0403:6014はHS2/HS3/他のFT232Hで共通。型番証拠・明示--cable hs3・利用者指定の既知シリアルを使い、公開コードに個人の機器情報を固定しません。
- v1/v4・本体/メザニンは同じXC7K160T。JTAG IDだけでは対象を決められません。
- SkeletonだけはDAQマニュアルにv1/v4共通が明記されています。他への共通扱いは禁止。
- USBドライバー、PATH、.py関連付け、ホスト設定を自動で変更しません。

## 書き込みと検証

内容でBIT/MCSを判別し、MCSの長さ・チェックサム・EOF・重複、BITのヘッダーとFPGA IDを検証します。openFPGALoaderへ形式を明示します。

GitHubのコミットを固定し、サイズ・Git blobハッシュを照合。直接URLは内容検査、指定SHA256は必ず一致させます。HTMLは使いません。latestは既定ブランチ内の一致ファイルの最新版であり、Releaseタグの最新版とは限りません。v2.Aなどの16進バージョンを扱います。

履歴は既定合計10件、タグとコミットをまとめ、--history-limitは最大1000件です。

メザニンの自動取得・書き込みは、ファイル選択前に実機フラッシュを判定します。判定はSPIブリッジをSRAMへロードするためDAQ回路を置き換えますが、フラッシュは消去しません。JEDEC ID・認識名・容量・対象を照合し、消去前に再確認。MT25QU256がN25Q256Aと表示される場合は20bb19/32MiBの署名対応を使います。N25Q128は16MiBです。不明・矛盾した機器は停止します。

全フラッシュをバックアップしてから書き込み、別のダンプでMCSイメージ全バイトを比較します。確認したWindows版では--verifyがこのモード未対応でした。終了0だけで照合成功と判断しません。

破壊的書き込みの自動再試行、電源操作、ライセンスEEPROM書き換え、ドライバー変更はしません。失敗時もバックアップを保存。バイト一致は電源再投入起動・DAQ・通信・ライセンスの確認を意味しません。

## OS・公開・テスト

本体同梱だけではWindowsドライバー、Linux USB権限、WSL転送、コンテナUSB設定は解決しません。対応ケーブルは選んだ実行ファイルのlist-cablesで判断します。確認したWindows版はXilinx純正ローダー非対応。Linux純正ローダー経路の一意選択には制約があり、1台だけ接続します。実機未確認です。

対象はWindows WSL2・Linuxネイティブ・macOSネイティブです。macOSはioregのplistを解析しFTDIをシリアル指定、Linux/WSLはsysfsとbus/device指定を使います。WSLはusbipd-win転送とLinuxのUSB権限が必要です。macOS検出の模擬テストと実機書き込みの検証を区別してください。Windowsネイティブは従来の実装・実機観測として保持します。

```bash
python3 -m unittest test_amaneq_firmware_programer -v
python3 amaneq-firmware-programer.py --help
```

追跡するテストは合成データを使います。実ファームウェア・ダンプ・認証情報・独自ライセンス・ドライバーバックアップ・ローカルランタイムはGitへ入れません。実機を変えるテストは別の明確な許可が必要です。専用スクリプトの確認には--helpを使います。

コードを通常のブロック構造で読みやすく保ち、コメントとガードを維持します。py/shのGit実行権限とcmdのCRLF設定を維持します。README・開発者文書・AGENTSの英語/日本語を同期し、ユーザーが許可したAI向け指示にも長期的な訂正・知見を反映します。プロジェクト固有の事実を万能な規則にしません。

Windows用setup-windows-wsl.ps1は明示実行するホスト導入用です。Setupは管理者でusbipd-winとWSL内aptパッケージを導入します。Attach/DetachはBUSID必須、自動選択・書き込み・再起動はしません。通常のPython実行はホスト設定を変更しません。導入の実行検証と構文・モック検証を区別してください。

## 明示操作によるWindowsネイティブのUSB切り替え

以前のWSL運用に加え、利用者がアプリ内のドライバー切り替えを明示的に依頼しました。amaneq-firmware-app.pyはデスクトップ画面、windows_usb.pyはUSBボタンと確認後だけ使う処理です。通常のCLI・書き込みから自動変更しません。管理者昇格はドライバー処理だけです。Windows x64のHS3が対象で、実物の確認とFT232Hが1本だけであることを要求し、変更直前にも照合します。

元のFTDIBUS OEMパッケージをpnputilで保存し、LOCALAPPDATA/AMANEQ/usb-drivers配下で全ファイルのハッシュを保管します。元バックアップは上書きせず、欠落・変更・別機器なら復元を拒否します。libwdiは公式v1.5.1 ABIに合わせ、署名・カタログ検査は無効化しません。復元は保存INFとUpdateDriverForPlugAndPlayDevicesWを使い、共有パッケージを削除しません。別FT232Hへの影響をシリアル指定だけで防げるとは説明しません。自動再試行や書き込み失敗後の自動復元はしません。状態を検証し、結果・エラーを残します。

ローカルビルドは未変更のlibwdi v1.5.1（9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602）と公式WDK 8再頒布部品（https://go.microsoft.com/fwlink/p/?LinkID=253170）です。MinGW x64、CC_FOR_BUILD=gcc、--disable-32bit、展開したWindows Kits/8.0を--with-wdkdirへ指定してクロスビルドします。WinUSB資源と実機照合は読み取り確認済みですが、新アプリでの実際の変更・復元は未確認です。過去のZadigでの変更・復元とは区別します。

build-windows-app.py --helpに従い、UCRT64・libwdi DLLと対応ソース・Cygwin binを指定し、PythonとPyInstallerでローカルEXE・ZIPを作ります。libwdiの対応ソース・ライセンスも同梱します。バックアップ、ビルドログ付きソース、個人パスを公開しません。第三者の表示と配布条件を確認してから外部向けバイナリを公開してください。ソース公開・実行ファイルの起動テストは接続機器の変更許可ではありません。

## macOSアプリのビルド

build-macos-app.pyはMac上で実行し、Apple Silicon arm64とIntel x86_64を対応するPythonで別々に作ります。macos-app.ymlはmacos-15とmacos-15-intelを使います。openFPGALoaderをPyInstallerのbinaryとして扱い、dylibを回収・再配置して、システム外への絶対リンクが残れば失敗させます。XC7K160T SPIブリッジは非圧縮で同梱します。openFPGALoader・libftdi・libusbの対応ソース・表示・Homebrewレシピを入れ、版やチェックサムの不一致を無視しません。

.app内へ書き込みや__pycache__生成をしません。GUIのCLI子プロセスは利用者のデータ用ROOTを使い、windowed起動で標準出力がNoneなら復旧します。Macの保存先は~/Library/Application Support/AMANEQです。HS3の機種確認欄は全タブ共通で、Windows用ドライバー変更は無効です。署名・起動・ローダー・機器未接続の検出・依存関係の検査と、実機書き込みを区別します。Developer ID署名・Apple公証は設定していません。dittoでシンボリックリンク・権限・資源を保つZIPを作ります。Artifact保存は30日で、恒久的なRelease配布ではありません。

## デスクトップ0.2の訂正

利用者は1画面、起動時ケーブルスキャン、最新版一覧、Ethernetアダプター選択を要求しています。Macに空のWindowsタブを作り直しません。ケーブル1本だけなら自動選択、複数ならシリアルを明示指定します。一覧は表示したコミット・パスへ固定し、5分キャッシュとオフライン・古い確認日時を明示します。起動時の読み取り処理でUSBドライバー・IP・フラッシュを変更しません。

macos_network.pyは明示確認と管理者許可後だけ一時IPv4 aliasを追加します。DHCP・DNS・ゲートウェイは保持し、ネットワークサービスやPC側IPを勝手に置き換えません。Ethernet・MAC・ホストIP・マスク・他IFとの重複を検査し、既存IPを流用・削除しません。利用者所有のnonce付き記録をアプリ外へ置き、昇格ヘルパーは固定の検証済み操作だけを行います。監視プロセスが元アプリの起動時刻と解除要求を確認し、自分の追加IPだけ外します。監視の起動失敗なら追加を巻き戻し、解除失敗はエラーにします。非永続aliasは再起動でも消えます。模擬テストと利用者の実アダプター変更を区別します。JTAG書き込みにEthernet設定は不要です。

Mac版はcertifiのCAとライセンスを同梱し、利用者の指定がない場合だけSSL_CERT_FILEを設定します。TLS検証を無効化しません。アドホック署名はApple公証ではなく、初回許可は残ります。両CPUのビルド成功後にReleaseへ公開し、Actionsは中間成果物として扱います。Actionsや期限切れの一時URLだけを利用者へ案内しません。

## Desktop 0.3の優先仕様

最新指示ではAMANEQ/CIRASAME/STAG選択の下にFirmware、set_cdce62002、MPC/MPCX/IPの3タブを配置します。CIRASAME表記は了承済みです。ネットワーク2タブはEthernet選択とPC側一時IP192.168.10.20/24を共有し、MPCX接続先.10、MPC .16、Customで任意指定します。切替だけでは適用せず、動作中IPの検証成功後だけ接続先を更新します。

クロックはhul-common-libの65476509aa401aad10148ec7c2d2a50ba7d2db3eに基づきます。SPIワード反転と0x10000間隔のリトルエンディアンのバイトレーンを保持し、TX B0000000、RX B0100000、実行B1000000/B2000000を使います。レジスタ0/1の一致後に任意の0x1F EEPROM保存を行い、上流同様初期状態は保存有効です。電源再投入後の保持は未確認です。CIRASAMEの公式hardware/cirasame/cirasame.mdはXC7K160T/FFG676とS25FL128S、practical/practical.mdはin_125_out_500_125を示します。専用ファームウェアだけを選別してください。STAGの未確認マップを推測せず書き込みを止めます。

SiTCPは指定リポジトリの固定ソースを変更せず組み込み、UPSTREAM.jsonに出所を残します。build-network-tools.pyでLinux/WSL/macOS用にビルドし、Macには3コマンドと対応ソースを同梱します。上流の世代照合・500ms待機・読み戻し・エラーを保持し、自動Clear/reset/再書き込みは行いません。Windowsネイティブのネットワーク補助コマンドは未対応です。一時IP自動設定はMacのみで、Linux/WSLのホストEthernetは手動設定です。生成バイナリと実ライセンスはGitへ含めません。新GUIでの実機書き込みは未確認です。

## Desktop 0.4の画面整理

最新指示によりDevice modeを廃止し、各ネットワークタブでTarget IPを.10/.16/Customから選びます。ライセンス/IPはファイル選択・内容からの種類判別、Target IP、一時IPの順です。Enableは初期状態で無効・非表示とし、チェックで欄を表示、Applyで明示適用します。追加中に外すと解除し、失敗時は欄を表示したままにします。クロックのEEPROM欄は次回電源投入用保存という表現にします。

Firmwareはケーブル自動判別、TargetとFirmwareで絞り込み、新しい順と先頭自動選択、対象ごとに編集できるGitHub URL、GitHub/Local切替、大きなProgram imageひとつとします。Loader欄とlatest-MCS専用ボタンは廃止します。複数ケーブル・不明機種のガードは維持し、URLや対象変更で選択を無効化して古い非同期結果を破棄します。書き込み前にも出所を照合します。キャッシュはリポジトリ・対象・種類別で、一時ファイル名を一意にします。既定ブランチ内の最大10ファイルで、CLI履歴の挙動は維持します。

## Desktop 0.5のタブ順と分類修正

最新の順序はFirmware、MPC / MPCX、IP、Jitter Cleanerです。IP専用の読み書きを独立させ、ライセンス書き込みへIPオプションを渡しません。sitcp-sitcpxg-ip-readerも追加し、Macには4つのネイティブ補助コマンドを同梱します。ネットワーク用3タブで一時IPを共有します。Target IPはラベル・選択/カスタム・Ping・結果の1行とし、マスクやUDPの説明を外します。Pingは非同期2回、全体8秒以内とし、Macの-Wはms、Linuxは秒である点に注意します。重複実行を抑止し、古い接続先の結果を現在値と混同しません。ICMP結果とRBCPの有効性は区別します。

重要な修正：上流の分類2（タグ位置6、差分0x34）は通常SiTCPのMPC、分類1（位置0、差分0x2C）はSiTCP-XGのMPCXです。判定順は上流通り分類2を先に保ちます。以前のPython表示名が逆でした。公式の合成fixtureで回帰テストし、MPCは接続先.16、MPCXは.10とします。拡張子に依存せず、検証済みC++ライターは変更しません。

## Desktop 0.6の過去版一覧

既定ブランチに残るファイルだけでなく、削除・置き換え済みの過去ファームウェアも表示します。現在のブランチ、タグ、mcs（Skeletonはbitも）のコミット履歴をたどり、各行の出所コミットとパスを固定します。形式・パス・Git blob SHAで重複をまとめ、同名でも内容が異なるものは保持します。History limitは合計10件が初期値で1～1000へ変更できます。現在のブランチを先頭とし、16進数の版番号で最新版を自動選択します。過去行にはタグ・日付・コミットを表示します。キャッシュキーに履歴モードと件数を含め、古いキャッシュや不完全な取得を明示します。探索はディレクトリごとにmin(1000,max(20,limit*3))コミットと有界のタグで、API制限を完全取得と扱いません。CLI履歴は維持します。公式StrLrTdc v4でv2.A、v2.9、v2.8.1、v2.8等を読み取り取得でき、実機書き込みは行っていません。
