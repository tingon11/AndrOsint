# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Componenti riusati dalle pagine: riquadri, pulsanti e tabelle."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from ..i18n import Text, again
from . import theme


class Card(ctk.CTkFrame):
    """Riquadro bordato con titolo in maiuscolo; il contenuto va dentro `body`."""

    def __init__(self, parent, title: str, fonts: theme.Fonts) -> None:
        super().__init__(parent, fg_color=theme.PANEL, border_width=1,
                         border_color=theme.BORDER, corner_radius=4)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        head.grid(row=0, column=0, sticky="ew", padx=theme.PAD, pady=(theme.PAD - 2, 0))
        # barretta d'accento accanto al titolo, come nei pannelli di TagFaces
        ctk.CTkFrame(head, fg_color=theme.ACCENT, width=2, height=11, corner_radius=0).pack(
            side="left", padx=(0, 7))
        self._title = title
        self._title_label = ctk.CTkLabel(head, text=title.upper(), font=fonts.title,
                                         text_color=theme.TEXT_DIM, anchor="w", height=14)
        self._title_label.pack(side="left", fill="x")

        self.body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew", padx=theme.PAD, pady=(theme.GAP, theme.PAD))

    def retranslate(self) -> None:
        self._title = again(self._title)
        self._title_label.configure(text=self._title.upper())


def button(
    parent, text: str, command, primary: bool = False, width: int = 0, danger: bool = False, **kwargs
) -> ctk.CTkButton:
    """Pulsante principale (accento), secondario (neutro) o distruttivo (bordo rosso)."""
    if danger:
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("hover_color", theme.HOVER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.ERR)
        kwargs.setdefault("text_color", theme.ERR)
    elif not primary:
        kwargs.setdefault("fg_color", theme.NEUTRAL)
        kwargs.setdefault("hover_color", theme.NEUTRAL_HOVER)
        kwargs.setdefault("text_color", theme.TEXT)
    kwargs.setdefault("font", (theme.ui_font(), 12, "bold"))
    kwargs.setdefault("height", 30)
    if width:
        kwargs["width"] = width
    return ctk.CTkButton(parent, text=text, command=command, **kwargs)


def link(parent, text: str, command) -> ctk.CTkButton:
    """Pulsante dall'aspetto di collegamento, per aprire un sito."""
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        height=26,
        width=0,
        fg_color="transparent",
        hover_color=theme.HOVER,
        text_color=theme.ACCENT,
        font=(theme.ui_font(), 12, "bold"),
    )


def note(parent, text: str, fonts: theme.Fonts, wraplength: int = 0) -> ctk.CTkLabel:
    """Testo esplicativo attenuato."""
    return ctk.CTkLabel(
        parent,
        text=text,
        font=fonts.small,
        text_color=theme.TEXT_DIM,
        anchor="w",
        justify="left",
        wraplength=wraplength,
    )


def follow_width(label: ctk.CTkLabel, container, margin: int = 0) -> None:
    """Fa andare a capo il testo secondo la larghezza del contenitore."""

    def resize(event) -> None:
        # <Configure> riporta pixel reali, wraplength vuole unita' non scalate.
        label.configure(wraplength=max(120, int(event.width / theme.scaling(label)) - margin))

    container.bind("<Configure>", resize, add="+")


class Table(ctk.CTkFrame):
    """Tabella ttk con barra di scorrimento e colori del tema.

    `columns` e' una lista di (chiave, titolo, larghezza, si_allarga): le colonne
    che si allargano si dividono lo spazio disponibile in proporzione alla
    larghezza indicata, cosi' la tabella riempie sempre la finestra senza
    barra orizzontale. `tags` associa un nome di riga a un colore del testo.
    """

    def __init__(
        self,
        parent,
        columns: list[tuple[str, str, int, bool]],
        selectmode: str = "browse",
        tags: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent, fg_color=theme.PANEL, border_width=1,
                         border_color=theme.BORDER, corner_radius=4)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        scale = theme.scaling(self)
        self._columns = [(key, int(width * scale), stretch) for key, _t, width, stretch in columns]
        self._min_width = int(40 * scale)
        self._fitted_width = 0

        self.tree = ttk.Treeview(
            self, columns=[c[0] for c in columns], show="headings", selectmode=selectmode
        )
        self._titles = {key: title for key, title, _width, _stretch in columns}
        for key, title in self._titles.items():
            self.tree.heading(key, text=title.upper(), anchor="w")
        for key, width, _stretch in self._columns:
            # La ripartizione la fa _fit: quella di ttk non restringe sotto la larghezza iniziale.
            self.tree.column(key, width=width, minwidth=self._min_width, anchor="w", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        self.tree.bind("<Configure>", self._fit, add="+")

        bar = ctk.CTkScrollbar(self, command=self.tree.yview)
        bar.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
        self.tree.configure(yscrollcommand=bar.set)

        for name, color in (tags or {}).items():
            self.tree.tag_configure(name, foreground=color)

    def _fit(self, event) -> None:
        """Ripartisce la larghezza disponibile tra le colonne che si allargano."""
        if event.width == self._fitted_width or event.width < 50:
            return
        self._fitted_width = event.width
        fixed = sum(width for _key, width, stretch in self._columns if not stretch)
        flexible = sum(width for _key, width, stretch in self._columns if stretch)
        if flexible <= 0:
            return
        factor = max(0.0, event.width - fixed) / flexible
        for key, width, stretch in self._columns:
            if stretch:
                self.tree.column(key, width=max(self._min_width, int(width * factor)))

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def retranslate(self) -> None:
        for key, title in self._titles.items():
            title = self._titles[key] = again(title)
            self.tree.heading(key, text=title.upper())


def retranslate_all(widget) -> None:
    """Porta nella lingua in uso i testi di `widget` e di tutto cio' che contiene.

    Un widget conserva il testo ricevuto: se viene da tr() ha con se' la propria
    chiave e basta ritradurlo. Chi il testo lo compone (titoli in maiuscolo,
    intestazioni e righe delle tabelle) espone un metodo retranslate().
    """
    for option in ("text", "placeholder_text"):
        try:
            value = widget.cget(option)
        except (ValueError, AttributeError, KeyError, tk.TclError):
            continue  # il widget non ha questa opzione
        if isinstance(value, Text):
            widget.configure(**{option: again(value)})
    own = getattr(widget, "retranslate", None)
    if callable(own):
        own()
    for child in widget.winfo_children():
        retranslate_all(child)
