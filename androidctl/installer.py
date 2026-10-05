# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Installazione sul telefono di pacchetti Android, ed estrazione dal telefono.

Formati riconosciuti:

* `.apk` - pacchetto singolo, installato con `adb install`;
* `.apks`, `.xapk`, `.apkm` - archivi zip con l'APK base piu' gli APK divisi
  (split) per processore, densita' dello schermo e lingua, ed eventuali dati
  OBB. Si estraggono, si scelgono gli split adatti al telefono collegato e si
  installano insieme con `adb install-multiple`.

Sono i normali comandi di installazione di Android: valgono le stesse verifiche
(firma, versione, compatibilita') di un'installazione fatta a mano.

L'estrazione fa il percorso inverso: copia sul PC gli APK di un'app installata
(`pm path` + `adb pull`), piu' gli eventuali dati OBB, e li impacchetta in un
file che questa stessa pagina sa reinstallare su un altro telefono.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .adb import Adb, AdbError
from .i18n import N_, tr

KINDS = {".apk": "APK", ".apks": "APKS", ".xapk": "XAPK", ".apkm": "APKM"}

_ABIS = ("arm64_v8a", "armeabi_v7a", "armeabi", "x86_64", "x86", "mips64", "mips")
_DENSITIES = {
    "ldpi": 120, "mdpi": 160, "tvdpi": 213, "hdpi": 240,
    "xhdpi": 320, "xxhdpi": 480, "xxxhdpi": 640,
}
_OBB_PATH = re.compile(r"Android/obb/[A-Za-z0-9_.]+/[A-Za-z0-9_.\-]+\.obb")
_FAILURE = re.compile(r"\[([A-Z][A-Z0-9_]+)(?::\s*([^\]]*))?\]")
_EXCEPTION = re.compile(r"^[\w.$]+(?:Exception|Error):\s*(.+)$", re.MULTILINE)

# Cause piu' frequenti, spiegate in modo che si capisca cosa fare.
_HINTS = {
    "INSTALL_FAILED_ALREADY_EXISTS":
        N_("the app is already installed: enable “Update if already installed”."),
    "INSTALL_FAILED_VERSION_DOWNGRADE":
        N_("the phone has a newer version: enable “Allow older version” "
           "or uninstall the app first."),
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE":
        N_("the signature differs from the installed app: uninstall it and try again."),
    "INSTALL_FAILED_INSUFFICIENT_STORAGE":
        N_("not enough space on the phone."),
    "INSTALL_FAILED_NO_MATCHING_ABIS":
        N_("the package is not compatible with the phone's processor: download the "
           "right variant (usually arm64-v8a)."),
    "INSTALL_FAILED_OLDER_SDK":
        N_("the package requires a newer Android version than the phone's."),
    "INSTALL_FAILED_DEPRECATED_SDK_VERSION":
        N_("the package is too old for this Android version."),
    "INSTALL_FAILED_USER_RESTRICTED":
        N_("installation blocked by the phone: in Developer options enable "
           "“Install via USB” and confirm the prompt shown on the screen."),
    "INSTALL_FAILED_ABORTED":
        N_("installation cancelled on the phone."),
    "INSTALL_FAILED_MISSING_SPLIT":
        N_("this APK is only part of the app: the full package is needed "
           "(.apks, .xapk or .apkm)."),
    "INSTALL_FAILED_INVALID_APK":
        N_("invalid or corrupted package: download it again."),
    "INSTALL_PARSE_FAILED_NOT_APK":
        N_("the file is not a valid APK: download it again."),
    "INSTALL_PARSE_FAILED_NO_CERTIFICATES":
        N_("unsigned or corrupted package: download it again."),
    "INSTALL_FAILED_VERIFICATION_FAILURE":
        N_("blocked by the phone's security check (Play Protect)."),
    "INSTALL_FAILED_TEST_ONLY":
        N_("test-only package, cannot be installed normally."),
}

StatusCb = Callable[[str], None]


class InstallError(RuntimeError):
    """Installazione non riuscita, con una spiegazione leggibile."""


@dataclass(frozen=True)
class Options:
    replace: bool = True     # aggiorna l'app se e' gia' installata
    downgrade: bool = False  # accetta una versione precedente a quella installata
    grant: bool = False      # concede subito i permessi richiesti dall'app

    def flags(self) -> list[str]:
        flags = []
        if self.replace:
            flags.append("-r")
        if self.downgrade:
            flags.append("-d")
        if self.grant:
            flags.append("-g")
        return flags


@dataclass(frozen=True)
class Profile:
    """Caratteristiche del telefono che decidono quali split installare."""

    abis: tuple[str, ...] = ()  # in ordine di preferenza, es. ("arm64_v8a", "armeabi_v7a")
    density: int = 0            # dpi dello schermo, 0 se sconosciuta


def read_profile(adb: Adb, serial: str) -> Profile:
    out = adb.try_shell("getprop ro.product.cpu.abilist; wm density", serial=serial, timeout=20)
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    abis: tuple[str, ...] = ()
    if lines and "density" not in lines[0].lower():
        abis = tuple(a.strip().replace("-", "_") for a in lines[0].split(",") if a.strip())
    # "Override density" segue "Physical density" ed e' quella effettivamente in uso.
    found = re.findall(r"density:\s*(\d+)", out)
    return Profile(abis=abis, density=int(found[-1]) if found else 0)


# ----------------------------------------------------------------- ricerca


def is_package(path: Path) -> bool:
    return path.suffix.lower() in KINDS


def kind_of(path: Path) -> str:
    return KINDS.get(path.suffix.lower(), "")


def find_packages(folder: Path) -> list[Path]:
    """Pacchetti presenti nella cartella e nelle sue sottocartelle dirette."""
    found: list[Path] = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return found
    for entry in entries:
        try:
            if entry.is_file() and is_package(entry):
                found.append(entry)
            elif entry.is_dir():
                found.extend(
                    sorted(
                        (p for p in entry.iterdir() if p.is_file() and is_package(p)),
                        key=lambda p: p.name.lower(),
                    )
                )
        except OSError:
            continue
    return found


# ------------------------------------------------------------------- split


def split_kind(name: str) -> tuple[str, str]:
    """Classifica un APK diviso dal nome: ("abi", ...), ("density", ...) o ("", "").

    Copre le convenzioni in uso: `split_config.arm64_v8a.apk`, `config.xxhdpi.apk`
    e quella di bundletool, `base-arm64_v8a.apk`.
    """
    token = re.split(r"[.\-]", Path(name).stem.lower())[-1]
    if token in _ABIS:
        return "abi", token
    if token in _DENSITIES:
        return "density", token
    return "", ""


def select_splits(names: list[str], profile: Profile) -> list[str]:
    """Sceglie gli APK da installare: base, lingue e i soli split adatti al telefono.

    Gli split per altri processori verrebbero rifiutati o occuperebbero spazio
    inutilmente; se il telefono e' sconosciuto si tengono tutti.
    """
    kinds = {name: split_kind(name) for name in names}
    abis = {value for kind, value in kinds.values() if kind == "abi"}
    densities = {value for kind, value in kinds.values() if kind == "density"}

    best_abi = next((abi for abi in profile.abis if abi in abis), None)

    best_density = None
    if densities and profile.density > 0:
        ordered = sorted(densities, key=_DENSITIES.__getitem__)
        best_density = next(
            (d for d in ordered if _DENSITIES[d] >= profile.density), ordered[-1]
        )

    chosen = []
    for name in names:
        kind, value = kinds[name]
        if kind == "abi" and best_abi and value != best_abi:
            continue
        if kind == "density" and best_density and value != best_density:
            continue
        chosen.append(name)
    return chosen


# ------------------------------------------------------------ installazione


def explain(output: str) -> str:
    """Trasforma l'errore di adb in una frase che dica cosa e' successo."""
    match = _FAILURE.search(output)
    if match:
        code, detail = match.group(1), (match.group(2) or "").strip()
        hint = _HINTS.get(code)
        if hint:
            return f"{tr(hint)} ({code})"
        return f"{code}: {detail}" if detail else code
    # Senza un codice INSTALL_*: l'eccezione di Android, non la coda dello stack trace.
    crash = _EXCEPTION.search(output)
    if crash:
        return crash.group(1).strip()
    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.lstrip().startswith(("at ", "Performing "))
    ]
    return lines[-1] if lines else tr("unknown error.")


