# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Pagina Installa APK: installa sul telefono i pacchetti scaricati sul PC."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ... import apkinfo, installer
from ...adb import Device
from ...i18n import N_, again, tr
from ...library import Entry
from ...paths import APP_DIR
from .. import theme
from ..widgets import Card, Table, button, follow_width, link, note
from .base import Page

WATCH_MS = 2500

# Dove procurarsi i pacchetti: siti che pubblicano gli APK originali, firmati
# dallo sviluppatore.
SOURCES = (
    ("APKMirror", "https://www.apkmirror.com/"),
    ("F-Droid", "https://f-droid.org/"),
    ("APKPure", "https://apkpure.com/"),
)

WAITING = N_("Waiting")


@dataclass
class Row:
    path: Path
    size: int
    info: apkinfo.ApkInfo
    state: str = ""
    tag: str = ""
    mark: str = ""  # segno davanti all'esito: ✔ oppure ✖
    busy: bool = False


class InstallPage(Page):
    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.rows: dict[str, Row] = {}
        self.extra: list[Path] = []  # file aggiunti a mano, fuori dalla cartella
        self._profiles: dict[str, installer.Profile] = {}
        self._scanning = False
        self._closed = False
        self._total = 0
        self._finished = 0
        self._failed = 0

        # Sorveglianza della cartella: pacchetti gia' visti e dimensioni in osservazione.
        self._auto_prime = True
        self._auto_seen: set[str] = set()
        self._auto_sizes: dict[str, int] = {}

        self._build_folder()
        self._build_table()
        self._build_actions()
        self._build_sources()

        self.after(WATCH_MS, self._watch_tick)

    # ------------------------------------------------------------ costruzione

    def _build_folder(self) -> None:
        config = self.app.config_store
        card = Card(self, tr("Packages folder"), self.fonts)
        card.grid(row=0, column=0, sticky="ew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)

        self.folder_var = ctk.StringVar(value=str(config.get("packages_dir")))
        ctk.CTkEntry(body, textvariable=self.folder_var, state="readonly", height=32).grid(
            row=0, column=0, sticky="ew"
        )
        button(body, tr("Browse…"), self._choose_folder, width=90).grid(row=0, column=1, padx=theme.GAP)
        button(body, tr("Open folder"), self._open_folder, width=110).grid(row=0, column=2)

        options = ctk.CTkFrame(body, fg_color="transparent")
        options.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(theme.GAP + 2, 0))
        self.option_vars = {}
        for column, (key, label) in enumerate(
            (
                ("install_replace", tr("Update if already installed")),
                ("install_downgrade", tr("Allow older version")),
                ("install_grant", tr("Grant permissions right away")),
            )
        ):
            var = self.option_vars[key] = ctk.BooleanVar(value=bool(config.get(key)))
            ctk.CTkCheckBox(
                options, text=label, variable=var, font=self.fonts.body,
                checkbox_width=20, checkbox_height=20,
                command=lambda k=key, v=var: config.set(k, v.get()),
            ).grid(row=0, column=column, sticky="w", padx=(0, 18))

        self.auto_var = ctk.BooleanVar(value=bool(config.get("install_auto")))
        ctk.CTkSwitch(
            body,
            text=tr("Automatically install new packages saved in this folder"),
            variable=self.auto_var,
            command=self._toggle_auto,
            font=self.fonts.body,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(theme.GAP + 2, 0))

    def _build_table(self) -> None:
        self.table = Table(
            self,
            columns=[
                ("app", "App", 190, True),
                ("file", tr("Package"), 220, True),
                ("kind", tr("Type"), 60, False),
                ("size", tr("Size"), 92, False),
                ("state", tr("Status"), 260, True),
            ],
            selectmode="extended",
            tags={"ok": theme.OK, "error": theme.ERROR, "busy": theme.ACCENT},
        )
        self.table.grid(row=1, column=0, sticky="nsew", pady=(theme.GAP, 0))
        self.table.tree.bind("<Double-1>", lambda _e: self._install_selected())
        self.table.tree.bind("<<TreeviewSelect>>", self._show_selected_state)

    def _build_actions(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(theme.GAP, 0))
        bar.grid_columnconfigure(4, weight=1)
        button(bar, tr("Install selected"), self._install_selected, primary=True, width=145).grid(
            row=0, column=0
        )
        button(bar, tr("Install all"), self._install_all, width=100).grid(row=0, column=1, padx=theme.GAP)
        button(bar, tr("Add files…"), self._add_files, width=110).grid(row=0, column=2)
        button(bar, tr("Refresh"), self.refresh, width=84).grid(row=0, column=3, padx=theme.GAP)
        self.count_label = note(bar, "", self.fonts)
        self.count_label.grid(row=0, column=4, sticky="e", padx=theme.GAP)
        self.progress = ctk.CTkProgressBar(bar, width=100, height=8)
        self.progress.grid(row=0, column=5)
        self.progress.set(0)

    def _build_sources(self) -> None:
        box = ctk.CTkFrame(self, border_width=1, border_color=theme.BORDER)
        box.grid(row=3, column=0, sticky="ew", pady=(theme.GAP, 0))
        box.grid_columnconfigure(len(SOURCES) + 1, weight=1)
        ctk.CTkLabel(box, text=tr("Where to download packages:"), font=self.fonts.bold).grid(
            row=0, column=0, padx=(theme.PAD, 4), pady=(theme.GAP, 0)
        )
        for column, (name, url) in enumerate(SOURCES, start=1):
            link(box, name, lambda u=url: webbrowser.open(u)).grid(
                row=0, column=column, padx=2, pady=(theme.GAP, 0), sticky="w"
            )
        hint = note(
            box,
            tr(
                "Save .apk, .apks, .xapk or .apkm files in the folder above. When available, "
                "prefer the app's official site and the arm64-v8a variant. Packages extracted from "
                "a phone with “Extract APK” (Apps page) also land here, ready to be reinstalled "
                "on another one."
            ),
            self.fonts,
        )
        hint.grid(
            row=1, column=0, columnspan=len(SOURCES) + 2, sticky="ew",
            padx=theme.PAD, pady=(2, theme.GAP),
        )
        follow_width(hint, box, margin=2 * theme.PAD)

    # ------------------------------------------------------------- cartella

    def _folder(self) -> Path:
        return Path(str(self.app.config_store.get("packages_dir")))

    def _choose_folder(self) -> None:
        current = self._folder()
        folder = filedialog.askdirectory(
            title=tr("Folder of the downloaded packages"),
            initialdir=str(current if current.is_dir() else APP_DIR),
            parent=self.app,
        )
        if not folder:
            return
        self.app.config_store.set("packages_dir", folder)
        self.folder_var.set(folder)
        # Cartella nuova: quello che contiene gia' non va installato da solo.
        self._auto_prime = True
        self.refresh()

    def _open_folder(self) -> None:
        folder = self._folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))  # noqa: S606 - apre Esplora risorse
        except (OSError, AttributeError) as exc:
            self.app.error(tr("Opening folder"), exc)

    def _add_files(self) -> None:
        patterns = " ".join(f"*{suffix}" for suffix in installer.KINDS)
        chosen = filedialog.askopenfilenames(
            title=tr("Packages to install"),
            filetypes=[(tr("Android packages"), patterns), (tr("All files"), "*.*")],
            parent=self.app,
        )
        added = 0
        for name in chosen:
            path = Path(name)
            if installer.is_package(path) and path not in self.extra and str(path) not in self.rows:
                self.extra.append(path)
                added += 1
        if added:
            self.refresh()
        elif chosen:
            self.app.status(tr("No new package among the chosen files."))

    # --------------------------------------------------------------- elenco

    def on_show(self) -> None:
        self.refresh()

    def on_close(self) -> None:
        self._closed = True

    def on_device(self, device: Device | None) -> None:
        if device is None:
            self._profiles.clear()

    def retranslate(self) -> None:
        """Ritraduce lo stato delle righe; un esito composto resta nella lingua in cui e' nato."""
        for key, row in self.rows.items():
            row.state = again(row.state)
            self._redraw_row(key)

    def refresh(self) -> None:
        """Rilegge la cartella in background e aggiorna la tabella."""
        if self._scanning:
            return
        self._scanning = True
        folder = self._folder()
        extra = list(self.extra)

        library = self.app.library

        def job() -> list[Entry]:
            return library.scan(folder, extra)

        def ok(entries: list[Entry]) -> None:
            self._scanning = False
            self._merge(entries)
            self._auto_check([(e.path, e.size, e.watched) for e in entries])
            apps = self.app.pages.get("apps")
            if apps is not None:
                apps.saved_changed(entries)

        def failed(_exc: BaseException) -> None:
            self._scanning = False

        self.app.tasks.run(job, ok, failed)

    def _merge(self, entries: list[Entry]) -> None:
        """Allinea la tabella ai file trovati, conservando lo stato di quelli gia' noti."""
        tree = self.table.tree
        present = set()
        for position, entry in enumerate(entries):
            path, size, info = entry.path, entry.size, entry.info
            key = str(path)
            present.add(key)
            row = self.rows.get(key)
            if row is None:
                row = self.rows[key] = Row(path=path, size=size, info=info, state=tr(WAITING))
                tree.insert("", position, iid=key, values=self._values(row))
            elif row.size != size or row.info != info:
                if row.size != size and not row.busy:
                    # File sostituito: l'esito precedente non vale piu'.
                    row.state, row.tag, row.mark = tr(WAITING), "", ""
                row.size, row.info = size, info
                self._redraw_row(key)
        for key in [k for k, row in self.rows.items() if k not in present and not row.busy]:
            del self.rows[key]
            if tree.exists(key):
                tree.delete(key)
        self.extra = [p for p in self.extra if str(p) in present]
        if not self._total:
            self.count_label.configure(
                text=tr("{count} packages").format(count=len(self.rows))
                if self.rows
                else tr("No package in the folder")
            )

    @staticmethod
    def _values(row: Row) -> tuple[str, str, str, str, str]:
        return (
            row.info.title or (tr("(name not readable)") if row.size else ""),
            row.path.name,
            installer.kind_of(row.path),
            installer.human_size(row.size),
            f"{row.mark}{row.state}",
        )

    @staticmethod
    def _name(row: Row) -> str:
        """Come chiamare il pacchetto nei messaggi: nome dell'app se noto."""
        return row.info.title or row.path.name

    def _redraw_row(self, key: str) -> None:
        row = self.rows.get(key)
        if row is not None and self.table.tree.exists(key):
            self.table.tree.item(key, values=self._values(row), tags=(row.tag,) if row.tag else ())

    def _set_state(self, key: str, state: str, tag: str, mark: str = "") -> None:
        row = self.rows.get(key)
        if row is not None:
            row.state, row.tag, row.mark = state, tag, mark
            self._redraw_row(key)

    def _show_selected_state(self, _event=None) -> None:
        """Riporta per intero nella barra di stato l'esito della riga scelta."""
        selection = self.table.tree.selection()
        row = self.rows.get(selection[0]) if len(selection) == 1 else None
        if row is not None and row.tag in ("ok", "error"):
            self.app.status(f"{self._name(row)}: {row.state}")

    # --------------------------------------------------------- installazione

    def _install_selected(self) -> None:
        keys = list(self.table.tree.selection())
        if not keys:
            self.app.status(tr("Select one or more packages from the list."))
            return
        self._install(keys)

    def _install_all(self) -> None:
        keys = list(self.table.tree.get_children())
        if not keys:
            self.app.status(tr("No package to install: save one in the folder."))
            return
        self._install(keys)

    def _install(self, keys: list[str], automatic: bool = False) -> None:
        app = self.app
        if automatic:
            device = app.current if app.current is not None and app.current.ready else None
        else:
            device = app.require_device()
        if device is None:
            return
        serial = device.serial
        options = installer.Options(
            replace=self.option_vars["install_replace"].get(),
            downgrade=self.option_vars["install_downgrade"].get(),
            grant=self.option_vars["install_grant"].get(),
        )

        for key in keys:
            row = self.rows.get(key)
            if row is None or row.busy:
                continue
            row.busy = True
            self._set_state(key, tr("Queued"), "busy")
            self._total += 1
            self._queue(key, row, serial, options)
        self._show_progress()

    def _queue(self, key: str, row: Row, serial: str, options: installer.Options) -> None:
        app = self.app
        path, name = row.path, self._name(row)

        def report(text: str) -> None:
            app.tasks.post(self._set_state, key, text, "busy")

        def job() -> str:
            report(tr("Preparing…"))
            profile = self._profiles.get(serial)
            if profile is None:
                profile = self._profiles[serial] = installer.read_profile(app.adb, serial)
            return installer.install(app.adb, serial, path, options, profile, status=report)

        def ok(summary: str) -> None:
            self._done(key, summary, "ok", "✔  ")
            app.log(
                tr("Installed {name} ({file}): {summary}").format(
                    name=name, file=path.name, summary=summary
                )
            )
            apps = app.pages.get("apps")
            if apps is not None:
                apps.invalidate()

        def failed(exc: BaseException) -> None:
            self._failed += 1
            self._done(key, str(exc), "error", "✖  ")
            app.log(
                tr("Installation of {name} ({file}) failed: {error}").format(
                    name=name, file=path.name, error=exc
                )
            )

        # Una installazione alla volta: il telefono non ne gestisce di parallele.
        app.tasks.run(job, ok, failed, lane="install")

    def _done(self, key: str, state: str, tag: str, mark: str) -> None:
        row = self.rows.get(key)
        if row is not None:
            row.busy = False
        self._set_state(key, state, tag, mark)
        self._finished += 1
        self._show_progress()
        if self._finished >= self._total:
            good = self._finished - self._failed
            message = tr("Installation finished: {good} succeeded").format(good=good)
            if self._failed:
                message += tr(", {failed} failed (reason in the Status column)").format(
                    failed=self._failed
                )
            self.app.status(message + ".")
            self._total = self._finished = self._failed = 0

    def _show_progress(self) -> None:
        if not self._total:
            return
        self.progress.set(self._finished / self._total)
        self.count_label.configure(text=f"{self._finished} / {self._total}")
        if self._finished < self._total:
            self.app.status(
                tr("Installing: {done} of {total}…").format(done=self._finished, total=self._total)
            )

    # --------------------------------------------- installazione automatica

    def note_exported(self, path: Path) -> None:
        """Un pacchetto appena estratto dal telefono non va reinstallato da solo."""
        self._auto_seen.add(str(path))
        self.refresh()

    def _toggle_auto(self) -> None:
        enabled = self.auto_var.get()
        self.app.config_store.set("install_auto", enabled)
        if enabled:
            # I pacchetti gia' in cartella restano dove sono: partono solo i nuovi arrivi.
            self._auto_prime = True
            self.refresh()
            self.app.status(tr("Automatic installation enabled: save a package in the folder."))
        else:
            self.app.status(tr("Automatic installation disabled."))

    def _watch_tick(self) -> None:
        if self._closed:
            return
        self.after(WATCH_MS, self._watch_tick)
        if self.auto_var.get() or self.winfo_ismapped():
            self.refresh()

    def _auto_check(self, listed: list[tuple[Path, int, bool]]) -> None:
        """Avvia l'installazione dei pacchetti comparsi nella cartella dall'ultima lettura."""
        watched = {str(path): size for path, size, in_folder in listed if in_folder}
        if self._auto_prime:
            self._auto_prime = False
            self._auto_seen = set(watched)
            self._auto_sizes.clear()
            return
        if not self.auto_var.get():
            # Sorveglianza spenta: cio' che arriva adesso non partira' alla riaccensione.
            self._auto_seen.update(watched)
            return

        device = self.app.current
        ready = []
        for key, size in watched.items():
            if key in self._auto_seen:
                continue
            if size == 0 or self._auto_sizes.get(key) != size:
                # Download ancora in corso: si attende che la dimensione si fermi.
                self._auto_sizes[key] = size
                continue
            if device is None or not device.ready:
                continue  # si riprova quando il telefono e' collegato
            self._auto_seen.add(key)
            self._auto_sizes.pop(key, None)
            ready.append(key)
        if ready:
            names = ", ".join(Path(k).name for k in ready)
            self.app.log(tr("Automatic installation: {files}").format(files=names))
            self._install(ready, automatic=True)
