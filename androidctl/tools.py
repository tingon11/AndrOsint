# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Verifica e download automatico di ADB e scrcpy nella cartella tools/.

Il download avviene esclusivamente dalle sorgenti ufficiali dei due progetti:

* ADB (platform-tools): https://developer.android.com/tools/releases/platform-tools
  pacchetto ufficiale Google `platform-tools-latest-windows.zip`;
* scrcpy: release ufficiali del progetto Genymobile/scrcpy su GitHub.

Nessuna installazione globale, nessuna modifica al PATH di Windows, nessun
privilegio amministrativo richiesto: tutto resta dentro la cartella tools/.
"""

from __future__ import annotations

import json
import platform
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__, paths
from .i18n import tr

ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
SCRCPY_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
SCRCPY_RELEASES_PAGE = "https://github.com/Genymobile/scrcpy/releases/latest"

USER_AGENT = f"AndrOsint/{__version__}"

ProgressCb = Callable[[str, int, int], None]


class ToolsError(RuntimeError):
    """Errore durante la verifica o il download degli strumenti."""


@dataclass
class ToolStatus:
    name: str
    present: bool
    path: Path | None
    version: str = ""

    @property
    def text(self) -> str:
        if not self.present:
            return tr("Missing")
        return f"OK{f' - v{self.version}' if self.version else ''}"


def status() -> dict[str, ToolStatus]:
    """Stato corrente dei due strumenti in tools/."""
    adb = paths.adb_path()
    scrcpy = paths.scrcpy_path()
    return {
        "adb": ToolStatus("ADB", adb is not None, adb),
        "scrcpy": ToolStatus("scrcpy", scrcpy is not None, scrcpy),
    }


def missing() -> list[str]:
    """Chiavi degli strumenti mancanti ('adb', 'scrcpy')."""
    return [key for key, value in status().items() if not value.present]


# --------------------------------------------------------------- download


def _open(url: str, timeout: float = 30.0):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def _download(url: str, target: Path, label: str, progress: ProgressCb | None) -> None:
    """Scarica un file mostrando l'avanzamento."""
    try:
        with _open(url, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with target.open("wb") as handle:
                while True:
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    handle.write(block)
                    done += len(block)
                    if progress:
                        progress(tr("Downloading {label}").format(label=label), done, total)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ToolsError(
            tr("Download of {label} failed: {error}").format(label=label, error=exc)
        ) from exc


def _safe_extract(archive: Path, destination: Path) -> Path:
    """Estrae uno zip in una cartella temporanea, rifiutando percorsi sospetti."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if not (root / member).resolve().is_relative_to(root):
                    raise ToolsError(
                        tr("Invalid archive: suspicious path '{member}'.").format(member=member)
                    )
            zf.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise ToolsError(tr("The downloaded file is not a valid zip archive.")) from exc
    return destination


def _strip_single_root(folder: Path) -> Path:
    """Se lo zip contiene una sola cartella radice, restituisce quella."""
    entries = [p for p in folder.iterdir() if p.name not in (".", "..")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return folder


def _replace_dir(source: Path, target: Path) -> None:
    """Sostituisce la cartella di destinazione con il contenuto scaricato."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name(target.name + ".old")
        shutil.rmtree(backup, ignore_errors=True)
        try:
            target.rename(backup)
        except OSError as exc:
            raise ToolsError(
                tr("Cannot update '{name}': files in use. Close the mirroring and try again.").format(
                    name=target.name
                )
            ) from exc
        shutil.rmtree(backup, ignore_errors=True)
    shutil.move(str(source), str(target))


def install_adb(progress: ProgressCb | None = None) -> Path:
    """Scarica ed estrae platform-tools (ADB) dal pacchetto ufficiale Google."""
    paths.ensure_dirs()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "platform-tools.zip"
        _download(ADB_URL, archive, "ADB (platform-tools)", progress)

        if progress:
            progress(tr("Extracting ADB"), 0, 0)
        extracted = _strip_single_root(_safe_extract(archive, tmp_dir / "out"))
        if not (extracted / "adb.exe").is_file():
            raise ToolsError(tr("The downloaded package does not contain adb.exe."))
        _replace_dir(extracted, paths.PLATFORM_TOOLS_DIR)

    exe = paths.adb_path()
    if exe is None:
        raise ToolsError(tr("adb.exe is missing after extraction."))
    return exe


def _scrcpy_asset_url() -> tuple[str, str]:
    """Trova l'asset Windows dell'ultima release ufficiale di scrcpy."""
    try:
        with _open(SCRCPY_API, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        raise ToolsError(
            tr("Cannot reach the official scrcpy releases: {error}\nDownload manually from {url}").format(
                error=exc, url=SCRCPY_RELEASES_PAGE
            )
        ) from exc

    tag = str(data.get("tag_name") or "")
    assets = data.get("assets") or []
    wanted = "win64" if platform.machine().endswith("64") else "win32"

    def pick(keyword: str) -> str:
        for asset in assets:
            name = str(asset.get("name") or "")
            if keyword in name.lower() and name.lower().endswith(".zip"):
                return str(asset.get("browser_download_url") or "")
        return ""

    url = pick(wanted) or pick("win64") or pick("win32")
    if not url:
        raise ToolsError(
            tr(
                "No Windows package found in the latest scrcpy release.\n"
                "Download manually from {url}"
            ).format(url=SCRCPY_RELEASES_PAGE)
        )
    return url, tag


def install_scrcpy(progress: ProgressCb | None = None) -> Path:
    """Scarica ed estrae l'ultima release ufficiale di scrcpy per Windows."""
    paths.ensure_dirs()
    if progress:
        progress(tr("Looking for the latest scrcpy release"), 0, 0)
    url, tag = _scrcpy_asset_url()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "scrcpy.zip"
        _download(url, archive, f"scrcpy {tag}".strip(), progress)

        if progress:
            progress(tr("Extracting scrcpy"), 0, 0)
        extracted = _strip_single_root(_safe_extract(archive, tmp_dir / "out"))
        if not (extracted / "scrcpy.exe").is_file():
            raise ToolsError(tr("The downloaded package does not contain scrcpy.exe."))
        _replace_dir(extracted, paths.SCRCPY_DIR)

    exe = paths.scrcpy_path()
    if exe is None:
        raise ToolsError(tr("scrcpy.exe is missing after extraction."))
    return exe


def install(keys: list[str], progress: ProgressCb | None = None) -> list[str]:
    """Installa gli strumenti richiesti; restituisce i messaggi di esito."""
    results: list[str] = []
    for key in keys:
        if key == "adb":
            exe = install_adb(progress)
            results.append(tr("ADB installed: {path}").format(path=_relative(exe)))
        elif key == "scrcpy":
            exe = install_scrcpy(progress)
            results.append(tr("scrcpy installed: {path}").format(path=_relative(exe)))
        else:
            raise ToolsError(tr("Unknown tool: {key}").format(key=key))
    return results


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(paths.APP_DIR))
    except ValueError:
        return str(path)