def install(
    adb: Adb,
    serial: str,
    path: Path,
    options: Options,
    profile: Profile | None = None,
    status: StatusCb | None = None,
) -> str:
    """Installa un pacchetto e restituisce un breve resoconto."""
    report = status or (lambda _text: None)
    if not path.is_file():
        raise InstallError(tr("the file no longer exists."))
    if path.stat().st_size == 0:
        raise InstallError(tr("the file is empty: the download did not complete."))
    try:
        if path.suffix.lower() == ".apk":
            report(tr("Installing…"))
            adb.install(serial, [path], options.flags())
            return tr("Installed")
        return _install_bundle(adb, serial, path, options, profile or Profile(), report)
    except AdbError as exc:
        raise InstallError(explain(str(exc))) from exc
    except zipfile.BadZipFile as exc:
        raise InstallError(tr("corrupted or invalid archive: download it again.")) from exc
    except OSError as exc:
        raise InstallError(str(exc)) from exc


def _install_bundle(
    adb: Adb, serial: str, path: Path, options: Options, profile: Profile, report: StatusCb
) -> str:
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix="apc_") as tmp:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        apks = [n for n in names if n.lower().endswith(".apk")]
        # Archivi di bundletool: splits/ contiene l'app, standalones/ varianti alternative.
        splits = [n for n in apks if n.lower().startswith("splits/")]
        if splits:
            apks = splits
        else:
            apks = [n for n in apks if not n.lower().startswith("standalones/")] or apks
        if not apks:
            raise InstallError(tr("the archive contains no APK."))

        chosen = select_splits(apks, profile)
        report(tr("Extracting…"))
        folder = Path(tmp)
        files = [
            _extract(archive, member, folder / f"{index:02d}_{Path(member).name}")
            for index, member in enumerate(chosen)
        ]

        report(tr("Installing…"))
        adb.install(serial, files, options.flags())
        summary = (
            tr("Installed")
            if len(files) == 1
            else tr("Installed ({count} APKs)").format(count=len(files))
        )

        obbs = [n for n in names if n.lower().endswith(".obb")]
        if obbs:
            package = _package_name(archive)
            copied = 0
            for index, member in enumerate(obbs):
                remote = _obb_target(member, package)
                if remote is None:
                    continue
                report(tr("Copying OBB data…"))
                local = _extract(archive, member, folder / f"obb{index:02d}.obb")
                adb.shell(f"mkdir -p '{remote.rsplit('/', 1)[0]}'", serial=serial, timeout=30)
                adb.push(serial, local, remote)
                local.unlink(missing_ok=True)
                copied += 1
            if copied:
                summary += f" + {copied} OBB"
            else:
                summary += tr(" (OBB data not copied: unknown destination)")
        return summary


