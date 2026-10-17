"""Optional Japanese GUI presentation; backend identifiers and logs stay English."""

import re
import tkinter as tk
from tkinter import ttk

JAPANESE = {
    "Language:": "言語:",
    "Board:": "基板:",
    "UI size:": "表示倍率:",
    "Firmware": "ファームウェア",
    "Jitter Cleaner": "ジッタークリーナー",
    "MPC / MPCX": "MPC / MPCX",
    "IP addr.": "IPアドレス",
    "Image source:": "取得元:",
    "GitHub list": "GitHub一覧",
    "Local file": "ローカルファイル",
    "JTAG cable:": "JTAGケーブル:",
    "Rescan": "再検出",
    "Target:": "対象基板:",
    "Firmware:": "種類:",
    "Format:": "形式:",
    "GitHub URL:": "GitHub URL:",
    "Refresh list": "一覧を更新",
    "History limit:": "履歴件数:",
    "Default 5 images; includes tags and firmware commits": "既定5件（タグ・変更履歴を含む）",
    "Why?": "理由は？",
    "Help": "説明",
    "Type": "形式",
    "Version": "バージョン",
    "Firmware image": "ファームウェアファイル",
    "Tag / commit": "タグ / コミット",
    "Local .bit file / .mcs file": "ローカルの .bit / .mcs ファイル",
    "Choose file": "ファイルを選択",
    "Program image": "書き込む",
    "Use WinUSB": "WinUSBに変更",
    "Restore Vivado driver": "Vivadoドライバーに戻す",
    "Temporary static host IP address (DHCP preserved, restored on exit)": "一時ホスト固定IP（DHCPを保持・終了時に復元）",
    "NIC:": "NIC:",
    "Refresh": "更新",
    "Host IP:": "ホストIP:",
    "Mask:": "マスク:",
    "Apply temporarily": "一時的に適用",
    "Restore network": "ネットワークを復元",
    "Messages:": "メッセージ:",
    "Follow latest": "最新を追尾",
    "First": "先頭",
    "Latest": "末尾",
    "Target IP:": "接続先IP:",
    "Ping": "Ping",
    "MPC / MPCX file:": "MPC / MPCXファイル:",
    "Select input / output frequencies of CDCE62002 chip (MHz):": "CDCE62002の入力 / 出力周波数（MHz）:",
    "Save clock settings for the next power-on": "次回起動用にクロック設定を保存",
    "Apply": "適用",
    "Initialize XG EEPROM from current settings before license programming": "ライセンス書き込み前に現在の設定でXG EEPROMを初期化",
    "New device IP:": "新しい基板IP:",
    "EEPROM IP": "EEPROM IP（保存）",
    "Current IP": "Current IP（実行中）",
    "Read": "読み取り",
    "Check": "照合",
    "Write MPC/MPCX": "MPC/MPCXを書き込む",
    "Read IP": "IPを読み取る",
    "Write IP": "IPを書き込む",
    "The unidentified FT232H cable is physically an HS3": "不明なFT232Hケーブルの実物がHS3であることを確認した",
    "Scanning connected cables...": "接続中のケーブルを検出しています…",
    "Loading latest firmware images...": "最新のファームウェア一覧を読み込んでいます…",
    "Loading matching firmware images...": "該当するファームウェア一覧を読み込んでいます…",
    "History limit must be an integer between 1 and 1000.": "履歴件数は1～1000の整数で指定してください。",
    "List acquisition will resume with the selected category after cooldown.": "待機終了後、選択したカテゴリの一覧を取得します。",
    "Repository changed. Loading matching images...": "リポジトリが変更されました。一覧を取得しています…",
    "No file selected.": "ファイルが選択されていません。",
    "No file selected. Choose an MPC/MPCX file to detect its type.": "MPC/MPCXファイルを選択すると、内容から種類を判別します。",
    "Checking file...": "ファイルを確認しています…",
    "STAG firmware and clock maps require an official reference.": "STAGのファームウェア・クロック設定は公式資料の確認が必要です。",
    "STAG clock register map is not verified; clock writes are unavailable.": "STAGのクロックレジスターが未確認のため、書き込めません。",
    "Temporary IP automation is available on macOS. On Linux/WSL configure the host Ethernet to 192.168.10.20/24 before using network operations.": "一時IPの自動設定はmacOSに対応しています。Linux/WSLではネットワーク操作の前にホストEthernetを192.168.10.20/24へ設定してください。"
}

