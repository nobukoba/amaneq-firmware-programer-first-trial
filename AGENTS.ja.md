# AGENTS.ja.md

**Language: [English](AGENTS.md) | 日本語**

英語版AGENTS.mdが自動開発用の正本です。この文書は同じ制約の日本語版です。

## 現在の引き継ぎ

別チャットで再開する前に [HANDOFF.ja.md](HANDOFF.ja.md) を読んでください。Windows D2XXとMCS実機結果の記述は、過去のWSL／WinUSB専用という前提に優先します。

## 目的と名前

Python 3.10以上・標準ライブラリのみで、openFPGALoaderを呼ぶ取得・書き込みツールを維持します。レジスタ設定やSiTCPライセンス書き込みのツールではありません。

- 本体名は `amaneq-firmware-programer.py`。指定されたprogramerの綴りを勝手に変えません。
- shebangは `#!/usr/bin/env python3`、BOMなしUTF-8、LF改行。
- コマンドは `scan/inspect/local/versions/download/program/wizard`。
- 専用スクリプトは `program-latest-mcs-amaneq-*` と、Skeletonだけの `program-latest-bit-amaneq-v4-skeleton`。
- 共通処理は `firmware-latest-amaneq-common.sh/.cmd`。

対応する各種類でローカル・直接URLを含めBIT / MCSを選べます。MikumariはMikuClockHubです。コード・コメント・表示・ヘルプ・エラーはすべて英語にし、利用者文書は英語・日本語を同じ実行例とLanguageリンクで同期します。ヘルプでは既定値を明示します。

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

履歴は既定合計5件、タグとコミットをまとめ、--history-limitは最大1000件です。

メザニンの自動取得・書き込みは、ファイル選択前に実機フラッシュを判定します。判定はSPIブリッジをSRAMへロードするためDAQ回路を置き換えますが、フラッシュは消去しません。JEDEC ID・認識名・容量・対象を照合し、消去前に再確認。MT25QU256がN25Q256Aと表示される場合は20bb19/32MiBの署名対応を使います。N25Q128は16MiBです。不明・矛盾した機器は停止します。

全フラッシュをバックアップしてから書き込み、別のダンプでMCSイメージ全バイトを比較します。確認したWindows版では--verifyがこのモード未対応でした。終了0だけで照合成功と判断しません。

破壊的書き込みの自動再試行、電源操作、ライセンスEEPROM書き換え、ドライバー変更はしません。失敗時もバックアップを保存。バイト一致は電源再投入起動・DAQ・通信・ライセンスの確認を意味しません。

## OS・公開・テスト

本体同梱だけではWindowsドライバー、Linux USB権限、WSL転送、コンテナUSB設定は解決しません。対応ケーブルは選んだ実行ファイルのlist-cablesで判断します。確認したWindows版はXilinx純正ローダー非対応。Linux純正ローダー経路の一意選択には制約があり、1台だけ接続します。実機未確認です。

対象はネイティブWindows D2XXデスクトップ版・Linux・macOSで、WSL2も代替経路として残します。macOSはioregのplistを解析しFTDIをシリアル指定、Linux/WSLはsysfsとbus/device指定を使います。WSLはusbipd-win転送とLinuxのUSB権限が必要です。macOS/Linuxの実機書き込みは未検証です。Windows D2XXでのMCS書き込み・読み戻しはHANDOFF.ja.mdのとおり実機確認済みで、以前のネイティブlibusb実装は従来経路として保持します。

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

SiTCPは指定リポジトリの固定ソースを変更せず組み込み、UPSTREAM.jsonに出所を残します。build-network-tools.pyでLinux/WSL/macOS用にビルドし、Macには4コマンドと対応ソースを同梱します。上流の世代照合・500ms待機・読み戻し・エラーを保持し、自動Clear/reset/再書き込みは行いません。現在のWindowsデスクトップ版はCygwinでビルドしたネットワーク補助コマンドを同梱します。ネイティブ版のパッケージ説明を参照してください。一時IP自動設定はMacのみで、Linux/WSLのホストEthernetは手動設定です。生成バイナリと実ライセンスはGitへ含めません。新GUIでの実機書き込みは未確認です。

## Desktop 0.4の画面整理