def _extract(archive: zipfile.ZipFile, member: str, target: Path) -> Path:
    """Estrae un singolo file con un nome scelto da noi, mai dal contenuto dello zip."""
    with archive.open(member) as source, target.open("wb") as handle:
        shutil.copyfileobj(source, handle, 1024 * 1024)
    return target


def _package_name(archive: zipfile.ZipFile) -> str:
    """Nome del pacchetto dai metadati dell'archivio (XAPK: manifest.json, APKM: info.json)."""
    for member, key in (("manifest.json", "package_name"), ("info.json", "pname")):
        try:
            data = json.loads(archive.read(member).decode("utf-8", errors="replace"))
        except (KeyError, ValueError):
            continue
        value = str(data.get(key) or "") if isinstance(data, dict) else ""
        if re.fullmatch(r"[A-Za-z0-9_.]+", value):
            return value
    return ""


def _obb_target(member: str, package: str) -> str | None:
    """Destinazione sul telefono di un file OBB contenuto nell'archivio."""
    if _OBB_PATH.fullmatch(member) and ".." not in member:
        return f"/sdcard/{member}"
    name = Path(member).name
    if package and re.fullmatch(r"[A-Za-z0-9_.\-]+\.obb", name):
        return f"/sdcard/Android/obb/{package}/{name}"
    return None


# ---------------------------------------------------------------- estrazione

