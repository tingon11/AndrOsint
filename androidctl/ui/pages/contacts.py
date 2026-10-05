# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Pagina Rubrica: aiuto all'inserimento di un numero sul telefono."""

from __future__ import annotations

import customtkinter as ctk

from ...i18n import tr
from .. import theme
from ..widgets import Card, button, follow_width, note
from .base import Page


class ContactsPage(Page):
    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        form = Card(self, tr("Number to enter"), self.fonts)
        form.grid(row=0, column=0, sticky="ew")
        body = form.body
        body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(body, text=tr("Number"), font=self.fonts.body, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, theme.PAD)
        )
        self.phone_entry = ctk.CTkEntry(body, placeholder_text="+39 333 1234567", height=32)
        self.phone_entry.grid(row=0, column=1, sticky="ew", pady=3)
        button(body, tr("From PC clipboard"), self._from_clipboard, width=160).grid(
            row=0, column=2, padx=(theme.GAP, 0)
        )
        ctk.CTkLabel(body, text=tr("Name (optional)"), font=self.fonts.body, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(0, theme.PAD)
        )
        self.name_entry = ctk.CTkEntry(body, height=32)
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=3)

        actions = Card(self, tr("Actions on the phone"), self.fonts)
        actions.grid(row=1, column=0, sticky="ew", pady=(theme.GAP, 0))
        actions.body.grid_columnconfigure((0, 1), weight=1, uniform="action")
        entries = (
            (tr("New pre-filled contact"), self._new_contact, True),
            (tr("Open Contacts"), self._open_contacts, False),
            (tr("Open dialer with number"), self._dial, False),
            (tr("Type number on phone"), self._type_phone, False),
        )
        for index, (label, command, primary) in enumerate(entries):
            button(actions.body, label, command, primary=primary).grid(
                row=index // 2, column=index % 2, sticky="ew",
                padx=(0, 4) if index % 2 == 0 else (4, 0), pady=3,
            )

        hint = note(
            self,
            tr(
                "The number is pre-filled in Android's new-contact screen: saving must be "
                "confirmed on the phone. The contacts database is never modified directly. "
                "“Open dialer” does not start the call."
            ),
            self.fonts,
        )
        hint.grid(row=2, column=0, sticky="ew", pady=(theme.GAP, 0))
        follow_width(hint, self)

    # --------------------------------------------------------------- azioni

    def _from_clipboard(self) -> None:
        text = self.app.clip_get().strip()
        if not text:
            self.app.status(tr("The PC clipboard is empty or contains no text."))
            return
        self.phone_entry.delete(0, "end")
        self.phone_entry.insert(0, text.splitlines()[0].strip())

    def _phone(self) -> str:
        phone = self.phone_entry.get().strip()
        if not phone:
            self.app.status(tr("Enter a phone number."))
        return phone

    def _run(self, action, done: str, title: str, needs_phone: bool = True) -> None:
        """Esegue `action(serial, numero)` in background sul dispositivo selezionato."""
        app = self.app
        device = app.require_device()
        if device is None:
            return
        phone = self._phone() if needs_phone else ""
        if needs_phone and not phone:
            return
        serial = device.serial
        app.tasks.run(
            lambda: action(serial, phone),
            lambda _r: app.status(done),
            lambda exc: app.error(title, exc),
        )

    def _new_contact(self) -> None:
        name = self.name_entry.get().strip()
        self._run(
            lambda serial, phone: self.app.adb.new_contact(serial, phone, name),
            tr("New-contact screen opened on the phone."),
            tr("New contact"),
        )

    def _open_contacts(self) -> None:
        self._run(
            lambda serial, _phone: self.app.adb.open_contacts(serial),
            tr("Contacts app opened."),
            tr("Opening Contacts"),
            needs_phone=False,
        )

    def _dial(self) -> None:
        self._run(
            lambda serial, phone: self.app.adb.dial(serial, phone),
            tr("Dialer opened with the number."),
            tr("Opening dialer"),
        )

    def _type_phone(self) -> None:
        self._run(
            lambda serial, phone: self.app.remote.type_text(serial, phone),
            tr("Number typed on the phone."),
            tr("Typing number"),
        )
