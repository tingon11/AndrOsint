# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Accesso diretto agli appunti di Windows (testo e immagini).

Tkinter espone solo il testo e lo consegna in modo differito; qui si scrive
subito negli appunti, anche un'immagine, cosi' uno screenshot si incolla
direttamente in un documento o in una chat.
"""

from __future__ import annotations

import contextlib
import io
import sys
import time

from .i18n import tr

AVAILABLE = sys.platform == "win32"

_CF_DIB = 8
_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_BMP_FILE_HEADER = 14


class ClipboardError(RuntimeError):
    """Gli appunti di Windows non sono accessibili in questo momento."""


if AVAILABLE:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.EmptyClipboard.restype = wintypes.BOOL
    _user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    _user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    _user32.GetClipboardData.argtypes = [wintypes.UINT]
    _user32.GetClipboardData.restype = ctypes.c_void_p
    _user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    _user32.SetClipboardData.restype = ctypes.c_void_p
    _user32.GetClipboardSequenceNumber.restype = wintypes.DWORD

    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalFree.restype = ctypes.c_void_p


@contextlib.contextmanager
def _opened():
    """Apre gli appunti, riprovando se un altro programma li sta usando."""
    for _ in range(12):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        raise ClipboardError(tr("The Windows clipboard is in use by another program."))
    try:
        yield
    finally:
        _user32.CloseClipboard()


def _put(fmt: int, data: bytes) -> None:
    handle = _kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
    if not handle:
        raise ClipboardError(tr("Not enough memory for the clipboard."))
    pointer = _kernel32.GlobalLock(handle)
    if not pointer:
        _kernel32.GlobalFree(handle)
        raise ClipboardError(tr("Clipboard memory not accessible."))
    ctypes.memmove(pointer, data, len(data))
    _kernel32.GlobalUnlock(handle)
    with _opened():
        _user32.EmptyClipboard()
        if not _user32.SetClipboardData(fmt, handle):
            # In caso di successo la memoria passa in gestione a Windows.
            _kernel32.GlobalFree(handle)
            raise ClipboardError(tr("Writing to the clipboard failed."))


def sequence() -> int:
    """Contatore che Windows incrementa a ogni modifica degli appunti."""
    return int(_user32.GetClipboardSequenceNumber()) if AVAILABLE else 0


def get_text() -> str:
    """Testo contenuto negli appunti (stringa vuota se non c'e' testo)."""
    if not AVAILABLE:
        return ""
    with _opened():
        if not _user32.IsClipboardFormatAvailable(_CF_UNICODETEXT):
            return ""
        handle = _user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            text = ctypes.wstring_at(pointer)
        finally:
            _kernel32.GlobalUnlock(handle)
    return text.replace("\r\n", "\n")


def set_text(text: str) -> None:
    """Scrive il testo negli appunti, con i ritorni a capo nel formato di Windows."""
    if not AVAILABLE:
        raise ClipboardError(tr("Clipboard available on Windows only."))
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    _put(_CF_UNICODETEXT, normalized.encode("utf-16-le") + b"\x00\x00")


def set_image(png: bytes) -> None:
    """Scrive un'immagine negli appunti a partire dai byte di un PNG."""
    if not AVAILABLE:
        raise ClipboardError(tr("Clipboard available on Windows only."))
    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "BMP")
    # Il formato CF_DIB e' un file BMP privato dell'intestazione di file.
    _put(_CF_DIB, buffer.getvalue()[_BMP_FILE_HEADER:])