最新指示によりDevice modeを廃止し、各ネットワークタブでTarget IPを.10/.16/Customから選びます。ライセンス/IPはファイル選択・内容からの種類判別、Target IP、一時IPの順です。Enableは初期状態で無効・非表示とし、チェックで欄を表示、Applyで明示適用します。追加中に外すと解除し、失敗時は欄を表示したままにします。クロックのEEPROM欄は次回電源投入用保存という表現にします。

Firmwareはケーブル自動判別、TargetとFirmwareで絞り込み、新しい順と先頭自動選択、対象ごとに編集できるGitHub URL、GitHub/Local切替、大きなProgram imageひとつとします。Loader欄とlatest-MCS専用ボタンは廃止します。複数ケーブル・不明機種のガードは維持し、URLや対象変更で選択を無効化して古い非同期結果を破棄します。書き込み前にも出所を照合します。キャッシュはリポジトリ・対象・種類別で、一時ファイル名を一意にします。既定ブランチ内の最大5ファイルで、CLI履歴の挙動は維持します。

## Desktop 0.5のタブ順と分類修正

最新の順序はFirmware、MPC / MPCX、IP、Jitter Cleanerです。IP専用の読み書きを独立させ、ライセンス書き込みへIPオプションを渡しません。sitcp-sitcpxg-ip-readerも追加し、Macには4つのネイティブ補助コマンドを同梱します。ネットワーク用3タブで一時IPを共有します。Target IPはラベル・選択/カスタム・Ping・結果の1行とし、マスクやUDPの説明を外します。Pingは非同期2回、全体8秒以内とし、Macの-Wはms、Linuxは秒である点に注意します。重複実行を抑止し、古い接続先の結果を現在値と混同しません。ICMP結果とRBCPの有効性は区別します。

重要な修正：上流の分類2（タグ位置6、差分0x34）は通常SiTCPのMPC、分類1（位置0、差分0x2C）はSiTCP-XGのMPCXです。判定順は上流通り分類2を先に保ちます。以前のPython表示名が逆でした。公式の合成fixtureで回帰テストし、MPCは接続先.16、MPCXは.10とします。拡張子に依存せず、検証済みC++ライターは変更しません。

## Desktop 0.6の過去版一覧

既定ブランチに残るファイルだけでなく、削除・置き換え済みの過去ファームウェアも表示します。現在のブランチ、タグ、mcs（Skeletonはbitも）のコミット履歴をたどり、各行の出所コミットとパスを固定します。形式・パス・Git blob SHAで重複をまとめ、同名でも内容が異なるものは保持します。History limitは合計5件が初期値で1～1000へ変更できます。現在のブランチを先頭とし、16進数の版番号で最新版を自動選択します。過去行にはタグ・日付・コミットを表示します。キャッシュキーに履歴モードと件数を含め、古いキャッシュや不完全な取得を明示します。探索はディレクトリごとにmin(1000,max(20,limit*3))コミットと有界のタグで、API制限を完全取得と扱いません。CLI履歴は維持します。公式StrLrTdc v4でv2.A、v2.9、v2.8.1、v2.8等を読み取り取得でき、実機書き込みは行っていません。

## Desktop 0.7の形式・パス欄

Format選択を追加し、履歴探索・件数制限より前に形式を絞り、キャッシュキーにも含めます。BITは従来の明示指定どおりSkeletonのみで、他の種類はMCSだけです。HR-TDCメザニンはhrtdc固定でラベルとFirmware選択欄を隠し、別対象へ戻したら復帰させます。Program imageは1つを維持します。ローカル内容と選択形式の照合はTkスレッド外で書き込み前に行います。MPC/MPCXファイルは1行の読み取り専用パスで、横ホイールと左右・Home/End移動を提供します。編集可能なURL欄の通常カーソル操作は維持します。起動テストで形式切替・欄の非表示と復帰・非常に長いパスを確認します。

Desktop 0.8：New device IPのラベル・入力・runtimeチェック欄を1行に配置します。表記はChange current (runtime) IP instead of saved EEPROM IPとTemporary static host IP address (DHCP preserved, restored on exit)です。動作は維持します。

Desktop 0.9：周波数ラベルとプリセットを1行とし、クロックのボタン名はApplyです。Program image、Write MPC/MPCX、Write IP、Applyは共通Action.TButtonを使い、通常サイズ・通常余白の太字にします。Program imageを全幅に広げたり大型化したりしません。

