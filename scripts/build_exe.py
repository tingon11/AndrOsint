# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Compila AndrOsint in un unico eseguibile Windows con PyInstaller.

Il risultato e' dist/AndrOsint.exe: un solo file, senza finestra console, con
l'icona «AO» e le proprieta' del file (versione, autore) compilate. Dentro ci
sono Python, le librerie, il logo e l'icona; ADB e scrcpy no: l'eseguibile li
cerca nella cartella tools/ accanto a se' e, se mancano, propone di scaricarli.
Accanto all'eseguibile finiscono anche config.json, apk/ e screenshots/.

PyInstaller viene installato nel virtualenv se non c'e'. L'icona, se manca,
viene rigenerata con make_brand.py (serve il carattere Panchang).

    .venv\\Scripts\\python.exe scripts\\build_exe.py
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from androidctl import APP_NAME, AUTHOR, COPYRIGHT, __version__  # noqa: E402

ASSETS = ROOT / "androidctl" / "ui" / "assets"
ICON = ASSETS / "androsint.ico"
BUILD = ROOT / "build"
DIST = ROOT / "dist"

# Proprieta' del file mostrate da Esplora risorse (lingua 0x0410 = italiano).
VERSION_INFO = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers}, prodvers={numbers},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0),
  ),
  kids=[
    StringFileInfo([StringTable('041004B0', [
      StringStruct('CompanyName', {author!r}),
      StringStruct('FileDescription', {name!r}),
      StringStruct('FileVersion', {version!r}),
      StringStruct('InternalName', {name!r}),
      StringStruct('LegalCopyright', {copyright!r}),
      StringStruct('OriginalFilename', {exe!r}),
      StringStruct('ProductName', {name!r}),
      StringStruct('ProductVersion', {version!r}),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0410, 1200])]),
  ],
)
"""


def ensure_icon() -> None:
    if ICON.is_file():
        return
    print("Icona assente: la rigenero con make_brand.py…")
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "make_brand.py")])


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller non presente: lo installo nel virtualenv…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def version_file() -> Path:
    parts = [int(p) for p in __version__.split(".") if p.isdigit()][:4]
    numbers = tuple(parts + [0] * (4 - len(parts)))
    target = BUILD / "version_info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        VERSION_INFO.format(
            numbers=numbers, author=AUTHOR, name=APP_NAME, version=__version__,
            copyright=COPYRIGHT, exe=f"{APP_NAME}.exe",
        ),
        encoding="utf-8",
    )
    return target


def main() -> int:
    if sys.platform != "win32":
        sys.exit("AndrOsint si compila solo su Windows.")
    ensure_icon()
    ensure_pyinstaller()

    argv = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", APP_NAME,
        "--icon", str(ICON),
        "--version-file", str(version_file()),
        # logo e icona: il programma li cerca accanto a theme.py
        "--add-data", f"{ASSETS}{os.pathsep}androidctl/ui/assets",
        # temi e caratteri di customtkinter sono file di dati, non moduli
        "--collect-data", "customtkinter",
        "--hidden-import", "PIL._tkinter_finder",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        str(ROOT / "main.py"),
    ]
    code = subprocess.call(argv, cwd=ROOT)
    if code != 0:
        return code

    exe = DIST / f"{APP_NAME}.exe"
    print(f"\n{exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
