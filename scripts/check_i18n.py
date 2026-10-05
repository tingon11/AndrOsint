# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Controlla che ogni testo dell'interfaccia abbia la traduzione italiana.

Legge i sorgenti senza eseguirli: raccoglie i testi passati a tr() e N_() e li
confronta con translations.IT. Segnala le traduzioni mancanti, quelle che
nessun testo usa piu', le chiavi ripetute e i segnaposto {nome} che non
coincidono tra inglese e italiano. Da lanciare dopo aver aggiunto o cambiato
un testo:

    .venv\\Scripts\\python.exe scripts\\check_i18n.py
"""

from __future__ import annotations

import ast
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from androidctl.translations import IT  # noqa: E402

MARKERS = {"tr", "N_"}
CATALOG = ROOT / "androidctl" / "translations.py"


def used_texts() -> dict[str, str]:
    """Testi marcati nei sorgenti, ognuno con il primo punto in cui compare."""
    found: dict[str, str] = {}
    for path in [ROOT / "main.py", *sorted((ROOT / "androidctl").rglob("*.py"))]:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            first = node.args[0]
            if name not in MARKERS:
                continue
            where = f"{path.relative_to(ROOT)}:{node.lineno}"
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.setdefault(first.value, where)
            elif isinstance(first, ast.JoinedStr):
                # Una f-string cambia a ogni chiamata: non puo' fare da chiave.
                found.setdefault(f"<f-string in {where}>", where)
    return found


def repeated_keys() -> list[str]:
    """Chiavi scritte due volte nel dizionario: la seconda cancellerebbe la prima."""
    tree = ast.parse(CATALOG.read_text(encoding="utf-8"), str(CATALOG))
    seen: set[str] = set()
    repeated: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant):
                    if key.value in seen:
                        repeated.append(key.value)
                    seen.add(key.value)
    return repeated


def fields(text: str) -> set[str]:
    return {name for _literal, name, _spec, _conv in string.Formatter().parse(text) if name}


def main() -> int:
    used = used_texts()
    problems: list[str] = []
    for text, where in used.items():
        if text not in IT:
            problems.append(f"manca la traduzione ({where}): {text!r}")
    for text in IT:
        if text not in used:
            problems.append(f"traduzione non piu' usata: {text!r}")
    for text in repeated_keys():
        problems.append(f"chiave ripetuta: {text!r}")
    for text, translated in IT.items():
        if fields(text) != fields(translated):
            problems.append(f"segnaposto diversi: {text!r} -> {translated!r}")

    for line in problems:
        print(line)
    print(f"{len(used)} testi, {len(IT)} traduzioni, {len(problems)} problemi")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
