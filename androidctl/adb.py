# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Wrapper attorno all'eseguibile ADB contenuto in tools/platform-tools."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import paths
from .i18n import tr
from .process import popen, run, run_binary, spawn_detached

# Caratteri che la shell di Android interpreta e che vanno protetti in `input text`.
_INPUT_SPECIALS = '()<>|;&*~"\'`$#!'

DEFAULT_SERVER_PORT = 5037


class AdbError(RuntimeError):
    """Errore riportato da adb o dall'assenza dell'eseguibile."""


@dataclass
class Device:
    serial: str
    state: str  # device | unauthorized | offline | ...
    model: str = ""
    manufacturer: str = ""
    android: str = ""
    sdk: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "device"

    @property
    def label(self) -> str:
        name = (self.model or "").strip()
        return f"{name} ({self.serial})" if name else self.serial

    @property
    def state_text(self) -> str:
        return {
            "device": tr("Connected"),
            "unauthorized": tr("Unauthorized"),
            "offline": "Offline",
            "recovery": "Recovery",
            "unknown": tr("Unknown"),
        }.get(self.state, self.state)


@dataclass
class AppInfo:
    package: str
    name: str
    launchable: bool = False
    component: str = ""
    system: bool = False
    labelled: bool = False  # True se `name` e' il nome mostrato dal telefono
    version: str = ""

    @property
    def label(self) -> str:
        """Nome vero se noto; altrimenti il package, che almeno non inganna."""
        return self.name if self.labelled else self.package

    def apply_labels(self, labels: dict[str, str]) -> None:
        label = labels.get(self.package, "").strip()
        if label:
            self.name = label
            self.labelled = True


