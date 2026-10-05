# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Base comune delle pagine dell'applicazione."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from ...adb import Device

if TYPE_CHECKING:
    from ..app import App


class Page(ctk.CTkFrame):
    """Una pagina viene costruita la prima volta che la si apre, non all'avvio."""

    def __init__(self, app: "App") -> None:
        super().__init__(app.content, fg_color="transparent")
        self.app = app
        self.fonts = app.fonts
        self.build()

    def build(self) -> None:
        raise NotImplementedError

    def on_show(self) -> None:
        """La pagina e' appena diventata visibile."""

    def on_device(self, device: Device | None) -> None:
        """Il dispositivo selezionato e' cambiato (None: nessuno pronto)."""

    def retranslate(self) -> None:
        """La lingua e' cambiata: i widget si ritraducono da soli, qui vanno
        aggiornati i testi che la pagina compone (righe delle tabelle)."""

    def on_close(self) -> None:
        """L'applicazione sta per chiudersi."""