HELP_JAPANESE = {
    "jtag": [
        "JTAGケーブルと自動検出",
        "JTAGは、FPGAの動作を書き換えたりフラッシュへ保存したりするための接続です。JTAGケーブルはUSB接続の書き込み器で、Ethernetのネットワークアダプターとは別物です。\n\n起動時に接続ケーブルを自動検出します。抜き差しした後は「再検出」を押してください。識別できたケーブルが1本なら自動選択し、複数ある場合は目的のシリアル番号を選びます。勝手に先頭のケーブルを選ぶことはありません。\n\nFT232Hは複数の機器で同じUSB識別番号を使います。番号だけではHS3と断定できません。不明なFT232HをHS3として使う場合は、実物がHS3であることを確認してください。\n\n検出や説明の表示では、基板への書き込みやUSBドライバー変更は行いません。「書き込む」を押した後、従来の確認処理を経て実行します。USBへのアクセス権など、ホスト側の準備が必要な場合があります。"
    ],
    "cooldown": [
        "なぜ待機するの？",
        "基板・種類・形式を変更すると、最新版や過去版を探すためにGitHubへ複数回アクセスする場合があります。未認証のREST APIは通常、同じ外向きIPアドレスから1時間60回までです。同じ研究室の別のコンピューターと枠を共有する場合もあります。\n\nこのアプリでは起動後の最初の3回は待機なしでカテゴリを変更できます。4回目以降は毎回60秒待ちます。待機中に変更すると、その選択から60秒を数え直します。待機終了後も累計回数はリセットしません。初期表示や同じカテゴリの更新は回数に含みません。「待機なし残り」はアプリ内の回数であり、GitHub側のアクセス残数ではありません。\n\n待機終了後、最後に選んだ一覧を自動取得します。ローカルファイルは待機中も利用できます。アクセス頻度を抑えるための仕組みで、GitHub側の制限回避を保証するものではありません。サーバーが指定する待機時間が優先される場合があります。\n\n公式資料: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"
    ],
    "firmware": [
        "ファームウェア・形式・ケーブル",
        "対象基板は実際の基板とリビジョン、種類は用途を表します。実物と目的に合うものを選んでください。FPGAの識別番号だけでは、すべての基板を区別できません。\n\nBITはFPGAの作業用メモリー（SRAM）へ一時的に読み込みます。電源を切ると失われ、従来のフラッシュ内容は残ります。MCSは電源を切っても残るフラッシュへ書き込み、後の起動に使います。どちらも書き込み中は実行中の機能へ影響します。\n\nGitHub一覧は選択した版をダウンロードし、ローカルファイルはコンピューター上のファイルを使います。拡張子だけでなく内容を検証します。履歴件数は表示候補数で、通信回数ではありません。最新版は、既定ブランチにある対象ファイル名の版番号から選びます。\n\nJTAGケーブルはUSB接続の書き込み器です。Ethernetアダプターではありません。複数接続時はシリアル番号を選択します。一覧表示だけでは書き込まず、「書き込む」で確認処理を経て実行します。"
    ],
    "ip": [
        "EEPROM IPとCurrent IP",
        "接続先IPは、今基板へアクセスするためのアドレスです。新しい基板IPは、これから基板へ書き込むアドレスです。コンピューター側のIPではありません。\n\nEEPROM IPは、電源を切っても残るメモリーへアドレスを保存します。実行中のアドレスは、基板が保存設定を読み直すまで変わらない場合があります。\n\nCurrent IPは、実行中のアドレスを変更し、EEPROMには保存しません。再起動や設定の再読み込みで失われる場合があります。実行中IPの書き込みを検証した後、アプリは接続先IPを新しい値へ切り替えます。\n\nラジオボタンを選ぶだけでは書き込みません。「IPを書き込む」で実行します。「IPを読み取る」は読み取りのみです。新しいアドレスがネットワーク内で重複していないことを確認し、変更後の接続先を控えてください。"
    ],
    "target": [
        "接続先IPとPing",
        "接続先IPは基板の現在のEthernetアドレスです。一般的な既定値はSiTCPが192.168.10.16、SiTCP-XGが192.168.10.10ですが、保存設定や実行中の設定によって異なります。必要に応じてCustomを使ってください。\n\nPingはICMPへの応答を確認します。応答がないだけで、基板が存在しない、またはレジスター通信が使えないとは断定できません。コンピューター側のネットワーク設定も必要です。\n\nネットワーク操作はEthernet経由のRBCPを使います。ファームウェアの書き込みはUSB/JTAGで、一時Ethernet設定は不要です。"
    ],
    "host": [
        "一時ホストIP",
        "ホストはこのコンピューター、接続先は基板です。NICはコンピューターのネットワークアダプターを意味します。基板につながるEthernetアダプターを選んでください。\n\n例えばホストIPを192.168.10.20、マスクを255.255.255.0にすると、基板の192.168.10.xと同じローカルネットワークに置けます。ホストと基板には異なる未使用のIPを使います。マスクは同じネットワークの範囲を表します。\n\nmacOSではチェックを付けると設定欄が現れます。「一時的に適用」を押して管理者確認を行うと、DHCP・DNS・ゲートウェイの設定を保持したまま、選択したアダプターへアドレスを追加します。DHCPはネットワークを自動設定する仕組みです。「ネットワークを復元」または通常の終了で、アプリが追加したアドレスを削除します。復元に失敗した場合は表示します。\n\n基板のIPは変更しません。Ethernet操作用の任意設定で、USB/JTAG書き込みには不要です。"
    ],
    "license": [
        "MPC / MPCXファイル",
        "MPCとMPCXは、対象機器向けに提供されるSiTCP / SiTCP-XGの設定・ライセンスファイルです。FPGA用のBIT / MCSではありません。基板向けに発行されたファイルを使ってください。このアプリはライセンスを生成しません。\n\nファイルを選ぶかパスを入力します。拡張子ではなく内容から種類を判別します。MPCなら通常192.168.10.16、MPCXなら192.168.10.10を接続先の候補にしますが、実際の基板アドレスを保証するものではありません。\n\n読み取りは基板情報を取得し、照合は選択データを基板と比較します。書き込みは確認後に選択データを書き込みます。XG EEPROM初期化はライセンス書き込み前に現在のXG設定をコピーする操作です。その準備操作が必要な場合だけ有効にしてください。"
    ],
    "clock": [
        "ジッタークリーナー",
        "CDCE62002は基板のクロック信号を整えるチップです。入力周波数はチップへ供給するクロック、出力周波数は基板とファームウェアの構成に合わせて選びます。MHzは1秒間に100万回の周期を表す単位です。\n\n「適用」は実行中のクロックレジスターを変更します。「次回起動用にクロック設定を保存」が有効なら、検証後にチップ内のEEPROMへも保存します。無効ならレジスター変更のみです。周波数を選ぶだけでは書き込みません。\n\n不適切なクロックはDAQや通信を中断する場合があります。実験のクロック構成に従ってください。IPアドレスだけでは正しい周波数は分かりません。STAGのレジスターが確認できるまでは、STAGのクロック書き込みは使えません。"
    ]
}


