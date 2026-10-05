# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Nome, package e versione di un pacchetto Android letti dal file, senza aapt.

Dentro un APK il manifest e' in XML binario e il nome dell'app e' di norma un
riferimento a una stringa in `resources.arsc`, tradotta per lingua. Qui si
leggono solo le parti necessarie dei due formati (quelli di aapt, stabili da
Android 1.0): abbastanza per mostrare "WhatsApp 2.26.38" invece del nome file.

Per gli archivi .xapk e .apkm il nome e' gia' nei metadati JSON; per .apks si
legge l'APK base contenuto nell'archivio.
"""

from __future__ import annotations

import io
import json
import locale
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Tipi di chunk dei formati binari di Android (ResourceTypes.h)
_RES_STRING_POOL = 0x0001
_RES_TABLE = 0x0002
_RES_XML = 0x0003
_RES_XML_START_ELEMENT = 0x0102
_RES_XML_RESOURCE_MAP = 0x0180
_RES_TABLE_PACKAGE = 0x0200
_RES_TABLE_TYPE = 0x0201

_TYPE_REFERENCE = 0x01
_TYPE_STRING = 0x03

_ATTR_LABEL = 0x01010001
_ATTR_VERSION_NAME = 0x0101021C

_FLAG_SORTED_UTF8 = 0x100
_FLAG_SPARSE = 0x01
_FLAG_OFFSET16 = 0x02
_ENTRY_COMPLEX = 0x0001

_BASE_NAMES = ("base.apk", "base-master.apk", "splits/base-master.apk")
_MAX_INNER = 400 * 1024 * 1024  # oltre, l'APK base non viene letto (memoria)
_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+")


@dataclass
class ApkInfo:
    package: str = ""
    label: str = ""
    version: str = ""

    @property
    def title(self) -> str:
        """Nome e versione da mostrare, oppure stringa vuota."""
        if not self.label:
            return ""
        return f"{self.label} {self.version}".strip()


class ApkFormatError(ValueError):
    """Il file non ha la struttura attesa."""


def system_language() -> str:
    """Lingua dell'interfaccia di Windows ("it", "en", ...), per scegliere la traduzione."""
    if sys.platform == "win32":
        try:
            import ctypes

            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            name = locale.windows_locale.get(langid, "")
        except (AttributeError, OSError):
            name = ""
    else:
        name = locale.getlocale()[0] or ""
    match = re.match(r"([a-z]{2,3})(?:[_-]|$)", name.lower())
    return match.group(1) if match else ""


# ------------------------------------------------------------- lettura file


def read(path: Path, lang: str = "") -> ApkInfo:
    """Informazioni del pacchetto; i campi che non si riescono a leggere restano vuoti."""
    suffix = path.suffix.lower()
    try:
        with zipfile.ZipFile(path) as archive:
            if suffix == ".apk":
                return _from_apk(archive, lang)
            info = _from_metadata(archive)
            if info.label and info.package:
                return info
            inner = _from_bundle(archive, lang)
            return ApkInfo(
                package=info.package or inner.package,
                label=info.label or inner.label,
                version=info.version or inner.version,
            )
    except (OSError, zipfile.BadZipFile, ApkFormatError, struct.error, KeyError, ValueError):
        return ApkInfo()