Desktop 0.10：履歴とは以前の画面ではなく過去メッセージと確認できました。起動中のログを保持し、ホイール・スクロールバー・履歴キーでは自動see(end)を停止します。First/Latest/Follow latestで表示位置を操作し、新規出力で過去の閲覧位置を奪いません。Messagesを縦Panedwindowの可変領域とし、境界ドラッグで高さを変えます。Expandボタンはありません。ウィンドウは最小720x480で拡縮し、UI sizeは元のサイズを保持して既存の名前付きフォントと太字アクションフォントを拡縮します。タブ切替のidleと25ms後に配置・Expose、Map時にCanvas内枠を再配置します。起動確認だけで利用者のMacの描画不具合を目視検証済みと扱いません。画面遷移の履歴は不要です。

Desktop 0.11：通常のクロック画面から実装寄りのHULレジスタマップ説明を削除し、Select input / output frequencies of CDCE62002 chip (MHz):とします。STAG未対応の条件付き表示は維持し、正式なCDCE62002表記を使います。以前のタブ順指定はJitter Cleanerが重複し回答がないため、末尾をIPと解釈し、Firmware / Jitter Cleaner / MPC/MPCX / IPとする前提を明示します。HULは公式ガイドのHadron Universal Logicです。ライブラリの出所は開発資料に記載し、通常の操作欄へ混ぜません。

Desktop 0.12：Target IPの表示は192.168.10.16 (SiTCP default)と192.168.10.10 (SiTCP-XG default)です。補足は表示専用で、Ping/RBCPには検証したIPアドレスだけを渡します。MPC/MPCXファイルの判定後も対応するラベルを選び、Customは維持します。

Desktop 0.13のFirmware表示：lrtdc → LR-TDC、hrtdc → HR-TDC、lrtdc-10g → LR-TDC 10GbE、mikumari → MIKUMARI Hub、skeleton → Skelton（指定表記）です。UI表示だけの対応付けで、CLIオプション・リポジトリ・実ファイル名・キャッシュキーの内部識別名は維持します。

Desktop 0.14では従来のSkeleton限定BIT制限を廃止し、対応する全種類でMCS / BITを選べます。FPGA・対象・ケーブル照合は維持します。BITは一時SRAMロード、MCSは永続フラッシュ書き込みです。MessagesのExpand/Restoreを廃止し、境界のドラッグで高さを変えます。MPC/MPCXパスは左右キー・Home/End・クリックで移動したカーソル位置を横スクロールして表示します。一時IPの有効化チェックはTemporary static host IP address (DHCP preserved, restored on exit)の1行とし、重複見出しを削除します。Write IP直下の説明行も削除します。画面の動作確認では実機書き込みやホストIP変更を行いません。

公開前にbuild-macos-app.pyの版番号とmacos-app.ymlのReleaseタグ・タイトルを一致させます。

Desktop 0.14.1では形式選択欄と画像一覧を.mcs file / .bit fileと表示します。内部のmcs / bitに明示的に対応付け、CLIオプション・内容検証・書き込み処理は維持します。

Desktop 0.14.2では形式表示をBIT / MCSに戻します。十六進バージョン解析前に.bit / .mcs拡張子を除外し、v2.A.bitをv2.Aと読みます。誤って追加されていた.Bを修正し、v2.A.B.bitのような本来の第3要素は維持します。一覧キャッシュも更新します。一時ホストIPの下はNIC:・アダプター選択・Refresh・Host IP:・Mask:を1行に配置し、Apply/Restoreはその下に残します。

Desktop 0.14.4ではCable (automatically detected)・ケーブル選択欄・Rescanを1行に配置します。枠の見出しを通常ラベルに変更し、検出結果と必要な場合のHS3実物確認は下に残します。複数ケーブルのシリアル指定・機種照合は維持します。

Desktop 0.14.5ではMPC/MPCXパスの直接入力・貼り付けに対応します。引用符付きパスと~を扱い、入力後・Enter・フォーカス移動で内容を検証して種類と既定ターゲットを設定します。不正な入力は欄に残してエラーを表示し、ファイルを使う書き込みを停止します。選択ボタンとカーソル追従は維持します。Messagesの上に高さ12ピクセルの見えるドラッグバーを置き、縦リサイズカーソルと明示的なマウス処理で高さを変更します。画面全体の座標で移動量を計算し、ネイティブ境界のつかみやすさに依存しません。押す・動かす・離すイベントとログ領域が実際に広がることを確認し、ログ履歴を維持します。Expandは復活させません。

