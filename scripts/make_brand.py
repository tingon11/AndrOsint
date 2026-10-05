# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Rigenera logo e icona dell'applicazione (stile TagFaces / Seity).

Il logo e' la scritta bicolore "AndrOsint" nel carattere Panchang Semibold:
prima parte bianca, seconda nel colore d'accento dell'interfaccia. L'icona e'
il quadrato scuro arrotondato con le iniziali e la barretta d'accento.

Serve il carattere Panchang installato sul PC (Fontshare). I file prodotti
finiscono in androidctl/ui/assets/ e viaggiano con il programma: per usarlo
il carattere non serve.

    .venv\\Scripts\\python.exe scripts\\make_brand.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "androidctl" / "ui" / "assets"

WORD_WHITE = "Andr"
WORD_ACCENT = "Osint"
INITIALS = "AO"
ACCENT = "#7b95dd"
WEIGHT = b"Semibold"

FONT_FILE = "Panchang-Variable.ttf"
FONT_DIRS = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
)

LOGO_HEIGHT = 160  # altezza del PNG: abbondante, l'interfaccia lo riduce
ICON_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
              (64, 64), (128, 128), (256, 256)]


def font(size: int) -> ImageFont.FreeTypeFont:
    for folder in FONT_DIRS:
        path = folder / FONT_FILE
        if path.is_file():
            loaded = ImageFont.truetype(str(path), size)
            loaded.set_variation_by_name(WEIGHT)
            return loaded
    sys.exit(f"Carattere {FONT_FILE} non trovato: installalo da fontshare.com e riprova.")


def wordmark(white: str, accent: str, size: int = 400) -> Image.Image:
    """Scritta bicolore su fondo trasparente, ritagliata al vivo."""
    face = font(size)
    width = int(face.getlength(white + accent)) + size
    image = Image.new("RGBA", (width, size * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    x, y = size // 2, size // 2
    draw.text((x, y), white, font=face, fill="white")
    draw.text((x + face.getlength(white), y), accent, font=face, fill=ACCENT)
    return image.crop(image.getbbox())


def logo() -> Image.Image:
    mark = wordmark(WORD_WHITE, WORD_ACCENT)
    width = round(mark.width * LOGO_HEIGHT / mark.height)
    return mark.resize((width, LOGO_HEIGHT), Image.LANCZOS)


def icon() -> Image.Image:
    """Icona stile Seity, con le proporzioni dell'originale a 256 px:
    raggio 52, bordo 5, iniziali nel box 184x106 centrato a quota 115,
    barretta 85..170 x 192..209.
    """
    size = 1024
    k = size / 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(52 * k), fill=(40, 52, 66, 255))
    border = int(5 * k)
    draw.rounded_rectangle(
        (border, border, size - 1 - border, size - 1 - border),
        radius=int(47 * k), fill=(13, 17, 23, 255),
    )
    mark = wordmark(INITIALS, "")
    scale = min(184 * k / mark.width, 106 * k / mark.height)
    mark = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    image.alpha_composite(mark, ((size - mark.width) // 2, int(115 * k) - mark.height // 2))
    rgb = tuple(int(ACCENT.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    draw.rounded_rectangle(
        (int(85 * k), int(192 * k), int(170 * k), int(209 * k)),
        radius=int(8.5 * k), fill=rgb + (255,),
    )
    return image.resize((256, 256), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    mark = logo()
    mark.save(ASSETS / "logo.png")
    icon().save(ASSETS / "androsint.ico", "ICO", sizes=ICON_SIZES)
    print(f"logo.png {mark.size}, androsint.ico ({len(ICON_SIZES)} risoluzioni) in {ASSETS}")


if __name__ == "__main__":
    main()
