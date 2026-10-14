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

対象基板は同じFPGA IDなので、JTAGだけでリビジョンや本体/メザニンを確定できません。既知名の機種・種類は照合しますが、任意に改名したファイルではその証拠は消えます。物理ターゲットの指定は利用者の意図です。BITはSkeletonだけに限定します。

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