Desktop 0.14.6ではFirmwareの先頭をImage sourceにします。GitHub listではTarget / Firmware / Format、その下にURL・履歴・一覧を表示します。Local fileではGitHub用の設定欄を隠し、基板を明示するTargetだけを残します。形式は検証済みファイル内容、既知の種類はファイル名から判定し、FPGA IDから基板リビジョンを推測しません。共通ケーブル欄は取得元別の領域の後、Program imageの前に置きます。切替時も選択を保持し、古い一覧の応答を破棄します。

Desktop 0.14.7ではLocal fileのTarget欄を削除し、ファイル選択だけにします。対象・種類は既知の公式ファイル名、形式は検証済みの内容から判定します。不明な名前や選択基板と矛盾する名前では書き込み前に停止します。DAQマニュアルで共通とされるAMANEQ Skeltonはv1/v4互換プロファイルを使い、JTAGから基板版を確定したとは扱いません。GitHub用設定は維持し、ケーブルの表記をJTAG cable:にします。

Desktop 0.15ではCDCE62002の選択欄を20文字幅に短縮し、Files are validatedの説明文を削除します。IPタブ名はIP addr.に変更し、EEPROM IP / Current IPのラジオボタンを使い、EEPROMを既定にします。項目ラベルに:を付けます（ボタンやタブ名は除く）。一覧取得は1件ずつ実行し、重複タイマーと古い応答のエラー表示を抑制します。GitHubのAPI情報は設定間で共有し、通常5分・固定コミット情報24時間のキャッシュを使います。明示更新は通常情報を再取得します。HTTP 403/429ではRetry-After・リセット時刻、最低60秒まで再送を止めます。アクセス制限中は表示された時刻まで待つか、リポジトリをブラウザーで開いて取得し、Local fileを使います。403は権限拒否でも発生し、模擬試験だけで利用者の回線の復旧を確認したとは扱いません。公式資料: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api。

Firmwareにも縦スクロールを設け、狭いウィンドウや拡大表示でも接続欄・Cable・Program imageへ移動できるようにします。「:」は項目ラベルだけに付け、タブ名には付けません。

Desktop 0.15.1では初期表示のChoose Ethernetの説明行を削除します。一時ネットワークの状態行は空欄なら表示せず、操作結果やエラーがあるときだけ表示します。

Desktop 0.15.2では、Messagesが画面全体を占める表示とmacOS USBのInvalid fileを修正します。tk.PanedWindowでタブ180ピクセル・Messages 80ピクセルの下限を設け、Map/Configure後に表示済みの高さが確定してから境界を一度だけ初期化します。利用者のサイズ変更は戻しません。起動確認ではテストが境界を動かす前に両領域の表示を検査し、境界の両端と最小ウィンドウでも確認します。USB検出はioreg -a -l -p IOUSBで行い、BOM・先頭空白・有効な空配列を扱います。空・不正・失敗時はsystem_profilerへ切り替え、-listDataTypesからSPUSBHostDataType / SPUSBDataTypeを選びます。JSONを検証し、シリアル・機種が曖昧なら停止する制約を維持します。両方失敗した場合は双方のエラーを表示します。読み取り成功を実機書き込み成功とは扱いません。同梱版の読み取り専用scanはビルド必須確認のままとし、代替取得分を含む上限を120秒とします。

Desktop 0.15.3では、GitHub tokenの行全体（入力欄、Apply、Open GitHub）を削除します。編集可能なGitHub URL、Refresh list、キャッシュ、アクセス制限時の待機処理は維持します。

Desktop 0.15.4: GUIとCLIの履歴既定件数を5件へ減らします。History limit / --history-limitで1～1000件に変更できる仕様と、キャッシュ・重複排除・アクセス制限時の待機処理を維持します。表示件数の削減で通信回数が必ず半分になるとは扱いません。

