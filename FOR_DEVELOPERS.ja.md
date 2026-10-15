# 開発者向け資料

**Language: [English](FOR_DEVELOPERS.md) | 日本語**

## 構造・実行環境

本体はamaneq-firmware-programer.pyの1つです。ハイフンとprogramerの綴りは利用者の指定です。テストはimportlibで読み込み、dataclass宣言の前にsys.modulesへ登録します。専用スクリプトは引数を固定する薄い呼び出しで、共通ヘルパーを通して同じprogram実装を使います。

Python 3.10以上・標準ライブラリと、外部openFPGALoaderが必要です。本体はPATHまたは--loader、任意に配置したinstalled/ucrt64を使います。SPIブリッジは任意の同梱配置、実行ファイルの導入prefix、/usr/share、/usr/local/shareを調べ、--bridgeで明示できます。第三者のバイナリとブリッジはGitに含めません。

WindowsヘルパーはAMANEQ_PYTHON、py -3、pythonの順です。cygpathはPATH、AMANEQ_CYGPATH_DIR、--cygpath-dir、Git for Windows、任意のローカルtools配置で探します。個人のPCパスを固定しません。利用者が確認したHS3のシリアルはAMANEQ_HS3_SERIALSへカンマ区切りで指定できます。

## 取得・履歴

標準配布先はAMANEQ-officialの各種類と、Skeletonのspadi-alliance/AMANEQ-Skeletonです。Skeletonのv1/v4共通名はDAQマニュアルに共通利用が明記されているため認めています。

ブランチ・タグをコミットへ解決してからtreeとrawファイルを取得し、長さとGit blobのSHA1を照合します。保存する出典にはSHA256も記録します。直接URLはGitの同一性保証がないため、既知SHA256の指定で追加照合できます。どちらも内容を検査します。

upstream名の版番号は16進成分で比較。latestは既定ブランチ内の一致ファイルであり、Releaseタグの最新版とは限りません。履歴はタグとコミットをまとめて日時順にし、現在ブランチを含む合計件数を制限します。annotated tagなどを拡張するときは実API応答も確認します。

通信は無応答タイムアウト・サイズ上限・Content-Length照合を使い、DNS/未接続・タイムアウト・HTTP・TLS・途中切断・JSON/HTML不正・ハッシュ失敗を英語で区別します。通信失敗後の破壊的再試行はしません。

## ファイルと対象

BITヘッダーにはpart/package・design・日時・payloadがあります。MCSはレコード、チェックサム、拡張アドレス、EOF、重複と32MiB上限を検査します。同期語とIDCODEパケットを読み、revision bitsを除いてXC7K160Tの0x0364c093に照合します。

対象基板は同じFPGA IDなので、JTAGだけでリビジョンや本体/メザニンを確定できません。既知名の機種・種類は照合しますが、任意に改名したファイルではその証拠は消えます。物理ターゲットの指定は利用者の意図です。対応する各種類でBIT / MCSを選べます。

## 書き込み手順

1. 取得・対話選択より先にケーブルを確認。複数台でシリアル未指定なら表示して停止します。
2. メザニンのGitHub MCS自動経路は、選択・取得の前にSPIフラッシュを判定します。判定はSRAMだけを変更します。
3. ファイル・種類・ターゲット・partと単一FPGAチェーンを検証します。
4. BITはSRAMへロードし、DONE=1を要求します。
5. MCSはSPIブリッジ、JEDEC・モデル・容量・再照合、全フラッシュバックアップ、書き込み、イメージ範囲のダンプ、全バイト比較、結果JSONの順です。

疎なMCSの穴はFFとし、全バックアップの長さを確認してから消去します。失敗時もバックアップ・エラー情報を保存し、自動回復書き込みはしません。SPIブリッジがSRAMに残る場合があるため、起動確認は利用者の電源再投入で行います。

署名：012018はS25FL128S/16MiB、20bb19はMT25QU256に使われるMicron 256Mbit系列/32MiB、20bb18/20ba18はN25Q128系列/16MiBです。同じJEDECを持つMT25/N25Qの表示名だけで厳密な製品型番は確定できません。モデル・容量の矛盾では消去前に停止します。この対応表は資料・ソース根拠であり、メザニンの実機検証ではありません。

## USB・OS

0403:6014はHS3/HS2/他のFT232Hで共通。Linuxはsysfs、Windowsは固定の読み取り専用PnPクエリーを使い、利用者文字列をPowerShellへ埋め込みません。LinuxのFTDI選択はbus/device、Windowsはserialです。Xilinx候補は既知03fd IDと本体の対応一覧で判断します。upstreamのXilinxコンストラクターへbus/serialが渡らないため、複数純正ケーブルの一意選択を保証しません。

対象はWindows WSL2・Linuxネイティブ・macOSネイティブです。macOSはioregのplistを解析しFTDIをシリアル指定、Linux/WSLはsysfsとbus/device指定を使います。WSLはusbipd-win転送とLinuxのUSB権限が必要です。macOS検出の模擬テストと実機書き込みの検証を区別してください。Windowsネイティブは従来の実装・実機観測として保持します。

## 2026-10-14の実機記録

