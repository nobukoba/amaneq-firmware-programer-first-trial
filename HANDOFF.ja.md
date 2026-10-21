# 開発引き継ぎ — 2026-10-21

**Language: [English](HANDOFF.md) | 日本語**

再開前にこのファイルと [AGENTS.md](AGENTS.md) を読んでください。ここにある内容が現在の状態で、以前のWSL優先・WinUSB必須という説明に優先します。`programer` の綴りを維持してください。

## 現在の実装

- macOSは既存のApple Silicon／Intel向けアプリビルダーを維持しています。
- `build-desktop-app.py` でネイティブWindows x64 ZIPとLinux x86_64 tar.gzを作成します。Python/Tk、CAデータ、openFPGALoader、非圧縮XC7K160Tブリッジ、4種類のSiTCP補助コマンドを同梱します。
- `.github/workflows/desktop-app.yml` は新しい両OS版をビルドし、30日保存のActions artifactを作成します。Releaseには公開しません。[実行39468344602](https://github.com/nobukoba/amaneq-firmware-programer-first-trial/actions/runs/39468344602)、コミット `6cdc836` でWindows・Linuxともにビルド、112件のテスト、GUI起動・CLI・ローダー・補助コマンドのチェック、成果物アップロードが成功しました。READMEのリンクからGitHubログイン後に取得できます。
- Windowsは `nobukoba/openFPGALoader` の `windows-hs3-d2xx` ブランチ、コミット `3e5727bc1126307a0838d62f21971a2fa8f6a12f` を `USE_FTDI_D2XX=ON`、`ENABLE_USB_SCAN=OFF`、`ENABLE_UDEV=OFF` で使います。同じフォークの `master` に置き換えないでください。
- Windowsは導入済みFTDI CDM／System32の `ftd2xx.dll` を使います。WinUSBへの変更やlibwdiは不要で、通常のデスクトップ版にはドライバー切り替えボタンを表示しません。Vivadoと本アプリは、切り替える際に相手側がケーブルを解放する必要があります。
- WindowsのMCSパス処理とSiTCP補助コマンドには引き続きCygwin/cygpathを同梱します。補助コマンドには `cygwin1.dll`、`cygiconv-2.dll`、`cygintl-8.dll` が必要です。対応ソースはパッケージのバージョン・サイズ・SHA512を検証し、ライセンスと同梱します。アプリ全体がWindows標準ライブラリだけで動くとは説明しないでください。
- Linuxはローダーのコミット `bf2b52916e7b6216ba1cc0b30933827d7735b05d` とlibftdi/libusbを維持します。ローカル版はUbuntu 26.04向け、CIはUbuntu 24.04向けです。USB権限・udevルールはホスト側の設定です。macOSもlibftdi/libusbを使います。

## 検証できたこと

ネイティブWindows／Python 3.12とLinux／WSL／Python 3.14で111件のオフラインテストが成功しました。展開したWindows/Linuxパッケージで、システム標準PATHのみを使ったGUI起動、CLIヘルプ、ローダーの対応一覧、4種類の補助コマンドのヘルプを確認済みです。画面レイアウトや基板のネットワーク動作の検査とは区別してください。

利用者の明示的な許可と物理HS3確認を受け、ネイティブWindows D2XXアプリで次を実機検証しました。

- 対象：AMANEQ v4、LR-TDC v2.A、MCS。
- ファームウェア：`AMANEQ-official/StrLrTdc`、コミット `d1b625988b5d0d243be0e725e56dd4ded6b89d7b`、`mcs/amaneq-4-strlrtdc-v2.A.mcs`。Git blob・サイズ・内容を検証済みです。
- 実機：XC7K160Tを1個、IDCODE `0x0364c093`。S25FL128S、JEDEC `0x012018`、16 MiB。既存FTDIBUSドライバーを維持しました。
- 消去前に16 MiB全体のバックアップとSHA256を保存し、バックアップ後にフラッシュ識別情報を再照合しました。MCSペイロード全6,692,572バイトが別のフラッシュダンプと一致し、終了コードは0でした。
- `--skip-reset` によりSPIブリッジをSRAMに残しました。ドライバー変更、独立したFPGAリセット、電源の再投入は要求していません。利用者には手動で電源を入れ直して起動確認するよう伝えました。

この最後の観測から基板の現在状態を決めつけないでください。その後の電源再投入・起動確認はまだ報告されていません。この特定の書き込み許可は、将来の無人書き込みへの許可ではありません。

## 維持する安全動作

- ケーブルの一意性と物理型番を確認します。FT232HのVID/PIDだけではHS3を識別できません。
- Windowsは選択したローダーの読み取り専用D2XXスキャンでシリアルの利用可能性を確認し、使用中・重複・利用不可のシリアルを拒否します。物理HS3確認でドライバー判定を上書きしないでください。
- MCSでは `--skip-reset` を明示し、容量全体のバックアップとSHA256を保存し、`-f` の前に識別情報を再検出します。書き込み後は別の読み戻しと全イメージバイトを比較します。失敗時は停止し、破壊的な再試行はしません。
- USBドライバー、ホストIP、電源・リセットを自動変更しないでください。実ファームウェア、バックアップ、ライセンス、ログ、ローカルランタイムはGitへ含めません。

## 開発の再開

```bash
git status --short
python -m unittest discover -v
python amaneq-firmware-programer.py --help
python build-desktop-app.py --help
```

Tkを導入したPythonを使ってください。依存の導入・コンパイル全手順は `.github/workflows/desktop-app.yml` と [FOR_DEVELOPERS.ja.md](FOR_DEVELOPERS.ja.md) にあります。上のコマンドは実機へ書き込みません。書き込みショートカットをテストとして実行しないでください。

元の開発checkoutでは、Git対象外の生成物は `dist/windows-d2xx/`、`dist/windows/`、`dist/linux/` にあります。私的な実機記録・バックアップは `logs/windows-d2xx-mcs-*/`（`*result.json`、`console.log`、全バックアップ、読み戻し）、ファームウェアの出所は `firmware/downloads/` にあります。新しくcloneした環境には含まれません。ポータブルなビルドツールは隣の `.amaneq-build-tools` ディレクトリーに置きました。引き継ぎのためにこれらをアップロードしないでください。

## 残っている作業と利用者の状況

1. Windows/LinuxのCIは上記実行で成功しました。Actions成果物は30日保存です。期限切れや更新時は対象OSのジョブと成果物を再確認してください。
2. 電源再投入後の起動・DAQ・ネットワーク動作、BITロード、macOS/Linuxの実機書き込みは未検証です。
3. FTDI/D2XXを維持する目的はVivadoとの共存です。フォークには以前の共存検証記録がありますが、今回のMCS書き込み後にVivadoを再接続する確認は行っていません。実施済みと説明しないでください。
4. 利用者向けにWindowsアプリを起動しましたが、現在の起動画面は目視確認していません。Computer Useの説明ファイルはありますが、このセッションには必要な `node_repl` ランタイムがありませんでした。ライブ画面が見えるとは説明しないでください。利用者が送った画像は確認できます。
5. 利用者はスマホでも会話を読んでおり、PC内ファイルへのリンクは開けませんでした。プッシュ後はREADME・引き継ぎへのHTTPS GitHubリンクを使うか、必要な内容をチャットに表示してください。

## 2026-10-22のUI更新

AMANEQのみの選択、既定のタブなしSimple modeと従来のExpert mode、最新版ファイル名・版・コミット表示、Helpの位置変更、コピー用メニューを追加しました。Initialize XG EEPROMは既定ONです。Simpleでは固定クロック・任意ライセンス・EEPROM IPを読み戻し付きで先に設定し、最後にMCSを書き込んで照合します。HR-TDCではSimpleネットワーク処理を省きます。DIP1=0の案内は既定IPで、EEPROMの独自IPはDIP1=1です。実機の新しい一括処理は未検証です。

最終検証: コード `be2ce6c` で115件のテストが全OSのPython 3.10/3.12で成功しました。Mac両アーキテクチャのビルド・起動・公開は実行39669574244、Windows/Linuxのビルド・起動・成果物作成は実行39669574336で成功しています。Mac最新版は `macos-preview-v0.15.9-be2ce6c`（未公証）。READMEの全OSリンクはこのコードの配布物に更新しました。


## 公開ダウンロードの自動更新

現在の配布方式は以前のActions限定案内を置き換えます。`publish-desktop.yml` は同一リポジトリmainの成功したビルドのみ取得し、SHA256照合後、Windows/Linuxは `desktop-preview`、未公証Macは `macos-preview` の固定Release URLへ公開します。一般利用者のGitHubログインは不要です。READMEは固定URLを維持し、ビルドごとに変更しません。失敗・PR・fork・古いビルドで成功版を上書きしません。コミット別Releaseと `build-info.json` を残します。公証ワークフローとは独立で、公開処理はAppleへのサブミットを行いません。テスト: `python -m unittest discover -s .github/scripts -p 'test_*.py' -v`。