def _from_metadata(archive: zipfile.ZipFile) -> ApkInfo:
    """XAPK (manifest.json) e APKM (info.json) dichiarano nome e versione."""
    for member, keys in (
        ("manifest.json", ("name", "package_name", "version_name")),
        ("info.json", ("app_name", "pname", "release_version")),
    ):
        try:
            data = json.loads(archive.read(member).decode("utf-8", errors="replace"))
        except (KeyError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        label, package, version = (str(data.get(k) or "").strip() for k in keys)
        if not _PACKAGE.fullmatch(package):
            package = ""
        return ApkInfo(package=package, label=label, version=version)
    return ApkInfo()


def _from_bundle(archive: zipfile.ZipFile, lang: str) -> ApkInfo:
    """Legge l'APK base contenuto in un archivio .apks/.xapk/.apkm."""
    members = {m.filename: m for m in archive.infolist() if m.filename.lower().endswith(".apk")}
    ordered = [n for n in _BASE_NAMES if n in members]
    ordered += sorted(n for n in members if n not in ordered and "config" not in n.lower())
    ordered += sorted(n for n in members if n not in ordered)
    for name in ordered[:6]:
        if members[name].file_size > _MAX_INNER:
            continue
        with archive.open(name) as handle:
            raw = handle.read()
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as inner:
                info, is_split = _parse(inner, lang)
        except (zipfile.BadZipFile, ApkFormatError, struct.error, KeyError, ValueError):
            continue
        if not is_split:
            return info
    return ApkInfo()


def _from_apk(archive: zipfile.ZipFile, lang: str) -> ApkInfo:
    info, _is_split = _parse(archive, lang)
    return info


def _parse(archive: zipfile.ZipFile, lang: str) -> tuple[ApkInfo, bool]:
    manifest = _manifest(archive.read("AndroidManifest.xml"))
    label = manifest.get("label", "")
    if isinstance(label, int):
        # Riferimento a una risorsa: la stringa sta in resources.arsc.
        try:
            label = _resource_string(archive.read("resources.arsc"), label, lang)
        except (KeyError, ApkFormatError, struct.error):
            label = ""
    package = str(manifest.get("package", ""))
    if not _PACKAGE.fullmatch(package):
        package = ""
    version = manifest.get("versionName", "")
    return (
        ApkInfo(package=package, label=str(label).strip(), version=str(version).strip()),
        bool(manifest.get("split")),
    )


# ---------------------------------------------------------- formati binari


def _string_pool(data: bytes, offset: int) -> list[str]:
    _type, header_size, _size, count, _styles, flags, strings_start, _styles_start = (
        struct.unpack_from("<HHIIIIII", data, offset)
    )
    offsets = struct.unpack_from(f"<{count}I", data, offset + header_size)
    base = offset + strings_start
    utf8 = bool(flags & _FLAG_SORTED_UTF8)
    strings: list[str] = []
    for entry in offsets:
        pos = base + entry
        if utf8:
            chars = data[pos]
            pos += 2 if chars & 0x80 else 1
            length = data[pos]
            pos += 1
            if length & 0x80:
                length = ((length & 0x7F) << 8) | data[pos]
                pos += 1
            strings.append(data[pos : pos + length].decode("utf-8", errors="replace"))
        else:
            (length,) = struct.unpack_from("<H", data, pos)
            pos += 2
            if length & 0x8000:
                (low,) = struct.unpack_from("<H", data, pos)
                length = ((length & 0x7FFF) << 16) | low
                pos += 2
            strings.append(data[pos : pos + length * 2].decode("utf-16-le", errors="replace"))
    return strings


def _manifest(data: bytes) -> dict:
    """Attributi utili di <manifest> e <application> dal manifest binario.

    `label` e' una stringa, oppure un int se e' un riferimento a una risorsa.
    """
    if len(data) < 8 or struct.unpack_from("<H", data, 0)[0] != _RES_XML:
        raise ApkFormatError("AndroidManifest.xml non e' in formato binario")
    strings: list[str] = []
    resource_map: tuple[int, ...] = ()
    found: dict = {}
    offset = 8
    while offset + 8 <= len(data):
        chunk_type, header_size, size = struct.unpack_from("<HHI", data, offset)
        if size < 8:
            raise ApkFormatError("chunk non valido")
        if chunk_type == _RES_STRING_POOL:
            strings = _string_pool(data, offset)
        elif chunk_type == _RES_XML_RESOURCE_MAP:
            resource_map = struct.unpack_from(f"<{(size - header_size) // 4}I", data, offset + header_size)
        elif chunk_type == _RES_XML_START_ELEMENT:
            body = offset + header_size
            _ns, name, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", data, body)
            tag = strings[name] if name < len(strings) else ""
            if tag in ("manifest", "application"):
                for index in range(attr_count):
                    at = body + attr_start + index * attr_size
                    _ans, aname, raw, _vsize, _res0, vtype, vdata = struct.unpack_from(
                        "<IIIHBBI", data, at
                    )
                    resid = resource_map[aname] if aname < len(resource_map) else 0
                    key = strings[aname] if aname < len(strings) else ""
                    if vtype == _TYPE_STRING:
                        value = strings[vdata] if vdata < len(strings) else ""
                    elif raw != 0xFFFFFFFF and raw < len(strings) and vtype != _TYPE_REFERENCE:
                        value = strings[raw]
                    elif vtype == _TYPE_REFERENCE:
                        value = vdata
                    else:
                        continue
                    if tag == "manifest" and key in ("package", "split"):
                        found[key] = value
                    elif tag == "manifest" and (resid == _ATTR_VERSION_NAME or key == "versionName"):
                        found["versionName"] = value if isinstance(value, str) else ""
                    elif tag == "application" and (resid == _ATTR_LABEL or key == "label"):
                        found["label"] = value
            if tag == "application":
                break
        offset += size
    return found


def _resource_string(data: bytes, resid: int, lang: str, depth: int = 0) -> str:
    """Stringa della risorsa `resid`, nella lingua richiesta se tradotta."""
    if len(data) < 12 or struct.unpack_from("<H", data, 0)[0] != _RES_TABLE:
        raise ApkFormatError("resources.arsc non valido")
    wanted_package = resid >> 24
    wanted_type = (resid >> 16) & 0xFF
    wanted_entry = resid & 0xFFFF
    strings: list[str] = []
    candidates: dict[str, tuple[int, int]] = {}  # lingua -> (tipo, valore)

    offset = struct.unpack_from("<H", data, 2)[0]
    while offset + 8 <= len(data):
        chunk_type, header_size, size = struct.unpack_from("<HHI", data, offset)
        if size < 8:
            break
        if chunk_type == _RES_STRING_POOL and not strings:
            strings = _string_pool(data, offset)
        elif chunk_type == _RES_TABLE_PACKAGE:
            (package_id,) = struct.unpack_from("<I", data, offset + 8)
            if package_id == wanted_package:
                _collect_entries(data, offset, header_size, size, wanted_type, wanted_entry, candidates)
        offset += size

    for language in (lang, "", *sorted(candidates)):
        value = candidates.get(language)
        if value is None:
            continue
        vtype, vdata = value
        if vtype == _TYPE_STRING and vdata < len(strings):
            return strings[vdata]
        if vtype == _TYPE_REFERENCE and depth < 3:
            return _resource_string(data, vdata, lang, depth + 1)
    return ""


def _collect_entries(
    data: bytes,
    start: int,
    header_size: int,
    size: int,
    wanted_type: int,
    wanted_entry: int,
    out: dict[str, tuple[int, int]],
) -> None:
    """Raccoglie, per ogni configurazione, il valore della voce cercata."""
    offset = start + header_size
    end = start + size
    while offset + 8 <= end:
        chunk_type, chunk_header, chunk_size = struct.unpack_from("<HHI", data, offset)
        if chunk_size < 8:
            break
        if chunk_type == _RES_TABLE_TYPE and data[offset + 8] == wanted_type:
            flags = data[offset + 9]
            entry_count, entries_start = struct.unpack_from("<II", data, offset + 12)
            language = _config_language(data, offset + 20)
            entry = _entry_offset(data, offset + chunk_header, flags, entry_count, wanted_entry)
            if entry is not None:
                pos = offset + entries_start + entry
                _esize, eflags = struct.unpack_from("<HH", data, pos)
                if not eflags & _ENTRY_COMPLEX:
                    _vsize, _res0, vtype, vdata = struct.unpack_from("<HBBI", data, pos + 8)
                    out.setdefault(language, (vtype, vdata))
        offset += chunk_size


def _entry_offset(data: bytes, table: int, flags: int, count: int, wanted: int) -> int | None:
    if flags & _FLAG_SPARSE:
        for index in range(count):
            entry_index, packed = struct.unpack_from("<HH", data, table + index * 4)
            if entry_index == wanted:
                return packed * 4
        return None
    if wanted >= count:
        return None
    if flags & _FLAG_OFFSET16:
        (packed,) = struct.unpack_from("<H", data, table + wanted * 2)
        return None if packed == 0xFFFF else packed * 4
    (value,) = struct.unpack_from("<I", data, table + wanted * 4)
    return None if value == 0xFFFFFFFF else value


def _config_language(data: bytes, config: int) -> str:
    """Lingua della configurazione ("" = predefinita, quella senza traduzione)."""
    raw = data[config + 8 : config + 10]
    if raw == b"\x00\x00":
        return ""
    if raw[0] & 0x80:
        # Codice a tre lettere impacchettato (raro): si tratta come lingua a parte.
        return raw.hex()
    return raw.decode("ascii", errors="replace").lower()
