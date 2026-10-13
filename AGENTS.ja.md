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

macOSの機器検出・書き込みは未実装と明示します。cygpathはWindowsのパス変換用で、USBドライバーではありません。

```bash
python3 -m unittest test_amaneq_firmware_programer -v
python3 amaneq-firmware-programer.py --help
```

追跡するテストは合成データを使います。実ファームウェア・ダンプ・認証情報・独自ライセンス・ドライバーバックアップ・ローカルランタイムはGitへ入れません。実機を変えるテストは別の明確な許可が必要です。専用スクリプトの確認には--helpを使います。

コードを通常のブロック構造で読みやすく保ち、コメントとガードを維持します。py/shのGit実行権限とcmdのCRLF設定を維持します。README・開発者文書・AGENTSの英語/日本語を同期し、ユーザーが許可したAI向け指示にも長期的な訂正・知見を反映します。プロジェクト固有の事実を万能な規則にしません。
