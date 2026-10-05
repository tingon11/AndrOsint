# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Canale di controllo diretto verso il telefono, basato su scrcpy-server.

`adb shell input keyevent` avvia una JVM a ogni pressione: sul telefono costa
oltre mezzo secondo. scrcpy-server resta invece in esecuzione e riceve i comandi
su un socket: i tasti arrivano in pochi millisecondi e gli appunti si leggono e
si scrivono per intero, Unicode compreso, cosa che ADB da solo non permette
(da Android 10 la shell non ha accesso agli appunti).

Il protocollo e' quello di controllo di scrcpy, lo stesso usato dal mirroring,
limitato qui a tasti, testo e appunti. Il server viene avviato senza video e
senza audio, quindi non consuma CPU ne' batteria quando non riceve comandi.

Lo stesso server sa anche elencare le app con il nome che l'utente vede sul
telefono (`list_apps`): ADB da solo non lo espone.
"""

from __future__ import annotations

import collections
import itertools
import random
import re
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from .adb import Adb, AdbError
from .i18n import tr

# Percorso diverso da quello del mirroring: scrcpy cancella il proprio server
# all'avvio, e i due non devono pestarsi i piedi.
REMOTE_JAR = "/data/local/tmp/apc-scrcpy-server.jar"

# Messaggi PC -> telefono
_INJECT_KEYCODE = 0
_INJECT_TEXT = 1
_EXPAND_NOTIFICATIONS = 5
_COLLAPSE_PANELS = 7
_GET_CLIPBOARD = 8
_SET_CLIPBOARD = 9

# Messaggi telefono -> PC
_DEV_CLIPBOARD = 0
_DEV_ACK_CLIPBOARD = 1
_DEV_UHID_OUTPUT = 2

_COPY_KEY_NONE = 0
_COPY_KEY_COPY = 1

_SERVER_CLASS = "com.genymobile.scrcpy.Server"

_TEXT_MAX = 300                      # limite del server per INJECT_TEXT
_CLIPBOARD_MAX = (1 << 18) - 14      # limite del server per SET_CLIPBOARD
_POLL_SETTLE = 0.3                   # attesa perche' una lettura periodica si esaurisca


class BridgeError(RuntimeError):
    """Il canale di controllo non e' disponibile o si e' interrotto."""


class Bridge:
    """Una connessione di controllo verso un dispositivo alla volta."""

    def __init__(
        self,
        adb: Adb,
        on_clipboard: Callable[[str], None] | None = None,
        on_closed: Callable[[str], None] | None = None,
    ) -> None:
        self._adb = adb
        # Entrambe le callback sono invocate dal thread di lettura, non dalla GUI.
        self._on_clipboard = on_clipboard
        self._on_closed = on_closed

        self._send_lock = threading.Lock()
        self._state = threading.Condition()
        self._sock: socket.socket | None = None
        self._proc: subprocess.Popen | None = None
        self._port = 0
        self._serial = ""
        self._output: collections.deque[str] = collections.deque(maxlen=20)

        self._sequence = itertools.count(1)
        self._acked: set[int] = set()
        self._clip_count = 0
        self._clip_text = ""
        self._last_poll = 0.0

    # ---------------------------------------------------------------- stato

    @property
    def serial(self) -> str:
        return self._serial

    def connected_to(self, serial: str) -> bool:
        return self._sock is not None and self._serial == serial

    # ----------------------------------------------------------- connessione

    def start(self, serial: str, server_jar: Path, version: str, timeout: float = 10.0) -> None:
        """Avvia il server sul telefono e apre il canale (bloccante: va in un thread)."""
        self.stop()
        if not version:
            raise BridgeError(tr("Cannot determine the scrcpy version."))

        scid = random.getrandbits(31)
        try:
            self._adb.push(serial, server_jar, REMOTE_JAR, timeout=60)
            port = self._adb.forward(serial, f"localabstract:scrcpy_{scid:08x}")
            proc = self._adb.spawn(
                [
                    "shell",
                    f"CLASSPATH={REMOTE_JAR}",
                    "app_process",
                    "/",
                    _SERVER_CLASS,
                    version,
                    f"scid={scid:08x}",
                    "log_level=info",
                    "video=false",
                    "audio=false",
                    "control=true",
                    "tunnel_forward=true",
                    "cleanup=false",
                    "power_on=false",
                    # La lettura degli appunti viene chiesta esplicitamente: con la
                    # sincronizzazione del server attiva, GET_CLIPBOARD non risponde.
                    "clipboard_autosync=false",
                    "send_device_meta=false",
                ],
                serial=serial,
            )
        except (AdbError, OSError) as exc:
            raise BridgeError(
                tr("Could not start the control channel: {error}").format(error=exc)
            ) from exc

        self._output.clear()
        threading.Thread(target=self._drain_output, args=(proc,), daemon=True).start()

        try:
            sock = self._connect(proc, port, timeout)
        except BridgeError:
            _terminate(proc)
            self._adb.forward_remove(serial, port)
            raise

        with self._state:
            self._sock = sock
            self._proc = proc
            self._port = port
            self._serial = serial
            self._acked.clear()
        threading.Thread(target=self._reader, args=(sock,), daemon=True).start()

    def _connect(self, proc: subprocess.Popen, port: int, timeout: float) -> socket.socket:
        """Attende che il server accetti la connessione.

        Con `adb forward` la connect() riesce anche se sul telefono nessuno e'
        ancora in ascolto: il server conferma di esserci inviando un byte.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                time.sleep(0.2)  # lascia arrivare le ultime righe di output
                detail = " ".join(self._output) or tr("exit code {code}").format(
                    code=proc.returncode
                )
                raise BridgeError(
                    tr("scrcpy-server exited immediately: {detail}").format(detail=detail)
                )
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=2)
            except OSError:
                time.sleep(0.1)
                continue
            try:
                sock.settimeout(2)
                if sock.recv(1) == b"\x00":
                    sock.settimeout(None)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    return sock
            except OSError:
                pass
            sock.close()
            time.sleep(0.1)
        raise BridgeError(tr("scrcpy-server did not respond in time."))

    def stop(self, keep_forward: bool = False) -> None:
        """Chiude il canale e ferma il server sul telefono.

        `keep_forward` evita di lanciare un altro comando adb: serve alla
        chiusura, quando il server ADB viene arrestato e non va risvegliato.
        """
        with self._state:
            sock, proc = self._sock, self._proc
            port, serial = self._port, self._serial
            self._sock = None
            self._proc = None
            self._port = 0
            self._serial = ""
            self._state.notify_all()
        if sock is not None:
            _close(sock)
        if proc is not None:
            _terminate(proc)
        if port and serial and not keep_forward:
            self._adb.forward_remove(serial, port)

    def _drain_output(self, proc: subprocess.Popen) -> None:
        """Svuota l'output del server: una pipe piena lo bloccherebbe."""
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

    # --------------------------------------------------------------- lettura

    def _reader(self, sock: socket.socket) -> None:
        try:
            while True:
                kind = _recv_exact(sock, 1)[0]
                if kind == _DEV_CLIPBOARD:
                    (size,) = struct.unpack(">I", _recv_exact(sock, 4))
                    text = _recv_exact(sock, size).decode("utf-8", errors="replace")
                    with self._state:
                        self._clip_text = text
                        self._clip_count += 1
                        self._state.notify_all()
                    if self._on_clipboard:
                        self._on_clipboard(text)
                elif kind == _DEV_ACK_CLIPBOARD:
                    (sequence,) = struct.unpack(">Q", _recv_exact(sock, 8))
                    with self._state:
                        self._acked.add(sequence)
                        self._state.notify_all()
                elif kind == _DEV_UHID_OUTPUT:
                    _id, size = struct.unpack(">HH", _recv_exact(sock, 4))
                    _recv_exact(sock, size)
                else:
                    raise BridgeError(f"messaggio sconosciuto dal telefono: {kind}")
        except (OSError, BridgeError, struct.error):
            pass
        finally:
            self._lost(sock)

    def _lost(self, sock: socket.socket) -> None:
        """Il socket si e' chiuso: telefono scollegato oppure stop() esplicito."""
        with self._state:
            if self._sock is not sock:
                return  # chiusura richiesta da stop(): gia' gestita
            serial = self._serial
        self.stop()
        if self._on_closed:
            self._on_closed(serial)

    # ---------------------------------------------------------------- invio

    def _send(self, payload: bytes) -> None:
        sock = self._sock
        if sock is None:
            raise BridgeError("Canale di controllo non attivo.")
        try:
            with self._send_lock:
                sock.sendall(payload)
        except OSError as exc:
            raise BridgeError(f"Canale di controllo interrotto: {exc}") from exc

    def key(self, keycode: int, metastate: int = 0) -> None:
        """Preme e rilascia un tasto Android."""
        press = struct.pack(">BBiii", _INJECT_KEYCODE, 0, keycode, 0, metastate)
        release = struct.pack(">BBiii", _INJECT_KEYCODE, 1, keycode, 0, metastate)
        self._send(press + release)

    def type_text(self, text: str) -> None:
        """Digita il testo come dalla tastiera (affidabile solo per caratteri comuni)."""
        for piece in _utf8_pieces(text, _TEXT_MAX):
            self._send(struct.pack(">BI", _INJECT_TEXT, len(piece)) + piece)

    def expand_notifications(self) -> None:
        self._send(bytes([_EXPAND_NOTIFICATIONS]))

    def collapse_panels(self) -> None:
        self._send(bytes([_COLLAPSE_PANELS]))

    # -------------------------------------------------------------- appunti

    def set_clipboard(self, text: str, paste: bool = False, timeout: float = 3.0) -> bool:
        """Scrive gli appunti del telefono; con `paste` li incolla subito nel campo attivo.

        Restituisce True quando il telefono conferma di aver ricevuto il testo.
        """
        raw = next(iter(_utf8_pieces(text, _CLIPBOARD_MAX)), b"")
        sequence = next(self._sequence)
        self._send(
            struct.pack(">BQBI", _SET_CLIPBOARD, sequence, 1 if paste else 0, len(raw)) + raw
        )
        deadline = time.monotonic() + timeout
        with self._state:
            while sequence not in self._acked:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self._sock is None:
                    return False
                self._state.wait(remaining)
            self._acked.discard(sequence)
        return True

    def poll_clipboard(self) -> None:
        """Chiede gli appunti del telefono senza attendere: la risposta arriva a on_clipboard.

        Se gli appunti del telefono sono vuoti il server non risponde affatto.
        """
        self._last_poll = time.monotonic()
        self._send(bytes([_GET_CLIPBOARD, _COPY_KEY_NONE]))

    def copy_from_device(self, timeout: float = 3.0) -> str | None:
        """Preme Copia sul telefono e ne restituisce gli appunti (None se vuoti)."""
        # Una lettura periodica ancora in volo verrebbe scambiata per la risposta:
        # le si lascia il tempo di arrivare prima di contare.
        settle = _POLL_SETTLE - (time.monotonic() - self._last_poll)
        if settle > 0:
            time.sleep(settle)
        with self._state:
            before = self._clip_count
        self._send(bytes([_GET_CLIPBOARD, _COPY_KEY_COPY]))
        deadline = time.monotonic() + timeout
        with self._state:
            while self._clip_count == before:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self._sock is None:
                    return None
                self._state.wait(remaining)
            return self._clip_text


