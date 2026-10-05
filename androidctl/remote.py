# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Comandi verso il telefono: canale diretto quando e' attivo, altrimenti ADB.

Chi chiama non deve sapere quale delle due strade e' disponibile: il canale
diretto (bridge) e' istantaneo e gestisce gli appunti per intero, ADB e' il
ripiego che funziona sempre ma e' lento e limitato ai caratteri ASCII.
"""

from __future__ import annotations

from .adb import Adb, is_ascii
from .bridge import Bridge, BridgeError

KEY_HOME = 3
KEY_BACK = 4
KEY_VOLUME_UP = 24
KEY_VOLUME_DOWN = 25
KEY_POWER = 26
KEY_APP_SWITCH = 187
KEY_WAKEUP = 224


class Remote:
    def __init__(self, adb: Adb, bridge: Bridge) -> None:
        self.adb = adb
        self.bridge = bridge

    def fast(self, serial: str) -> bool:
        """True se per questo dispositivo e' attivo il canale diretto."""
        return self.bridge.connected_to(serial)

    def key(self, serial: str, keycode: int) -> None:
        if self.fast(serial):
            try:
                self.bridge.key(keycode)
                return
            except BridgeError:
                pass
        self.adb.key(serial, keycode)

    def type_text(self, serial: str, text: str) -> None:
        """Digita il testo nel campo attivo, senza toccare gli appunti del telefono."""
        if self.fast(serial) and is_ascii(text):
            try:
                self.bridge.type_text(text)
                return
            except BridgeError:
                pass
        self.adb.type_text(serial, text)

    def paste(self, serial: str, text: str) -> bool:
        """Incolla il testo nel campo attivo del telefono.

        Restituisce True se e' passato dagli appunti del telefono (testo completo,
        Unicode compreso), False se e' stato digitato via ADB.
        """
        if self.fast(serial):
            try:
                if self.bridge.set_clipboard(text, paste=True):
                    return True
            except BridgeError:
                pass
        self.adb.type_text(serial, text)
        return False

    def copy(self, serial: str) -> str:
        """Copia la selezione sul telefono e restituisce gli appunti del telefono."""
        if self.fast(serial):
            try:
                return self.bridge.copy_from_device() or ""
            except BridgeError:
                pass
        return self.adb.device_copy(serial)