WindowsでopenFPGALoader v1.1.1とHS3を直接呼び、FTDIBUSからWinUSBへ変更後にXC7K160Tへ接続しました。変更前はUSB open -4。BITはDONE=1、MCSは012018のS25FL128Sを認識して完了しました。

--verifyは終了0でもVerify not supported in this modeと表示。別のダンプで6,692,572バイトすべてが一致しました。payload SHA256は15c99849279621b90f74c9ffac898fe234698204b7c51a1e5a09aac068bfa32b、MCSファイルは8d7d8029b183090b16364dd1668e3d6c04523a0384318dc25180929ca47ea9f2です。

WindowsのSPIブリッジ読み込みにはcygpathが必要でした。JTAG reset後はDONE=0のままで、フラッシュ起動を確認できませんでした。同じBITを再ロードしてDONE=1へ戻しました。完成したPythonの手順・全バックアップ、メザニン、Linux、Macの書き込み、コンテナを実機検証したとは表現しません。

実ライセンス、ダンプ、キャプチャー、第三者バイナリは同梱しません。SiTCP/SiTCP-XGライセンスは別のEEPROM設定です。

## テスト・維持

```bash
python3 -m unittest test_amaneq_firmware_programer -v
python3 -m compileall -q amaneq-firmware-programer.py test_amaneq_firmware_programer.py
```

初回公開時の36テストはオフライン・合成データ・模擬機器で自己完結します。解析、破損・重複、拡張子違い、ケーブル一意性、バックアップ順序、読み戻し失敗、ネットワーク、直接URL、履歴、Skeleton互換、メザニン自動選択を検証。実機の証拠とは区別します。

CIはUbuntu/Windows/macOS、Python3.10/3.12で同じテストを実行します。Macでテストが通ってもUSB実装の証明にはなりません。専用スクリプトの通常実行は避け、--helpを確認します。

Blackで可読性を保ち、コードは英語、利用者例は英日同期にします。shebang、LF、Git実行権限、cmdのCRLFを維持し、公開前に秘密情報や個人パス・生成ディレクトリが混ざっていないか確認します。

Windows用setup-windows-wsl.ps1は明示実行するホスト導入用です。Setupは管理者でusbipd-winとWSL内aptパッケージを導入します。Attach/DetachはBUSID必須、自動選択・書き込み・再起動はしません。通常のPython実行はホスト設定を変更しません。導入の実行検証と構文・モック検証を区別してください。

## 明示操作によるWindowsネイティブのUSB切り替え

以前のWSL運用に加え、利用者がアプリ内のドライバー切り替えを明示的に依頼しました。amaneq-firmware-app.pyはデスクトップ画面、windows_usb.pyはUSBボタンと確認後だけ使う処理です。通常のCLI・書き込みから自動変更しません。管理者昇格はドライバー処理だけです。Windows x64のHS3が対象で、実物の確認とFT232Hが1本だけであることを要求し、変更直前にも照合します。

元のFTDIBUS OEMパッケージをpnputilで保存し、LOCALAPPDATA/AMANEQ/usb-drivers配下で全ファイルのハッシュを保管します。元バックアップは上書きせず、欠落・変更・別機器なら復元を拒否します。libwdiは公式v1.5.1 ABIに合わせ、署名・カタログ検査は無効化しません。復元は保存INFとUpdateDriverForPlugAndPlayDevicesWを使い、共有パッケージを削除しません。別FT232Hへの影響をシリアル指定だけで防げるとは説明しません。自動再試行や書き込み失敗後の自動復元はしません。状態を検証し、結果・エラーを残します。

ローカルビルドは未変更のlibwdi v1.5.1（9b23b82a2dd1cbffc16d46c212f92c6bf8c0c602）と公式WDK 8再頒布部品（https://go.microsoft.com/fwlink/p/?LinkID=253170）です。MinGW x64、CC_FOR_BUILD=gcc、--disable-32bit、展開したWindows Kits/8.0を--with-wdkdirへ指定してクロスビルドします。WinUSB資源と実機照合は読み取り確認済みですが、新アプリでの実際の変更・復元は未確認です。過去のZadigでの変更・復元とは区別します。

build-windows-app.py --helpに従い、UCRT64・libwdi DLLと対応ソース・Cygwin binを指定し、PythonとPyInstallerでローカルEXE・ZIPを作ります。libwdiの対応ソース・ライセンスも同梱します。バックアップ、ビルドログ付きソース、個人パスを公開しません。第三者の表示と配布条件を確認してから外部向けバイナリを公開してください。ソース公開・実行ファイルの起動テストは接続機器の変更許可ではありません。

## macOSアプリのビルド

build-macos-app.pyはMac上で実行し、Apple Silicon arm64とIntel x86_64を対応するPythonで別々に作ります。macos-app.ymlはmacos-15とmacos-15-intelを使います。openFPGALoaderをPyInstallerのbinaryとして扱い、dylibを回収・再配置して、システム外への絶対リンクが残れば失敗させます。XC7K160T SPIブリッジは非圧縮で同梱します。openFPGALoader・libftdi・libusbの対応ソース・表示・Homebrewレシピを入れ、版やチェックサムの不一致を無視しません。

