# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""AndrOsint - punto di ingresso.

Telecomando desktop per un telefono Android collegato via USB.
Usa ADB e scrcpy come programmi standalone nella cartella tools/.
"""

from __future__ import annotations

import sys


def _fail(message: str) -> int:
    """Segnala un avvio impossibile anche senza console (Avvia.bat usa pythonw)."""
    if sys.stderr is not None:
        print(message, file=sys.stderr)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "AndrOsint", 0x10)
    return 1


def main() -> int:
    from androidctl import i18n
    from androidctl.config import Config

    i18n.set_language(Config().get("language"))
    try:
        from androidctl.ui import run
    except ImportError as exc:  # pragma: no cover - ambiente incompleto
        return _fail(
            i18n.tr(
                "Cannot start the interface: {error}\n\n"
                "Install the dependencies with:\n"
                "    python -m pip install -r requirements.txt"
            ).format(error=exc)
        )
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