Desktop 0.15.5: GitHub一覧では、初期選択を除くカテゴリ（Board / Target / Firmware / Format）の4回目の変更で60秒の強制クールタイムを設け、注意文と残り秒数を表示します。待機中はRefresh list・URL・履歴件数を含む追加一覧取得を止め、変更しても待機時間は延長しません。選択は変更でき、終了時に最後の選択を自動取得します。終了後は変更回数をリセットします。同じ選択の再取得・Local fileは回数に含めません。開始済みの通信は中断せず、古い結果は破棄します。これはGitHub側の403/429制限の解除を保証しません。

Desktop 0.15.6では前版の繰り返し周期を廃止します。起動中のカテゴリ変更を累計し、最初の3回のみ待機なし、4回目以降は変更のたびに60秒待機します。待機中の変更は最後の選択から60秒へ再設定し、同じカテゴリの更新は延長しません。変更回数と待機なし残り回数を表示し、GitHub API残数とは区別します。Why?で理由と動作を説明します。HelpリンクでEEPROM IP/Current IP、Target IP/Ping、BIT/MCS/JTAG、MPC/MPCX、一時ホストIP/NIC/Mask/DHCP、Jitter Cleaner/永続保存を英語ポップアップにまとめます。通常画面には長い説明を増やさず、リンクはキーボードでも開けます。説明を開くだけでは通信・書き込み・ホスト設定変更を行いません。

Desktop 0.15.7: メッセージ欄の区切りは、追加したドラッグバー1本だけを表示します。標準PanedWindowのsashは幅・余白を0、flat、ハンドル非表示にし、二重線を除きます。独自バーのドラッグ処理、180/80ピクセルの最小ペイン高さ、起動後の初回配置、履歴表示は維持します。

Desktop 0.15.8: ケーブルのラベルをJTAG cable:へ短縮し、同じ行のHelpでJTAGの意味、自動検出、Rescan、複数ケーブルのシリアル選択、FT232HだけではHS3と断定できないことを説明します。Ethernetアダプターとの違いを明記し、自動選択の安全ガードや書き込み動作は維持します。

Desktop 0.15.9: 上部のLanguage / 言語でEnglish / 日本語を切り替えます。既定はEnglishで、項目・ボタン・タブ・待機回数と秒数・Help/Why?の説明を切り替えます。ファームウェア名、リポジトリ、ファイルパス、IP、診断ログとバックエンドのエラーは英語のまま維持します。翻訳は表示専用で、言語変更は選択値や通信、クールタイム回数を変更しません。ソースのコメント・識別子は英語を維持し、日本語の翻訳文字列のみui_language.pyへ分離します（以前のUIも英語のみとする規則に対する明示的な変更）。各言語のHelp項目をそろえ、表示用StringVarと操作用StringVarを分離します。言語設定は起動中のみで、CLIは従来どおり英語です。


Macの署名・公証はGitHubのmacOSランナーで実行し、管理者のMacでのビルド・署名作業は不要です。手動のSign and notarize macOS releaseワークフローとmacos_notarization.pyは、App Store ConnectのチームAPIキーまたはApple Accountのアプリ用パスワードに対応します。Actions Secretsの初期登録は必要です。実際にAppleのAccepted・チケット検証・Gatekeeper確認を通るまでは公証済みと扱いません。初回のSecrets登録とブラウザーだけで実行する手順は[開発者向け資料](FOR_DEVELOPERS.ja.md)を参照してください。秘密鍵・パスワードをチャットやGitへ出さないでください。

公証タイムアウトの復旧: 実行39025172325は両アーキテクチャの署名後、notarytool submit --wait --timeout 30mが終了コード124になりました。待機時間切れであり、Appleの却下を示すものではありません。提出は待機と分け、UUID・提出した署名済みsubmission.zipのSHA256を直ちに保存し、状態取得と待機（既定90分）を行います。保留・最終状態、標準出力・エラー、Appleのログを保存します。notary-stateアーティファクトにはアーキテクチャ別の提出ZIPと元リリース名を必ず保存し、証明書・秘密鍵・キーチェーンを含めません。再開時は同じ元リリースと前回の実行IDを指定します。保存ZIPのハッシュを照合し、再署名・再提出せず同じ申請を確認し、Acceptedの後だけチケットを添付します。署名やタイムスタンプを変えたアプリへ古い申請IDを流用してはいけません。公証済み配布は両版のチケット検証・Gatekeeper・画面テスト完了後に限ります。main上の公証ヘルパー・ワークフロー変更では最新のテスト済みプレビューを対象に実行します。手動実行では元リリースとresume_runを指定できます。旧実行では提出済みZIP・IDを保存していないため、新しいアーティファクト再開機能で直接再開できません。

