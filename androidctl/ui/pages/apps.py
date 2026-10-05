# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Pagina App: elenco delle applicazioni installate, avvio, chiusura, disinstallazione."""

from __future__ import annotations

import threading
from pathlib import Path

import customtkinter as ctk

from ... import installer
from ...adb import AppInfo, Device
from ...i18n import tr
from ...library import Entry
from .. import theme
from ..dialogs import messagebox
from ..widgets import Table, button, follow_width, note
from .base import Page

FILTER_DELAY_MS = 120  # attende una pausa nella digitazione prima di ridisegnare l'elenco


class AppsPage(Page):
    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.all_apps: list[AppInfo] = []
        self._loaded_for = ""  # seriale per cui l'elenco e' valido
        self._loading = False
        self._filter_job: str | None = None
        self._saved: dict[str, list[str]] = {}  # package -> versioni salvate nel PC
        self._scanning_saved = False

        bar = ctk.CTkFrame(self, border_width=1, border_color=theme.BORDER)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        # Senza textvariable: con una variabile collegata il segnaposto non compare.
        self.search = ctk.CTkEntry(bar, placeholder_text=tr("Search by name or package…"), height=32)
        self.search.grid(row=0, column=0, sticky="ew", padx=(theme.PAD, theme.GAP), pady=theme.PAD)
        self.search.bind("<KeyRelease>", lambda _e: self._schedule_filter())

        self.system_var = ctk.BooleanVar(value=bool(self.app.config_store.get("show_system_apps")))
        ctk.CTkSwitch(
            bar, text=tr("System apps"), variable=self.system_var, command=self._reload,
            font=self.fonts.body,
        ).grid(row=0, column=1, padx=theme.GAP)
        button(bar, tr("Refresh list"), self._reload, width=130).grid(
            row=0, column=2, padx=(theme.GAP, theme.PAD)
        )

        self.table = Table(
            self,
            columns=[
                ("name", tr("Name"), 180, True),
                ("package", "Package", 260, True),
                ("version", tr("Version"), 100, True),
                ("launch", tr("Launchable"), 88, False),
                ("saved", tr("Saved on PC"), 150, True),
            ],
            tags={"saved": theme.OK, "stale": theme.WARN},
        )
        self.table.grid(row=1, column=0, sticky="nsew", pady=(theme.GAP, 0))
        self.table.tree.bind("<Double-1>", lambda _e: self._open())
        self.table.tree.bind("<Return>", lambda _e: self._open())

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(theme.GAP, 0))
        footer.grid_columnconfigure(4, weight=1)
        button(footer, tr("Open"), self._open, primary=True, width=100).grid(row=0, column=0)
        button(footer, tr("Close"), self._close, width=100).grid(row=0, column=1, padx=theme.GAP)
        button(footer, tr("Uninstall"), self._uninstall, width=100, danger=True).grid(row=0, column=2)
        button(footer, tr("Extract APK"), self._export, width=110).grid(row=0, column=3, padx=theme.GAP)
        self.count_label = note(footer, "", self.fonts)
        self.count_label.grid(row=0, column=4, sticky="e")

        hint = note(
            self,
            tr(
                "“Extract APK” copies the app's package (APK, splits and OBB data) to the PC, "
                "into the folder of the Install APK page, from which it can be reinstalled on "
                "another phone. The “Saved on PC” column shows which apps are already there: green "
                "for the same version as the phone, orange for a different one. Names in brackets "
                "are derived from the package: the phone exposes no name for apps without an icon."
            ),
            self.fonts,
        )
        hint.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        follow_width(hint, self)

    # -- ciclo di vita -------------------------------------------------------

    def on_show(self) -> None:
        device = self.app.current
        if device is not None and device.ready and self._loaded_for != device.serial:
            self._load(device)
        else:
            self._refresh_saved()

    def on_device(self, device: Device | None) -> None:
        if device is not None and device.serial == self._loaded_for:
            return
        self._clear()
        if device is not None and self.winfo_ismapped():
            self._load(device)

    def _clear(self) -> None:
        self.all_apps = []
        self._loaded_for = ""
        self.table.clear()
        self.count_label.configure(text="")

    def retranslate(self) -> None:
        # «sì» e la colonna «Salvata nel PC» sono testi delle righe: si ridisegnano.
        if self.all_apps:
            self._apply_filter()

    # -- elenco --------------------------------------------------------------

    def _reload(self) -> None:
        self.app.config_store.set("show_system_apps", self.system_var.get())
        device = self.app.require_device()
        if device is not None:
            self._load(device, refresh_labels=True)

    def _load(self, device: Device, refresh_labels: bool = False) -> None:
        if self._loading:
            return
        app = self.app
        serial = device.serial
        include_system = self.system_var.get()
        self._loading = True
        app.status(tr("Reading the installed applications and their names…"))

        def job() -> list[AppInfo]:
            # I nomi visibili arrivano da scrcpy-server e costano qualche secondo:
            # si leggono in parallelo all'elenco dei pacchetti.
            labels: dict[str, dict[str, str]] = {}
            reader = threading.Thread(
                target=lambda: labels.update(found=app.app_labels(serial, refresh=refresh_labels)),
                daemon=True,
            )
            reader.start()
            apps = app.adb.list_apps(serial, include_system)
            versions = app.adb.package_versions(serial)
            saved = app.library.by_package(app.library.scan(app.packages_dir()))
            reader.join()
            for info in apps:
                info.apply_labels(labels.get("found", {}))
                info.version = versions.get(info.package, "")
            apps.sort(key=lambda a: (not a.labelled, a.name.lower()))
            return apps, {pkg: [e.info.version for e in entries] for pkg, entries in saved.items()}

        def ok(result) -> None:
            apps, saved = result
            self._loading = False
            if app.current is None or app.current.serial != serial:
                return
            self.all_apps = apps
            self._loaded_for = serial
            self._saved = saved
            self._apply_filter()
            named = sum(1 for a in apps if a.labelled)
            app.status(
                tr("{count} applications found, {named} with a visible name.").format(
                    count=len(apps), named=named
                )
            )

        def failed(exc: BaseException) -> None:
            self._loading = False
            app.error(tr("Application list"), exc)

        app.tasks.run(job, ok, failed)

    def _schedule_filter(self) -> None:
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(FILTER_DELAY_MS, self._apply_filter)

    def _apply_filter(self) -> None:
        self._filter_job = None
        needle = self.search.get().strip().lower()
        tree = self.table.tree
        selected = tree.selection()
        self.table.clear()
        shown = 0
        for app in self.all_apps:
            if needle and needle not in app.name.lower() and needle not in app.package.lower():
                continue
            saved, tag = self._saved_state(app)
            tree.insert(
                "", "end", iid=app.package,
                values=(
                    app.name if app.labelled else f"({app.name})",
                    app.package,
                    app.version,
                    tr("yes") if app.launchable else "-",
                    saved,
                ),
                tags=(tag,) if tag else (),
            )
            shown += 1
        if selected and tree.exists(selected[0]):
            tree.selection_set(selected[0])
        total_saved = sum(1 for a in self.all_apps if a.package in self._saved)
        self.count_label.configure(
            text=tr("{shown} of {total} apps  ·  {saved} saved on PC").format(
                shown=shown, total=len(self.all_apps), saved=total_saved
            )
        )

    def _saved_state(self, app: AppInfo) -> tuple[str, str]:
        """Testo e colore della colonna «Salvata nel PC» per un'app."""
        versions = self._saved.get(app.package)
        if not versions:
            return "", ""
        if app.version and app.version in versions:
            return f"✔  {app.version}", "saved"
        shown = ", ".join(dict.fromkeys(v or "?" for v in versions))
        text = tr("✔  {saved} (phone: {phone})").format(saved=shown, phone=app.version or "?")
        return text, "stale"

    # -- pacchetti salvati ---------------------------------------------------

    def _refresh_saved(self) -> None:
        """Rilegge la cartella dei pacchetti e aggiorna la colonna «Salvata nel PC»."""
        if self._scanning_saved or not self.all_apps:
            return
        self._scanning_saved = True
        app = self.app
        folder = app.packages_dir()

        def ok(entries: list[Entry]) -> None:
            self._scanning_saved = False
            self.saved_changed(entries)

        def failed(_exc: BaseException) -> None:
            self._scanning_saved = False

        app.tasks.run(lambda: app.library.scan(folder), ok, failed)

    def saved_changed(self, entries: list[Entry]) -> None:
        """La pagina Installa APK ha riletto la cartella: si aggiorna la colonna."""
        saved = {
            pkg: [e.info.version for e in group]
            for pkg, group in self.app.library.by_package(e for e in entries if e.watched).items()
        }
        if saved == self._saved:
            return
        self._saved = saved
        tree = self.table.tree
        for info in self.all_apps:
            if tree.exists(info.package):
                text, tag = self._saved_state(info)
                values = list(tree.item(info.package, "values"))
                values[4] = text
                tree.item(info.package, values=values, tags=(tag,) if tag else ())
        total_saved = sum(1 for a in self.all_apps if a.package in self._saved)
        shown = len(tree.get_children())
        self.count_label.configure(
            text=tr("{shown} of {total} apps  ·  {saved} saved on PC").format(
                shown=shown, total=len(self.all_apps), saved=total_saved
            )
        )

    def _selected(self) -> AppInfo | None:
        selection = self.table.tree.selection()
        if not selection:
            self.app.status(tr("Select an application from the list."))
            return None
        return next((a for a in self.all_apps if a.package == selection[0]), None)

    # -- azioni --------------------------------------------------------------

    def _open(self) -> None:
        app = self.app
        device = app.require_device()
        info = self._selected() if device is not None else None
        if info is None:
            return
        serial = device.serial
        app.status(tr("Starting {package}…").format(package=info.package))
        app.tasks.run(
            lambda: app.adb.launch_app(serial, info),
            lambda _r: app.status(tr("Started: {package}").format(package=info.package)),
            lambda exc: app.error(tr("Starting application"), exc),
        )

    def _close(self) -> None:
        app = self.app
        device = app.require_device()
        info = self._selected() if device is not None else None
        if info is None:
            return
        serial = device.serial
        app.status(tr("Closing {package}…").format(package=info.package))
        app.tasks.run(
            lambda: app.adb.stop_app(serial, info.package),
            lambda _r: app.status(tr("Closed: {package}").format(package=info.package)),
            lambda exc: app.error(tr("Closing application"), exc),
        )

    def _uninstall(self) -> None:
        app = self.app
        device = app.require_device()
        info = self._selected() if device is not None else None
        if info is None:
            return
        confirmed = messagebox.askyesno(
            tr("Uninstall application"),
            tr(
                "Uninstall {name} from the phone?\n\n{package}\n\n"
                "The application's data will be deleted."
            ).format(name=info.label, package=info.package),
            icon="warning",
            default="no",
            parent=app,
        )
        if not confirmed:
            return
        serial = device.serial

        def ok(_result) -> None:
            self.all_apps = [a for a in self.all_apps if a.package != info.package]
            app.forget_labels(serial)
            self._apply_filter()
            app.status(tr("Uninstalled: {name}").format(name=info.label))
            app.log(tr("Uninstalled {package}").format(package=info.package))

        app.status(tr("Uninstalling {package}…").format(package=info.package))
        app.tasks.run(
            lambda: app.adb.uninstall(serial, info.package),
            ok,
            lambda exc: app.error(tr("Uninstallation"), exc),
        )

    def _export(self) -> None:
        """Copia sul PC gli APK dell'app selezionata, pronti per un altro telefono."""
        app = self.app
        device = app.require_device()
        info = self._selected() if device is not None else None
        if info is None:
            return
        serial = device.serial
        folder = Path(str(app.config_store.get("packages_dir")))

        def job() -> Path:
            return installer.export(
                app.adb, serial, info.package, folder,
                label=info.name if info.labelled else "",
                status=lambda text: app.tasks.post(app.status, f"{info.label}: {text}"),
            )

        def ok(target: Path) -> None:
            install_page = app.pages.get("install")
            if install_page is not None:
                install_page.note_exported(target)
            self._refresh_saved()
            size = installer.human_size(target.stat().st_size)
            app.status(
                tr("{name} extracted to {file} ({size}): you will find it on the Install APK page.").format(
                    name=info.label, file=target.name, size=size
                )
            )
            app.log(tr("Extracted {package} -> {path}").format(package=info.package, path=target))

        def failed(exc: BaseException) -> None:
            app.error(tr("Extraction of {name}").format(name=info.label), exc)

        app.status(tr("Extracting {name}…").format(name=info.label))
        # Una estrazione alla volta: ogni file passa dallo stesso cavo USB.
        app.tasks.run(job, ok, failed, lane="export")

    def invalidate(self) -> None:
        """L'elenco non e' piu' aggiornato (es. dopo un'installazione)."""
        self.app.forget_labels(self._loaded_for)
        self._loaded_for = ""
