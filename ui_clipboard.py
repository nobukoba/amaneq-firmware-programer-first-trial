"""Consistent copy/paste menus for desktop text and selectable status labels."""

import tkinter as tk
from tkinter import ttk


def widget_text(widget, all_text=False):
    if isinstance(widget, tk.Text):
        if not all_text:
            try:
                return widget.get("sel.first", "sel.last")
            except tk.TclError:
                return ""
        return widget.get("1.0", "end-1c")
    if isinstance(widget, ttk.Treeview):
        return "\n".join(
            "\t".join(map(str, widget.item(item, "values")))
            for item in widget.selection()
        )
    if isinstance(widget, (ttk.Entry, tk.Entry)):
        if widget.selection_present() and not all_text:
            return widget.get()[widget.index("sel.first") : widget.index("sel.last")]
        return widget.get()
    try:
        if "textvariable" in widget.keys() and widget.cget("textvariable"):
            return str(widget.getvar(widget.cget("textvariable")))
        return str(widget.cget("text"))
    except tk.TclError:
        return ""


def install_copy_support(root):
    def copy(widget, all_text=False):
        text = widget_text(widget, all_text)
        if text:
            root.clipboard_clear()
            root.clipboard_append(text)
        return "break"

    def popup(event):
        widget = event.widget
        menu = tk.Menu(root, tearoff=False)
        from ui_language import translate

        manager = getattr(root, "ui_language", None)
        language = manager.language if manager else "en"
        menu.add_command(
            label=translate("Copy", language), command=lambda: copy(widget)
        )
        menu.add_command(
            label=translate("Copy all", language), command=lambda: copy(widget, True)
        )
        if isinstance(widget, (ttk.Entry, tk.Entry, tk.Text)):
            readonly = isinstance(widget, ttk.Entry) and widget.instate(["readonly"])
            if not readonly and str(widget.cget("state")) != "disabled":
                menu.add_command(
                    label=translate("Paste", language),
                    command=lambda: widget.event_generate("<<Paste>>"),
                )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def visit(widget):
        if isinstance(
            widget, (ttk.Label, tk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton)
        ):
            widget.configure(takefocus=True)
            widget.bind("<Button-1>", lambda event: event.widget.focus_set(), add="+")
            for key in ("<Control-c>", "<Command-c>"):
                widget.bind(key, lambda event: copy(event.widget))
        if isinstance(
            widget,
            (
                ttk.Label,
                tk.Label,
                ttk.Button,
                ttk.Checkbutton,
                ttk.Radiobutton,
                ttk.Entry,
                tk.Entry,
                tk.Text,
                ttk.Treeview,
            ),
        ):
            widget.bind("<Button-3>", popup, add="+")
            if root.tk.call("tk", "windowingsystem") == "aqua":
                widget.bind("<Control-Button-1>", popup, add="+")
        for child in widget.winfo_children():
            visit(child)

    visit(root)