def translate(text, language):
    if language != "ja":
        return text
    if text in JAPANESE:
        return JAPANESE[text]
    match = re.fullmatch(r"Changes: (\d+) \| No-wait changes left: (\d+)", text)
    if match:
        return f"変更回数: {match[1]} | 待機なし残り: {match[2]}"
    match = re.fullmatch(r"Cooldown: (\d+) s", text)
    if match:
        return f"待機: あと{match[1]}秒"
    if text.startswith("Detected from contents: "):
        return "内容から判別: " + text.partition(": ")[2]
    return text


class LanguageManager:
    """Translate presentation widgets without changing operation variables."""

    def __init__(self, root):
        self.root = root
        self.language = "en"
        self.widgets = []
        self.variables = []
        self.tabs = []
        self.headings = []
        root.ui_language = self
        self.collect(root)

    def collect(self, widget):
        if isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                self.tabs.append((widget, tab, widget.tab(tab, "text")))
        if isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                self.headings.append((widget, column, widget.heading(column, "text")))
        if isinstance(widget, (ttk.Label, tk.Label)) and widget.cget("textvariable"):
            name = str(widget.cget("textvariable"))
            proxy = tk.StringVar(master=self.root)

            def update(*unused, source=name, destination=proxy):
                destination.set(translate(str(self.root.getvar(source)), self.language))

            token = self.root.tk.call("trace", "add", "variable", name, "write",
                                      self.root.register(update))
            self.variables.append((proxy, update))
            widget.configure(textvariable=proxy)
            update()
        elif "text" in widget.keys() and widget.cget("text"):
            self.widgets.append((widget, str(widget.cget("text"))))
        for child in widget.winfo_children():
            self.collect(child)

    def set_language(self, language):
        if language not in ("en", "ja"):
            raise ValueError("Unsupported interface language.")
        self.language = language
        for widget, original in self.widgets:
            widget.configure(text=translate(original, language))
        for notebook, tab, original in self.tabs:
            notebook.tab(tab, text=translate(original, language))
        for tree, column, original in self.headings:
            tree.heading(column, text=translate(original, language))
        for unused, update in self.variables:
            update()
        self.root.update_idletasks()
