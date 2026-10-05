# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Dialoghi scuri nello stile dell'applicazione, al posto di tkinter.messagebox.

`messagebox` ha la stessa firma di quello di Tk (showinfo, showwarning,
showerror, askyesno): cambiando l'import i moduli restano com'erano.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ..i18n import N_, tr
from . import frameless, theme

_ACCENT = {"info": theme.ACCENT, "question": theme.ACCENT, "warning": theme.WARN, "error": theme.ERR}
_LABEL = {"info": "INFO", "question": N_("CONFIRM"), "warning": N_("WARNING"), "error": N_("ERROR")}

# (testo, valore restituito, colore, colore al passaggio); "ghost" = solo bordo
_OK = [("OK", True, theme.BTN, theme.BTN_HOVER)]
_YESNO = [(N_("Yes"), True, theme.BTN, theme.BTN_HOVER), ("No", False, "ghost", theme.HOVER)]


def _show(kind: str, title: str, message: str, buttons, parent=None, default: str = ""):
    master = parent or tk._default_root
    win = ctk.CTkToplevel(master)
    win.title(title or "")
    win.configure(fg_color=theme.BG)
    win.resizable(False, False)
    theme.set_icon(win)
    # CustomTkinter reimposta icona e barra dopo ~200 ms: si ripassa dopo.
    win.after(250, lambda: theme.set_icon(win) if win.winfo_exists() else None)
    win.after(320, lambda: frameless.style_titlebar(
        win, caption=theme.BG, text=theme.TEXT_DIM, border=theme.BORDER) if win.winfo_exists() else None)

    result = {"value": None}

    def close(value) -> None:
        result["value"] = value
        try:
            win.grab_release()
        except tk.TclError:
            pass
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", lambda: close(None))

    outer = ctk.CTkFrame(win, fg_color=theme.PANEL, border_width=1,
                         border_color=theme.BORDER, corner_radius=4)
    outer.pack(fill="both", expand=True, padx=10, pady=10)
    accent = _ACCENT.get(kind, theme.ACCENT)
    ctk.CTkFrame(outer, height=2, corner_radius=0, border_width=0, fg_color=accent).pack(
        fill="x", padx=1, pady=(1, 0))

    head = ctk.CTkFrame(outer, fg_color="transparent", border_width=0)
    head.pack(fill="x", padx=16, pady=(12, 2))
    ctk.CTkLabel(head, text="●", font=(theme.mono_font(), 11), text_color=accent).pack(side="left")
    ctk.CTkLabel(head, text=tr(_LABEL.get(kind, "INFO")), font=(theme.mono_font(), 9, "bold"),
                 text_color=theme.TEXT_DIM).pack(side="left", padx=(6, 10))
    ctk.CTkLabel(head, text=title or "", font=(theme.ui_font(), 13, "bold"),
                 text_color=theme.TEXT, anchor="w").pack(side="left", fill="x")

    ctk.CTkLabel(outer, text=message, font=(theme.ui_font(), 12), text_color=theme.TEXT_SOFT,
                 justify="left", anchor="w", wraplength=460).pack(fill="x", padx=16, pady=(6, 16))

    row = ctk.CTkFrame(outer, fg_color="transparent", border_width=0)
    row.pack(fill="x", padx=16, pady=(0, 14))
    widgets = {}
    for text, value, color, hover in reversed(buttons):
        ghost = color == "ghost"
        widgets[value] = ctk.CTkButton(
            row, text=tr(text), width=96, height=30, corner_radius=4,
            font=(theme.ui_font(), 12, "bold"),
            fg_color="transparent" if ghost else color,
            hover_color=theme.HOVER if ghost else hover,
            border_width=1 if ghost else 0, border_color=theme.BORDER_STRONG,
            text_color=theme.TEXT if ghost else theme.BTN_TEXT,
            command=lambda v=value: close(v),
        )
        widgets[value].pack(side="right", padx=(6, 0))

    # Invio conferma la scelta predefinita: per le azioni distruttive e' «No».
    enter_value = False if default == "no" and False in widgets else buttons[0][1]
    win.bind("<Escape>", lambda _e: close(None))
    win.bind("<Return>", lambda _e: close(enter_value))

    win.update_idletasks()
    width, height = win.winfo_width(), win.winfo_height()
    try:
        if not master.winfo_viewable() or master.state() == "iconic":
            raise tk.TclError("finestra madre non visibile")
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 3
    except (tk.TclError, AttributeError):
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 3
    win.geometry(f"+{max(0, x)}+{max(0, y)}")

    try:
        win.transient(master)
        win.grab_set()
        win.lift()
        win.focus_force()
    except tk.TclError:
        pass
    widgets[enter_value].focus_set()
    win.wait_window()
    return result["value"]


class MessageBox:
    """Sostituto scuro di tkinter.messagebox (stessa firma)."""

    @staticmethod
    def showinfo(title="", message="", parent=None, **_kw):
        return _show("info", title, message, _OK, parent)

    @staticmethod
    def showwarning(title="", message="", parent=None, **_kw):
        return _show("warning", title, message,
                     [("OK", True, theme.WARN_BTN, theme.WARN_BTN_HOVER)], parent)

    @staticmethod
    def showerror(title="", message="", parent=None, **_kw):
        return _show("error", title, message,
                     [("OK", True, theme.DANGER, theme.DANGER_HOVER)], parent)

    @staticmethod
    def askyesno(title="", message="", parent=None, icon="question", default="yes", **_kw):
        kind = "warning" if icon == "warning" else "question"
        buttons = _YESNO
        if kind == "warning":
            buttons = [(N_("Yes"), True, theme.DANGER, theme.DANGER_HOVER), _YESNO[1]]
        return bool(_show(kind, title, message, buttons, parent, default=default))


messagebox = MessageBox()
