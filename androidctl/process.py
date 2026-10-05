# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Utility per lanciare processi esterni senza far comparire finestre console."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _no_window_kwargs() -> dict:
    """Su Windows evita che ogni chiamata ad adb apra una finestra nera."""
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


# Calcolato una volta sola: Popen copia lo STARTUPINFO a ogni avvio.
_NO_WINDOW = _no_window_kwargs()


def run(argv: list[str], timeout: float = 20.0, env: dict | None = None) -> subprocess.CompletedProcess:
    """Esegue un comando raccogliendo stdout/stderr come testo."""
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        stdin=subprocess.DEVNULL,
        **_NO_WINDOW,
    )


def run_binary(argv: list[str], timeout: float = 60.0, env: dict | None = None) -> subprocess.CompletedProcess:
    """Come run(), ma restituisce stdout in byte grezzi (per gli screenshot PNG)."""
    return subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout,
        env=env,
        stdin=subprocess.DEVNULL,
        **_NO_WINDOW,
    )


def popen(argv: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.Popen:
    """Avvia un processo a lunga durata (scrcpy, scrcpy-server) senza console.

    stdout e stderr confluiscono in un'unica pipe che il chiamante deve leggere:
    una pipe mai svuotata, una volta piena, blocca il processo figlio.
    """
    return subprocess.Popen(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **_NO_WINDOW,
    )


def spawn_detached(argv: list[str], env: dict | None = None) -> None:
    """Lancia un comando senza attenderlo: prosegue anche se l'applicazione si chiude."""
    try:
        subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_NO_WINDOW,
        )
    except OSError:
        pass