# ------------------------------------------------------------ nomi delle app

# " * Nome<spazi>package" (sistema) oppure " - Nome<spazi>package" (utente);
# un nome lungo manda il package a capo, rientrato.
_APP_LINE = re.compile(r"^ [*-] (.+?) {2,}(\S+)$")
_APP_WRAPPED = re.compile(r"^\s{3,}(\S+)$")


def app_labels(
    adb: Adb, server_jar: Path, version: str, serial: str, timeout: float = 90.0
) -> dict[str, str]:
    """Nome visibile di ogni app avviabile, come lo mostra il telefono (package -> nome).

    Esegue scrcpy-server in modalita' elenco: stampa la lista ed esce, senza
    aprire alcun canale. Richiede qualche secondo, quindi va chiamata in background.
    """
    if not version:
        raise BridgeError(tr("Cannot determine the scrcpy version."))
    try:
        adb.push(serial, server_jar, REMOTE_JAR, timeout=60)
        out = adb.shell(
            f"CLASSPATH={REMOTE_JAR} app_process / {_SERVER_CLASS} {version} list_apps=true",
            serial=serial,
            timeout=timeout,
        )
    except AdbError as exc:
        raise BridgeError(tr("app list failed: {error}").format(error=exc)) from exc

    labels: dict[str, str] = {}
    wrapped = ""
    for line in out.splitlines():
        line = line.rstrip()
        match = _APP_LINE.match(line)
        if match:
            labels[match.group(2)] = match.group(1).strip()
            wrapped = ""
        elif line.startswith((" * ", " - ")):
            wrapped = line[3:].strip()
        elif wrapped:
            match = _APP_WRAPPED.match(line)
            if match:
                labels[match.group(1)] = wrapped
            wrapped = ""
    if not labels and "List of apps" not in out:
        detail = next((l for l in out.splitlines() if "ERROR" in l or "Exception" in l), "")
        raise BridgeError(
            tr("scrcpy-server did not return the list. {detail}").format(detail=detail).strip()
        )
    return labels


# ----------------------------------------------------------------- helper


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise BridgeError("canale chiuso")
        data += chunk
    return data


def _utf8_pieces(text: str, limit: int):
    """Spezza il testo in blocchi UTF-8 di al piu' `limit` byte, senza tagliare un carattere."""
    raw = text.encode("utf-8")
    start = 0
    while start < len(raw):
        end = min(start + limit, len(raw))
        # I byte di continuazione (10xxxxxx) non possono aprire un blocco.
        while end < len(raw) and end > start and (raw[end] & 0xC0) == 0x80:
            end -= 1
        yield raw[start:end]
        start = end


def _close(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
