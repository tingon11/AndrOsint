# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Impostazioni persistenti dell'applicazione (semplice file JSON, nessun database)."""

from __future__ import annotations

import json
import os
from typing import Any

from .paths import CONFIG_FILE, DEFAULT_PACKAGES_DIR, DEFAULT_SCREENSHOT_DIR

DEFAULTS: dict[str, Any] = {
    "screenshot_dir": str(DEFAULT_SCREENSHOT_DIR),
    "shot_to_clipboard": True,
    "last_serial": "",
    # Interfaccia
    "language": "en",  # "en" oppure "it": vedi i18n.LANGUAGES
    "geometry": "",
    # Mirroring: valori pensati per un basso consumo di CPU/GPU.
    "mirror_max_size": 1024,
    "mirror_bitrate": "4M",
    "mirror_max_fps": 30,
    "mirror_stay_awake": True,
    "mirror_turn_screen_off": False,
    "mirror_always_on_top": False,
    # Canale di controllo diretto (tasti e appunti istantanei)
    "fast_control": True,
    "clip_autosync": False,
    "kill_adb_on_exit": False,
    "show_system_apps": False,
    # Installazione pacchetti
    "packages_dir": str(DEFAULT_PACKAGES_DIR),
    "install_replace": True,
    "install_downgrade": False,
    "install_grant": False,
    "install_auto": False,
}


class Config:
    """Dizionario di impostazioni salvato accanto all'applicazione."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._dirty = False
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(raw, dict):
            for key in DEFAULTS:
                if key in raw:
                    self._data[key] = raw[key]

    def save(self) -> None:
        """Scrive il file solo se qualcosa e' cambiato, senza mai lasciarlo a meta'."""
        if not self._dirty:
            return
        temp = CONFIG_FILE.with_name(CONFIG_FILE.name + ".tmp")
        try:
            temp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, CONFIG_FILE)
        except OSError:
            return
        self._dirty = False

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        if self._data.get(key) != value:
            self._data[key] = value
            self._dirty = True
