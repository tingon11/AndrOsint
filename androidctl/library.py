# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Indice dei pacchetti presenti nella cartella del PC (nome, package, versione).

Lo usano sia la pagina Installa APK (per l'elenco) sia la pagina App (per dire
quali app sono gia' state salvate). La lettura di un file e' cara rispetto a
una scansione, quindi il risultato resta in memoria finche' il file non cambia.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import apkinfo, installer


@dataclass(frozen=True)
class Entry:
    path: Path
    size: int
    watched: bool  # True se sta nella cartella sorvegliata, False se aggiunto a mano
    info: apkinfo.ApkInfo


class PackageLibrary:
    def __init__(self, language: str = "") -> None:
        self._language = language
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[int, float, apkinfo.ApkInfo]] = {}

    def scan(self, folder: Path, extra: Iterable[Path] = ()) -> list[Entry]:
        """Pacchetti nella cartella piu' quelli aggiunti a mano (da un thread di lavoro)."""
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        found = [(path, True) for path in installer.find_packages(folder)]
        found += [(path, False) for path in extra]

        entries: list[Entry] = []
        for path, watched in found:
            try:
                stat = path.stat()
            except OSError:
                continue  # sparito nel frattempo
            key = str(path)
            with self._lock:
                cached = self._cache.get(key)
            if cached is None or cached[0] != stat.st_size or cached[1] != stat.st_mtime:
                info = apkinfo.read(path, self._language)
                with self._lock:
                    self._cache[key] = (stat.st_size, stat.st_mtime, info)
            else:
                info = cached[2]
            entries.append(Entry(path, stat.st_size, watched, info))

        present = {str(entry.path) for entry in entries}
        with self._lock:
            for key in [k for k in self._cache if k not in present]:
                del self._cache[key]
        return entries

    @staticmethod
    def by_package(entries: Iterable[Entry]) -> dict[str, list[Entry]]:
        """Raggruppa per package, nell'ordine in cui compaiono."""
        grouped: dict[str, list[Entry]] = {}
        for entry in entries:
            if entry.info.package:
                grouped.setdefault(entry.info.package, []).append(entry)
        return grouped
