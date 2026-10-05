# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Avvio e arresto del mirroring dello schermo tramite scrcpy."""

from __future__ import annotations

import collections
import re
import subprocess
import threading
from pathlib import Path

from . import paths
from .adb import Adb
from .i18n import tr
from .process import popen, run


class ScrcpyError(RuntimeError):
    """scrcpy non disponibile o non avviabile."""


class Scrcpy:
    """Gestisce un singolo processo scrcpy (una finestra di mirroring alla volta)."""

    def __init__(self, adb: Adb) -> None:
        self._adb = adb
        self._proc: subprocess.Popen | None = None
        self._output: collections.deque[str] = collections.deque(maxlen=30)
        # La versione si legge lanciando scrcpy: la si ricorda per eseguibile.
        self._version: tuple[Path, float, str] | None = None

    # ---------------------------------------------------------------- stato

    @property
    def available(self) -> bool:
        return paths.scrcpy_path() is not None

    @property
    def exe(self) -> Path:
        exe = paths.scrcpy_path()
        if exe is None:
            raise ScrcpyError(
                tr("scrcpy.exe not found in tools/. Use the Tools page to download it.")
            )
        return exe

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def version_string(self) -> str:
        try:
            exe = self.exe
            stamp = exe.stat().st_mtime
        except (OSError, ScrcpyError):
            return ""
        cached = self._version
        if cached and cached[0] == exe and cached[1] == stamp:
            return cached[2]
        try:
            out = run([str(exe), "--version"], timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
        match = re.search(r"scrcpy\s+([0-9][0-9.]*)", out)
        version = match.group(1) if match else ""
        if version:
            self._version = (exe, stamp, version)
        return version

    def _major(self) -> int:
        found = re.findall(r"\d+", self.version_string())
        return int(found[0]) if found else 0

    # -------------------------------------------------------------- comandi

    def build_args(self, serial: str, options: dict) -> list[str]:
        """Costruisce la riga di comando, orientata al basso consumo di CPU/GPU."""
        major = self._major()
        argv = [str(self.exe), "-s", serial]

        max_size = int(options.get("mirror_max_size") or 0)
        if max_size > 0:
            argv += ["--max-size", str(max_size)]

        bitrate = str(options.get("mirror_bitrate") or "").strip()
        if bitrate:
            argv += ["--video-bit-rate" if major >= 2 else "--bit-rate", bitrate]

        max_fps = int(options.get("mirror_max_fps") or 0)
        if max_fps > 0:
            argv += ["--max-fps", str(max_fps)]

        if major >= 2:
            # L'audio raddoppia il carico e non serve per il controllo remoto.
            argv.append("--no-audio")

        if options.get("mirror_stay_awake"):
            argv.append("--stay-awake")
        if options.get("mirror_turn_screen_off"):
            argv.append("--turn-screen-off")
        if options.get("mirror_always_on_top"):
            argv.append("--always-on-top")

        argv += ["--window-title", f"Android - {serial}"]
        return argv

    def start(self, serial: str, options: dict) -> None:
        """Apre la finestra di mirroring per il dispositivo indicato."""
        if self.is_running():
            return
        argv = self.build_args(serial, options)
        # scrcpy deve usare lo stesso adb dell'applicazione, per non avviare
        # un secondo adb server di versione diversa.
        env = self._adb.child_env()
        try:
            proc = popen(argv, cwd=self.exe.parent, env=env)
        except OSError as exc:
            raise ScrcpyError(tr("Cannot start scrcpy: {error}").format(error=exc)) from exc
        self._output.clear()
        self._proc = proc
        threading.Thread(target=self._drain_output, args=(proc,), daemon=True).start()

    def _drain_output(self, proc: subprocess.Popen) -> None:
        """Svuota l'output di scrcpy: una pipe piena ne bloccherebbe la finestra."""
        stream = proc.stdout
        if stream is None:
            return
        try:
            for raw in stream:
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._output.append(line)
        except (OSError, ValueError):
            pass

    def stop(self) -> None:
        """Chiude la finestra di mirroring, senza attendere che il processo termini."""
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
        except OSError:
            pass

    def last_error(self) -> str:
        """Messaggio di errore se scrcpy e' terminato da solo con un problema."""
        proc = self._proc
        if proc is None or proc.poll() is None or proc.returncode == 0:
            return ""
        errors = [line for line in self._output if "ERROR" in line]
        return "\n".join(errors or list(self._output)[-5:])