全ネットワークタブのTarget IP行でPing横にget_versionを配置する。hul-common-libに合わせ、BCT 0xe0100000を0x10000間隔の4バイトレーンでリトルエンディアンとして読み、上位16ビットのFW IDと10進のmajor/minorを表示する。UIスレッド外で実行し、結果・エラーはメッセージ欄へ送る。レジスター書き込みや不明IDからの基板リビジョン推定は行わない。

## ネイティブWindows・Linuxデスクトップ版

今回のユーザー依頼はmacOSに加えてネイティブWindows・Linuxデスクトップ版を明示的に追加するもので、従来のWindowsはWSL優先という境界に優先します。build-desktop-app.pyとdesktop-app.ymlを使用します。Windowsはユーザーのwindows-hs3-d2xxブランチの3e5727bc1126307a0838d62f21971a2fa8f6a12fをUSE_FTDI_D2XX=ON、ENABLE_USB_SCAN=OFF、ENABLE_UDEV=OFFでビルドします。Linuxはbf2b52916e7b6216ba1cc0b30933827d7735b05dのままです。コミット・対応ソースの来歴とXC7K160Tブリッジを保持してください。Linuxローダーはruntime/linux/bin、Windowsの補助コマンドは.exe付きで探索します。固定済みPOSIX版SiTCP補助コマンドは変更せずWindowsでCygwinビルドし、必要なランタイムを同梱します。検証済みEEPROMロジックを書き換えないでください。Windows D2XXは既存FTDI CDM/System32のftd2xx.dllを使うため、WinUSBへの置き換えを要求しないでください。このパッケージではlibwdiとドライバー切り替えボタンを省きます。選択したローダーの読み取り専用--scan-usbでシリアルの接続可能性を確認し、使用中・重複シリアルを拒否し、物理HS3確認後も接続可否判定を保持します。ホストの一時IP自動設定は引き続きmacOS専用です。同梱GUI/CLI/ローダー/補助コマンドの起動検査を要求し、ローカルWindows・Linuxのビルドと起動検査は成功しています。これと未実行のホストCI・実機検証を区別してください。Cygwin/iconv/intlのランタイム依存と、バージョンを照合してSHA512を検証した対応ソースを同梱してください。フォルダー全体とSHA256付きアーカイブを保持します。Actions artifactは30日保存で自動Releaseは行いません。

MCSではブリッジのdump/writeコマンドに--skip-resetを明示し、アクセス後のSRAM状態をローダーの既定動作に任せないでください。全バックアップのSHA256を保存し、バックアップ後に型番・JEDEC由来の識別情報・容量を再検出して、変化があれば-fの前で停止します。失敗時も全バックアップを保持してください。

Windows D2XXの実機検証：AMANEQ-official/StrLrTdcのコミットd1b625988b5d0d243be0e725e56dd4ded6b89d7bにあるAMANEQ v4 LR-TDC v2.AのMCSを、物理確認したHS3と既存FTDIBUSドライバーで書き込みました。JTAGはXC7K160Tを1個、フラッシュはS25FL128S、JEDEC 012018、16 MiBでした。消去前に全バックアップとSHA256を保存し、識別情報を再照合してから書き込み、MCSペイロード全6,692,572バイトが別のフラッシュダンプと一致しました。--skip-resetでSPIブリッジをSRAMに残しています。電源再投入後の起動、DAQ・ネットワーク動作、BITロード、macOS/Linuxでの実機書き込みは未検証です。ドライバー変更、独立したFPGAリセット、電源の再投入は行っていません。私的なバックアップ・ログはGitへ含めないでください。

READMEの冒頭にOS・CPU別のダウンロードリンクと公開状況を明示します。既知の配布ファイルは直接リンクし、未公開・ビルド失敗・期限切れをダウンロード可能と記載しません。Actions成果物ではワークフローURL、成功実行、Artifactsの位置、ログイン要否、展開・起動手順を示します。UTF-8で保存し、日本語の言語リンクの表示とMarkdown括弧・リンク先を確認してください。