_OBB_DIR = "/sdcard/Android/obb"
_SAFE = re.compile(r"[^A-Za-z0-9_.\-]+")
_FILENAME_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def file_label(label: str) -> str:
    """Nome dell'app reso utilizzabile come nome di file su Windows."""
    cleaned = _FILENAME_FORBIDDEN.sub(" ", label)
    cleaned = " ".join(cleaned.split()).strip(" .")
    return cleaned[:60].strip(" .")


def installed_files(adb: Adb, serial: str, package: str) -> list[str]:
    """Percorsi sul telefono degli APK di un'app installata (base + split)."""
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise InstallError(tr("invalid package name: {package}").format(package=repr(package)))
    try:
        out = adb.shell(f"pm path {package}", serial=serial, timeout=30)
    except AdbError as exc:
        raise InstallError(str(exc)) from exc
    files = [
        line.split(":", 1)[1].strip()
        for line in out.splitlines()
        if line.strip().startswith("package:")
    ]
    if not files:
        raise InstallError(tr("the app is not installed on the phone."))
    return files


def installed_version(adb: Adb, serial: str, package: str) -> str:
    out = adb.try_shell(f"dumpsys package {package} | grep -m1 versionName", serial=serial, timeout=30)
    match = re.search(r"versionName=(\S+)", out)
    return match.group(1) if match else ""


def obb_files(adb: Adb, serial: str, package: str) -> list[str]:
    """File OBB dell'app (dati aggiuntivi dei giochi), se presenti."""
    out = adb.try_shell(f"ls {_OBB_DIR}/{package}/ 2>/dev/null", serial=serial, timeout=30)
    return [f"{_OBB_DIR}/{package}/{name}" for name in out.split() if name.endswith(".obb")]


def export(
    adb: Adb,
    serial: str,
    package: str,
    folder: Path,
    label: str = "",
    status: StatusCb | None = None,
) -> Path:
    """Copia sul PC l'app installata e restituisce il file creato.

    Il file si chiama `<Nome> (<package>) <versione>` quando il nome visibile
    dell'app e' noto, altrimenti `<package> <versione>`. Un'app in un solo APK
    ha estensione .apk; con split o dati OBB diventa un archivio .apks, che
    install() sa reinstallare. Un file con lo stesso nome (stessa app, stessa
    versione) viene sostituito.
    """
    report = status or (lambda _text: None)
    report(tr("Reading the app on the phone…"))
    apks = installed_files(adb, serial, package)
    obbs = obb_files(adb, serial, package)
    version = _SAFE.sub("_", installed_version(adb, serial, package)).strip("_.")
    stem = " ".join(part for part in (file_label(label), f"({package})" if label else package, version) if part)
    bundle = len(apks) > 1 or bool(obbs)
    target = folder / f"{stem}{'.apks' if bundle else '.apk'}"

    folder.mkdir(parents=True, exist_ok=True)
    # Cartella di lavoro accanto alla destinazione: lo spostamento finale e' immediato.
    with tempfile.TemporaryDirectory(prefix=".apc_", dir=folder) as tmp:
        work = Path(tmp)
        total = len(apks) + len(obbs)
        pulled: list[tuple[Path, str]] = []
        for index, remote in enumerate(apks + obbs, start=1):
            name = remote.rsplit("/", 1)[-1]
            report(
                tr("Copying {index} of {total}: {name}…").format(index=index, total=total, name=name)
            )
            local = work / f"{index:02d}_{name}"
            try:
                adb.call(["pull", remote, str(local)], serial=serial, timeout=1800)
            except AdbError as exc:
                raise InstallError(
                    tr("copy of {name} failed: {error}").format(name=name, error=exc)
                ) from exc
            if not local.is_file() or local.stat().st_size == 0:
                raise InstallError(tr("copy of {name} failed: empty file.").format(name=name))
            arcname = f"Android/obb/{package}/{name}" if remote in obbs else name
            pulled.append((local, arcname))

        if not bundle:
            pulled[0][0].replace(target)
            return target

        report(tr("Building the package…"))
        partial = work / "bundle.apks"
        # Gli APK sono gia' compressi: si archivia senza ricomprimere.
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_STORED) as archive:
            for local, arcname in pulled:
                archive.write(local, arcname)
        partial.replace(target)
    return target


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.2f} GB"
