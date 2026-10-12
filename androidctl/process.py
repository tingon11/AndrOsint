# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Processi esterni: avvio senza finestre console e fine insieme all'applicazione.

adb e scrcpy sono programmi a parte: se l'applicazione si chiude, o si
interrompe per un errore, da soli resterebbero in esecuzione. Su Windows
vengono quindi messi in un «job» creato con l'opzione «termina alla chiusura»:
quando l'applicazione esce, in qualunque modo (chiusura normale, errore,
processo terminato a forza), il sistema chiude il job e con lui tutti i
processi che contiene. Nel job entrano i comandi avviati da questo modulo e i
processi che essi avviano a loro volta, compreso il server ADB.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _no_window_kwargs() -> dict:
    """Su Windows evita che ogni chiamata ad adb apra una finestra nera."""
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


# Calcolato una volta sola: Popen copia lo STARTUPINFO a ogni avvio.
_NO_WINDOW = _no_window_kwargs()


# --------------------------------------------------------------- job di Windows

_KILL_ON_JOB_CLOSE = 0x2000
_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_AF_INET = 2
_TCP_TABLE_OWNER_PID_LISTENER = 3

_job = None  # handle del job; None dove i job non esistono o non si riesce a crearne uno

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _TcpListener(ctypes.Structure):
        _fields_ = [
            ("dwState", wintypes.DWORD),
            ("dwLocalAddr", wintypes.DWORD),
            ("dwLocalPort", wintypes.DWORD),
            ("dwRemoteAddr", wintypes.DWORD),
            ("dwRemotePort", wintypes.DWORD),
            ("dwOwningPid", wintypes.DWORD),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    _iphlpapi = ctypes.WinDLL("iphlpapi")
    _iphlpapi.GetExtendedTcpTable.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
        wintypes.ULONG, ctypes.c_int, wintypes.ULONG,
    ]
    _iphlpapi.GetExtendedTcpTable.restype = wintypes.DWORD

    def _set_kill_on_close(enabled: bool) -> bool:
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE if enabled else 0
        return bool(
            _kernel32.SetInformationJobObject(
                _job, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
            )
        )

    # L'handle non viene mai chiuso da noi: lo chiude il sistema quando il processo
    # finisce, ed e' proprio quel momento a far terminare i processi del job.
    _job = _kernel32.CreateJobObjectW(None, None) or None
    if _job is not None and not _set_kill_on_close(True):
        _kernel32.CloseHandle(_job)
        _job = None


def adopt(pid: int) -> bool:
    """Lega il processo `pid` alla vita dell'applicazione; True se e' entrato nel job.

    Chi e' nel job vi porta anche i processi che avvia in seguito.
    """
    if _job is None:
        return False
    handle = _kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        return bool(_kernel32.AssignProcessToJobObject(_job, handle))
    finally:
        _kernel32.CloseHandle(handle)


def _image_name(pid: int) -> str:
    """Nome del file eseguibile del processo, in minuscolo ("" se non leggibile)."""
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name.lower()
    finally:
        _kernel32.CloseHandle(handle)


def _listener_pid(port: int) -> int:
    """Processo in ascolto sulla porta TCP locale `port` (0 se nessuno)."""
    size = wintypes.DWORD(0)
    _iphlpapi.GetExtendedTcpTable(
        None, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0
    )
    buffer = ctypes.create_string_buffer(max(size.value, ctypes.sizeof(wintypes.DWORD)))
    if _iphlpapi.GetExtendedTcpTable(
        buffer, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0
    ):
        return 0  # tabella cambiata nel frattempo: si riprovera' alla prossima occasione
    count = wintypes.DWORD.from_buffer(buffer).value
    rows = (_TcpListener * count).from_buffer(buffer, ctypes.sizeof(wintypes.DWORD))
    for row in rows:
        # La porta e' in ordine di rete nei due byte bassi.
        if ((row.dwLocalPort & 0xFF) << 8 | (row.dwLocalPort >> 8) & 0xFF) == port:
            return int(row.dwOwningPid)
    return 0


def adopt_listener(port: int, image_name: str) -> bool:
    """Lega all'applicazione il programma in ascolto sulla porta TCP locale `port`.

    Serve per un server ADB che era gia' in esecuzione: non l'abbiamo avviato
    noi, quindi nel job non c'e'. `image_name` (es. "adb.exe") evita di prendere
    un programma diverso che usasse la stessa porta.
    """
    if _job is None:
        return False
    try:
        pid = _listener_pid(port)
    except (OSError, ValueError):
        return False
    if not pid or _image_name(pid) != image_name.lower():
        return False
    return adopt(pid)


def keep_children_on_exit() -> None:
    """Scioglie il legame: i processi ancora vivi sopravvivono alla chiusura.

    Va chiamata solo in una chiusura ordinata, quando si e' scelto di lasciare
    attivo il server ADB e tutto il resto e' gia' stato fermato.
    """
    if _job is not None:
        _set_kill_on_close(False)


# ------------------------------------------------------------- avvio comandi


def _capture(argv: list[str], timeout: float, env: dict | None, **text) -> subprocess.CompletedProcess:
    """Come subprocess.run con cattura dell'output, con in piu' l'ingresso nel job."""
    with subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        **text,
        **_NO_WINDOW,
    ) as proc:
        adopt(proc.pid)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            exc.stdout, exc.stderr = proc.communicate()
            raise
        except BaseException:
            proc.kill()
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def run(argv: list[str], timeout: float = 20.0, env: dict | None = None) -> subprocess.CompletedProcess:
    """Esegue un comando raccogliendo stdout/stderr come testo."""
    return _capture(argv, timeout, env, text=True, encoding="utf-8", errors="replace")


def run_binary(argv: list[str], timeout: float = 60.0, env: dict | None = None) -> subprocess.CompletedProcess:
    """Come run(), ma restituisce stdout in byte grezzi (per gli screenshot PNG)."""
    return _capture(argv, timeout, env)


def popen(argv: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.Popen:
    """Avvia un processo a lunga durata (scrcpy, scrcpy-server) senza console.

    stdout e stderr confluiscono in un'unica pipe che il chiamante deve leggere:
    una pipe mai svuotata, una volta piena, blocca il processo figlio.
    """
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **_NO_WINDOW,
    )
    adopt(proc.pid)
    return proc


def spawn_detached(argv: list[str], env: dict | None = None) -> None:
    """Lancia un comando senza attenderne l'esito."""
    try:
        proc = subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_NO_WINDOW,
        )
    except OSError:
        return
    adopt(proc.pid)
