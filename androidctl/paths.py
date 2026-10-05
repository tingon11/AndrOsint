# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Risoluzione dei percorsi dell'applicazione e degli strumenti in tools/."""

from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """Cartella base dell'applicazione (funziona anche se impacchettata con PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = app_dir()
TOOLS_DIR = APP_DIR / "tools"
CONFIG_FILE = APP_DIR / "config.json"
DEFAULT_SCREENSHOT_DIR = APP_DIR / "screenshots"
DEFAULT_PACKAGES_DIR = APP_DIR / "apk"

PLATFORM_TOOLS_DIR = TOOLS_DIR / "platform-tools"
SCRCPY_DIR = TOOLS_DIR / "scrcpy"

ADB_EXE = PLATFORM_TOOLS_DIR / "adb.exe"
SCRCPY_EXE = SCRCPY_DIR / "scrcpy.exe"


def _find_below(root: Path, name: str, max_depth: int = 3) -> Path | None:
    """Cerca un eseguibile sotto `root`, per tollerare strutture di zip diverse."""
    if not root.is_dir():
        return None
    for depth in range(max_depth + 1):
        pattern = "/".join(["*"] * depth + [name]) if depth else name
        for candidate in sorted(root.glob(pattern)):
            if candidate.is_file():
                return candidate
    return None


def adb_path() -> Path | None:
    """Percorso di adb.exe dentro tools/, oppure None se assente."""
    if ADB_EXE.is_file():
        return ADB_EXE
    return _find_below(TOOLS_DIR, "adb.exe")


def scrcpy_path() -> Path | None:
    """Percorso di scrcpy.exe dentro tools/, oppure None se assente."""
    if SCRCPY_EXE.is_file():
        return SCRCPY_EXE
    return _find_below(TOOLS_DIR, "scrcpy.exe")


def scrcpy_server_path() -> Path | None:
    """Percorso di scrcpy-server (distribuito accanto a scrcpy.exe), oppure None."""
    exe = scrcpy_path()
    if exe is None:
        return None
    server = exe.parent / "scrcpy-server"
    return server if server.is_file() else None


def ensure_dirs() -> None:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