class Adb:
    """Interfaccia minimale ad ADB: solo comandi pubblici e non invasivi."""

    def __init__(self) -> None:
        self._exe: Path | None = paths.adb_path()
        self._env: dict | None = None
        # Messo a True mentre si aggiornano gli strumenti: il server non va riavviato.
        self.paused = False

    # ---------------------------------------------------------------- setup

    def refresh_path(self) -> None:
        self._exe = paths.adb_path()
        self._env = None

    @property
    def available(self) -> bool:
        if self._exe is None or not self._exe.is_file():
            self.refresh_path()
        return self._exe is not None

    @property
    def exe(self) -> Path:
        if not self.available:
            raise AdbError(
                tr("adb.exe not found in tools/. Use the Tools page to download it.")
            )
        return self._exe

    def child_env(self) -> dict:
        """Ambiente per i processi figli: forza l'uso del nostro adb (anche per scrcpy)."""
        exe = str(self.exe)
        if self._env is None or self._env.get("ADB") != exe:
            env = os.environ.copy()
            env["ADB"] = exe
            self._env = env
        return self._env

    def version(self) -> str:
        try:
            out = run([str(self.exe), "version"], timeout=10).stdout
        except (OSError, subprocess.SubprocessError, AdbError):
            return ""
        match = re.search(r"version\s+([0-9.]+)", out)
        if match:
            return match.group(1)
        lines = out.strip().splitlines()
        return lines[0] if lines else ""

    # ------------------------------------------------------------- comandi

    def base(self, serial: str | None) -> list[str]:
        argv = [str(self.exe)]
        if serial:
            argv += ["-s", serial]
        return argv

    def call(self, args: list[str], serial: str | None = None, timeout: float = 20.0) -> str:
        """Esegue un comando adb e restituisce stdout; solleva AdbError in caso di errore."""
        try:
            proc = run(self.base(serial) + args, timeout=timeout, env=self.child_env())
        except subprocess.TimeoutExpired as exc:
            raise AdbError(
                tr("adb did not respond within {seconds} seconds.").format(seconds=int(timeout))
            ) from exc
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "").strip()
            raise AdbError(message or tr("adb returned exit code {code}").format(code=proc.returncode))
        return proc.stdout

    def shell(self, command: str, serial: str | None = None, timeout: float = 20.0) -> str:
        return self.call(["shell", command], serial=serial, timeout=timeout)

    def try_shell(self, command: str, serial: str | None = None, timeout: float = 20.0) -> str:
        """Come shell(), ma restituisce stringa vuota invece di sollevare eccezioni."""
        try:
            return self.shell(command, serial=serial, timeout=timeout)
        except (AdbError, OSError, subprocess.SubprocessError):
            return ""

    def spawn(self, args: list[str], serial: str | None = None) -> subprocess.Popen:
        """Avvia un comando adb a lunga durata (l'output va letto dal chiamante)."""
        return popen(self.base(serial) + args, env=self.child_env())

    def start_server(self) -> None:
        try:
            run([str(self.exe), "start-server"], timeout=25, env=self.child_env())
        except (OSError, subprocess.SubprocessError, AdbError):
            pass

    def kill_server(self) -> None:
        try:
            run([str(self.exe), "kill-server"], timeout=15, env=self.child_env())
        except (OSError, subprocess.SubprocessError, AdbError):
            pass

    def kill_server_detached(self) -> None:
        """Arresta il server senza attendere: usata alla chiusura dell'applicazione."""
        if self.available:
            spawn_detached([str(self.exe), "kill-server"], env=self.child_env())

    # ----------------------------------------------------------- dispositivi

    def devices(self) -> list[Device]:
        """Elenco dei dispositivi collegati, con relativo stato di connessione."""
        out = self.call(["devices", "-l"], timeout=15)
        return parse_devices("\n".join(out.splitlines()[1:]))

    def track_devices(
        self, on_change: Callable[[list[Device]], None], stop: threading.Event
    ) -> None:
        """Segue collegamenti e scollegamenti in tempo reale (bloccante: va in un thread).

        Resta in ascolto sul server ADB, che notifica ogni variazione appena
        avviene: nessun `adb devices` ripetuto, nessun ritardo di polling.
        """

        def interrupted() -> bool:
            return stop.is_set() or self.paused

        while not stop.is_set():
            if self.paused or not self.available:
                on_change([])
                stop.wait(1.0)
                continue
            self.start_server()
            try:
                with socket.create_connection(("127.0.0.1", server_port()), timeout=5) as sock:
                    sock.settimeout(1.0)
                    _request(sock, "host:track-devices-l", interrupted)
                    while True:
                        size = int(_recv_exact(sock, 4, interrupted), 16)
                        payload = _recv_exact(sock, size, interrupted) if size else b""
                        on_change(parse_devices(payload.decode("utf-8", errors="replace")))
            except _Interrupted:
                continue  # chiusura o pausa: decide il controllo in testa al ciclo
            except (OSError, ValueError, AdbError):
                # Server ADB riavviato o non raggiungibile: si riprova tra poco.
                on_change([])
                stop.wait(1.5)

    def device_info(self, serial: str) -> dict[str, str]:
        """Modello, produttore e versione Android con una sola chiamata alla shell."""
        command = (
            "getprop ro.product.model; getprop ro.product.manufacturer; "
            "getprop ro.build.version.release; getprop ro.build.version.sdk"
        )
        out = self.try_shell(command, serial=serial, timeout=15)
        values = [line.strip() for line in out.splitlines() if line.strip()]
        while len(values) < 4:
            values.append("")
        return {
            "model": values[0],
            "manufacturer": values[1],
            "android": values[2],
            "sdk": values[3],
        }

    def key(self, serial: str, keycode: int) -> None:
        """Preme un tasto con `input keyevent` (lento: avvia una JVM sul telefono)."""
        self.shell(f"input keyevent {int(keycode)}", serial=serial)

    # ------------------------------------------------------------ applicazioni

    def list_apps(self, serial: str, include_system: bool = False) -> list[AppInfo]:
        """Elenco delle applicazioni installate (package + nome derivato dal package).

        Il nome che l'utente vede sul telefono non e' esposto da ADB: lo
        fornisce bridge.app_labels(), da applicare con AppInfo.apply_labels().
        """
        apps: dict[str, AppInfo] = {}

        wanted = [("-3", False)] + ([("-s", True)] if include_system else [])
        for flag, is_system in wanted:
            out = self.try_shell(f"pm list packages {flag}", serial=serial, timeout=30)
            for line in out.splitlines():
                line = line.strip()
                if not line.startswith("package:"):
                    continue
                package = line.split(":", 1)[1].strip()
                if package:
                    apps[package] = AppInfo(
                        package=package, name=pretty_name(package), system=is_system
                    )

        for package, component in self._launcher_components(serial).items():
            app = apps.get(package)
            if app is not None:
                app.launchable = True
                app.component = component

        return sorted(apps.values(), key=lambda a: a.name.lower())

    def package_versions(self, serial: str) -> dict[str, str]:
        """versionName di ogni pacchetto installato, con una sola chiamata."""
        out = self.try_shell("dumpsys package packages", serial=serial, timeout=60)
        versions: dict[str, str] = {}
        current = ""
        for line in out.splitlines():
            if line.startswith("  Package [") and "]" in line:
                current = line[len("  Package ["):line.index("]")]
            elif current and line.startswith("    versionName=") and current not in versions:
                versions[current] = line.split("=", 1)[1].strip()
        return versions

    def _launcher_components(self, serial: str) -> dict[str, str]:
        """Mappa package -> activity di lancio, per avviare le app senza monkey."""
        out = self.try_shell(
            "cmd package query-activities --brief "
            "-a android.intent.action.MAIN -c android.intent.category.LAUNCHER",
            serial=serial,
            timeout=30,
        )
        components: dict[str, str] = {}
        for line in out.splitlines():
            line = line.strip()
            match = re.fullmatch(r"([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)", line)
            if match:
                components.setdefault(match.group(1), line)
        return components

    def launch_app(self, serial: str, app: AppInfo) -> str:
        """Avvia un'applicazione tramite il normale intent di lancio."""
        component = app.component
        if not component:
            brief = self.try_shell(
                f"cmd package resolve-activity --brief {app.package}", serial=serial, timeout=15
            )
            for line in reversed(brief.strip().splitlines()):
                line = line.strip()
                if "/" in line and " " not in line:
                    component = line
                    break
        if component:
            out = self.try_shell(f"am start -n '{component}'", serial=serial, timeout=20)
            if out and "Error" not in out:
                return out.strip()
        # Fallback universale quando l'activity non e' risolvibile.
        return self.shell(
            f"monkey -p {app.package} -c android.intent.category.LAUNCHER 1",
            serial=serial,
            timeout=20,
        ).strip()

    def stop_app(self, serial: str, package: str) -> None:
        """Chiude un'applicazione con il normale comando Android force-stop."""
        self.shell(f"am force-stop {package}", serial=serial, timeout=20)

    def install(
        self, serial: str, files: list[Path], flags: list[str], timeout: float = 900.0
    ) -> str:
        """Installa un APK, oppure piu' APK divisi (split) dello stesso pacchetto."""
        command = "install" if len(files) == 1 else "install-multiple"
        try:
            proc = run(
                self.base(serial) + [command, *flags, *(str(f) for f in files)],
                timeout=timeout,
                env=self.child_env(),
            )
        except subprocess.TimeoutExpired as exc:
            raise AdbError(tr("Installation aborted: time limit exceeded.")) from exc
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part.strip())
        if proc.returncode != 0 or "Success" not in output:
            raise AdbError(output or tr("adb returned exit code {code}").format(code=proc.returncode))
        return output

    def uninstall(self, serial: str, package: str) -> None:
        """Disinstalla un'applicazione (comando standard `adb uninstall`)."""
        out = self.call(["uninstall", package], serial=serial, timeout=120)
        if "Success" not in out:
            raise AdbError(out.strip() or tr("Uninstall failed."))

    def push(self, serial: str, local: Path, remote: str, timeout: float = 900.0) -> None:
        self.call(["push", str(local), remote], serial=serial, timeout=timeout)

    def forward(self, serial: str, remote: str) -> int:
        """Inoltra una porta TCP locale libera verso `remote`; restituisce la porta."""
        out = self.call(["forward", "tcp:0", remote], serial=serial, timeout=15)
        try:
            return int(out.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise AdbError(
                tr("adb forward did not return a port: {output}").format(output=repr(out.strip()))
            ) from exc

    def forward_remove(self, serial: str, port: int) -> None:
        if self.available:
            spawn_detached(
                self.base(serial) + ["forward", "--remove", f"tcp:{port}"], env=self.child_env()
            )

    # -------------------------------------------------------------- rubrica

    def open_contacts(self, serial: str) -> None:
        """Apre l'applicazione Contatti tramite intent pubblico."""
        out = self.try_shell(
            "am start -a android.intent.action.VIEW -d content://contacts/people/",
            serial=serial,
            timeout=20,
        )
        if not out.strip() or "Error" in out:
            self.shell(
                "am start -a android.intent.action.VIEW -t vnd.android.cursor.dir/contact",
                serial=serial,
                timeout=20,
            )

    def new_contact(self, serial: str, phone: str, name: str = "") -> None:
        """Apre la schermata di creazione contatto precompilata.

        Usa l'intent pubblico INSERT: non viene toccato il database dei contatti,
        l'utente conferma il salvataggio sul telefono.
        """
        command = (
            "am start -a android.intent.action.INSERT "
            "-t vnd.android.cursor.dir/contact "
            f'-e phone "{shell_quote(phone)}"'
        )
        if name.strip():
            command += f' -e name "{shell_quote(name)}"'
        self.shell(command, serial=serial, timeout=20)

    def dial(self, serial: str, phone: str) -> None:
        """Apre il dialer con il numero gia' inserito (non avvia la chiamata)."""
        digits = re.sub(r"[^0-9+*#]", "", phone)
        if not digits:
            raise AdbError(tr("Invalid phone number."))
        self.shell(
            f"am start -a android.intent.action.DIAL -d 'tel:{digits}'", serial=serial, timeout=20
        )

    # ------------------------------------------------------------- clipboard

    def type_text(self, serial: str, text: str) -> None:
        """Scrive il testo sul telefono, come se venisse digitato dalla tastiera."""
        for index, line in enumerate(split_lines(text)):
            if index:
                self.try_shell("input keyevent 66", serial=serial, timeout=15)  # ENTER
            for piece in chunks(line, 400):
                if piece:
                    self.shell(
                        f'input text "{escape_input_text(piece)}"', serial=serial, timeout=25
                    )

    def device_copy(self, serial: str) -> str:
        """Copia la selezione corrente sul telefono e prova a leggerne la clipboard.

        Ripiego usato solo senza canale di controllo diretto: da Android 10
        l'accesso agli appunti via shell e' quasi sempre negato.
        """
        self.try_shell("input keyevent 278", serial=serial, timeout=15)  # KEYCODE_COPY
        out = self.try_shell("cmd clipboard get-primary", serial=serial, timeout=15)
        text = out.strip()
        if not text or text.startswith("cmd:") or "Exception" in text or "Error:" in text:
            return ""
        if "No shell command implementation" in text or "Unknown command" in text:
            return ""
        return text

    # ------------------------------------------------------------ screenshot

    def screenshot(self, serial: str) -> bytes:
        """Acquisisce uno screenshot PNG dal dispositivo."""
        try:
            proc = run_binary(
                self.base(serial) + ["exec-out", "screencap", "-p"],
                timeout=60,
                env=self.child_env(),
            )
            data = proc.stdout or b""
        except (OSError, subprocess.SubprocessError):
            data = b""
        if data.startswith(b"\x89PNG"):
            return data
        return self._screenshot_via_pull(serial)

    def _screenshot_via_pull(self, serial: str) -> bytes:
        """Fallback: salva sul dispositivo, scarica sul PC e ripulisce."""
        remote = "/sdcard/_apc_screenshot.png"
        self.shell(f"screencap -p {remote}", serial=serial, timeout=60)
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "shot.png"
            self.call(["pull", remote, str(local)], serial=serial, timeout=60)
            data = local.read_bytes() if local.is_file() else b""
        self.try_shell(f"rm -f {remote}", serial=serial, timeout=15)
        if not data.startswith(b"\x89PNG"):
            raise AdbError(tr("Screenshot failed: the device did not return a valid PNG."))
        return data


# ------------------------------------------------------- protocollo del server


class _Interrupted(Exception):
    """L'ascolto e' stato interrotto dall'applicazione (chiusura o pausa)."""


def server_port() -> int:
    try:
        return int(os.environ.get("ANDROID_ADB_SERVER_PORT", "") or DEFAULT_SERVER_PORT)
    except ValueError:
        return DEFAULT_SERVER_PORT


def _recv_exact(sock: socket.socket, size: int, interrupted: Callable[[], bool]) -> bytes:
    """Legge esattamente `size` byte, controllando `interrupted` a ogni timeout del socket."""
    data = b""
    while len(data) < size:
        try:
            chunk = sock.recv(size - len(data))
        except socket.timeout:
            if interrupted():
                raise _Interrupted from None
            continue
        if not chunk:
            raise AdbError("Connessione al server ADB chiusa.")
        data += chunk
    return data


def _request(sock: socket.socket, service: str, interrupted: Callable[[], bool]) -> None:
    payload = service.encode("utf-8")
    sock.sendall(b"%04x" % len(payload) + payload)
    status = _recv_exact(sock, 4, interrupted)
    if status != b"OKAY":
        size = int(_recv_exact(sock, 4, interrupted), 16)
        reason = _recv_exact(sock, size, interrupted).decode("utf-8", errors="replace")
        raise AdbError(reason or "Richiesta rifiutata dal server ADB.")


def parse_devices(text: str) -> list[Device]:
    """Interpreta le righe `seriale stato chiave:valore ...` di `adb devices -l`."""
    found: list[Device] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        model = ""
        for token in parts[2:]:
            if token.startswith("model:"):
                model = token.split(":", 1)[1].replace("_", " ")
        found.append(Device(serial=serial, state=state, model=model))
    return found


# ----------------------------------------------------------------- helper


# Segmenti di package che non identificano l'applicazione.
_GENERIC_SEGMENTS = {
    "android", "app", "apps", "application", "client", "mobile", "main", "ui",
    "free", "pro", "lite", "beta", "release", "phone", "gms", "core",
}
_DOMAIN_SEGMENTS = {"com", "org", "net", "io", "co", "it", "de", "eu", "me", "tv"}


def pretty_name(package: str) -> str:
    """Nome leggibile derivato dal package name.

    L'etichetta reale dell'app non e' esposta da ADB senza aapt: si sceglie il
    segmento piu' significativo del package (es. com.instagram.android ->
    Instagram, com.whatsapp.w4b -> Whatsapp).
    """
    segments = [s for s in package.split(".") if s]
    if not segments:
        return package
    chosen = ""
    for segment in reversed(segments):
        low = segment.lower()
        if low in _GENERIC_SEGMENTS or low in _DOMAIN_SEGMENTS or len(segment) <= 3:
            continue
        chosen = segment
        break
    if not chosen:
        chosen = segments[-1]
    chosen = re.sub(r"[_\-]+", " ", chosen)
    chosen = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", chosen)
    return chosen.strip().title() or package


def shell_quote(value: str) -> str:
    """Protegge un valore da inserire tra doppi apici nella shell del telefono."""
    for ch in '\\"$`':
        value = value.replace(ch, "\\" + ch)
    return value


def escape_input_text(text: str) -> str:
    """Protegge i caratteri speciali per `adb shell input text`."""
    out = text.replace("\\", "\\\\")
    for ch in _INPUT_SPECIALS:
        out = out.replace(ch, "\\" + ch)
    return out.replace(" ", "%s")


def split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def is_ascii(text: str) -> bool:
    return all(ord(ch) < 128 for ch in text)