.app内へ書き込みや__pycache__生成をしません。GUIのCLI子プロセスは利用者のデータ用ROOTを使い、windowed起動で標準出力がNoneなら復旧します。Macの保存先は~/Library/Application Support/AMANEQです。HS3の機種確認欄は全タブ共通で、Windows用ドライバー変更は無効です。署名・起動・ローダー・機器未接続の検出・依存関係の検査と、実機書き込みを区別します。Developer ID署名・Apple公証は設定していません。dittoでシンボリックリンク・権限・資源を保つZIPを作ります。Artifact保存は30日で、恒久的なRelease配布ではありません。

2026-10-15、Actions実行38740982476でarm64・x86_64の両方のビルド・署名検査・GUI起動・同梱ローダー・機器未接続でのscanが成功しました。47件の模擬テストと通常CIの6構成も成功しました。これはHS3実機書き込みの検証ではありません。

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

## Desktop 0.7の形式・パス欄

Format選択を追加し、履歴探索・件数制限より前に形式を絞り、キャッシュキーにも含めます。BITは従来の明示指定どおりSkeletonのみで、他の種類はMCSだけです。HR-TDCメザニンはhrtdc固定でラベルとFirmware選択欄を隠し、別対象へ戻したら復帰させます。Program imageは1つを維持します。ローカル内容と選択形式の照合はTkスレッド外で書き込み前に行います。MPC/MPCXファイルは1行の読み取り専用パスで、横ホイールと左右・Home/End移動を提供します。編集可能なURL欄の通常カーソル操作は維持します。起動テストで形式切替・欄の非表示と復帰・非常に長いパスを確認します。

Desktop 0.8：New device IPのラベル・入力・runtimeチェック欄を1行に配置します。表記はChange current (runtime) IP instead of saved EEPROM IPとTemporary static host IP address (DHCP preserved, restored on exit)です。動作は維持します。

Desktop 0.9：周波数ラベルとプリセットを1行とし、クロックのボタン名はApplyです。Program image、Write MPC/MPCX、Write IP、Applyは共通Action.TButtonを使い、通常サイズ・通常余白の太字にします。Program imageを全幅に広げたり大型化したりしません。

Desktop 0.10：履歴とは以前の画面ではなく過去メッセージと確認できました。起動中のログを保持し、ホイール・スクロールバー・履歴キーでは自動see(end)を停止します。First/Latest/Follow latestで表示位置を操作し、新規出力で過去の閲覧位置を奪いません。Messagesを縦Panedwindowの可変領域とし、境界ドラッグで高さを変えます。Expandボタンはありません。ウィンドウは最小720x480で拡縮し、UI sizeは元のサイズを保持して既存の名前付きフォントと太字アクションフォントを拡縮します。タブ切替のidleと25ms後に配置・Expose、Map時にCanvas内枠を再配置します。起動確認だけで利用者のMacの描画不具合を目視検証済みと扱いません。画面遷移の履歴は不要です。

Desktop 0.11：通常のクロック画面から実装寄りのHULレジスタマップ説明を削除し、Select input / output frequencies of CDCE62002 chip (MHz):とします。STAG未対応の条件付き表示は維持し、正式なCDCE62002表記を使います。以前のタブ順指定はJitter Cleanerが重複し回答がないため、末尾をIPと解釈し、Firmware / Jitter Cleaner / MPC/MPCX / IPとする前提を明示します。HULは公式ガイドのHadron Universal Logicです。ライブラリの出所は開発資料に記載し、通常の操作欄へ混ぜません。

Desktop 0.12：Target IPの表示は192.168.10.16 (SiTCP default)と192.168.10.10 (SiTCP-XG default)です。補足は表示専用で、Ping/RBCPには検証したIPアドレスだけを渡します。MPC/MPCXファイルの判定後も対応するラベルを選び、Customは維持します。

Desktop 0.13のFirmware表示：lrtdc → LR-TDC、hrtdc → HR-TDC、lrtdc-10g → LR-TDC 10GbE、mikumari → MIKUMARI Hub、skeleton → Skelton（指定表記）です。UI表示だけの対応付けで、CLIオプション・リポジトリ・実ファイル名・キャッシュキーの内部識別名は維持します。

Desktop 0.14では従来のSkeleton限定BIT制限を廃止し、対応する全種類でMCS / BITを選べます。FPGA・対象・ケーブル照合は維持します。BITは一時SRAMロード、MCSは永続フラッシュ書き込みです。MessagesのExpand/Restoreを廃止し、境界のドラッグで高さを変えます。MPC/MPCXパスは左右キー・Home/End・クリックで移動したカーソル位置を横スクロールして表示します。一時IPの有効化チェックはTemporary static host IP address (DHCP preserved, restored on exit)の1行とし、重複見出しを削除します。Write IP直下の説明行も削除します。画面の動作確認では実機書き込みやホストIP変更を行いません。

Desktop 0.14.1では形式選択欄と画像一覧を.mcs file / .bit fileと表示します。内部のmcs / bitに明示的に対応付け、CLIオプション・内容検証・書き込み処理は維持します。
