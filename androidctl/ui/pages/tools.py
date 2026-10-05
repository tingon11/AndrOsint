# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Pagina Strumenti: ADB e scrcpy locali, impostazioni e registro."""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from ... import tools
from ...i18n import tr
from ...paths import APP_DIR
from .. import theme
from ..widgets import Card, button, note
from .base import Page


class ToolsPage(Page):
    def build(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.grid_rowconfigure(2, weight=1)

        self._installing = False

        self._build_tools()
        self._build_mirror()
        self._build_general()
        self._build_log()
        self.refresh_tools()

    # ------------------------------------------------------------ costruzione

    def _build_tools(self) -> None:
        card = Card(self, tr("Local tools (tools/ folder)"), self.fonts)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, theme.GAP))
        body = card.body
        body.grid_columnconfigure(1, weight=1)

        self.tool_labels = {}
        for row, (key, label) in enumerate((("adb", "ADB"), ("scrcpy", "scrcpy"))):
            ctk.CTkLabel(body, text=label, font=self.fonts.bold, anchor="w", width=60).grid(
                row=row, column=0, sticky="w"
            )
            self.tool_labels[key] = ctk.CTkLabel(body, text="-", font=self.fonts.body, anchor="w")
            self.tool_labels[key].grid(row=row, column=1, sticky="ew")

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(theme.GAP, 0))
        buttons.grid_columnconfigure((0, 1, 2), weight=1)
        button(buttons, tr("Check"), self.refresh_tools, width=70).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        button(buttons, tr("Download / Update"), lambda: self.install_tools(None), width=120).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        button(buttons, tr("Restart ADB"), self._restart_adb, width=90).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        self.progress = ctk.CTkProgressBar(body, height=8)
        self.progress.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(theme.PAD, 0))
        self.progress.set(0)

    def _build_mirror(self) -> None:
        config = self.app.config_store
        card = Card(self, "Mirroring", self.fonts)
        card.grid(row=0, column=1, sticky="nsew")
        body = card.body
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="field")

        fields = (
            ("mirror_max_size", tr("Max resolution (px)"), self._as_int(1024)),
            ("mirror_bitrate", tr("Video bitrate"), lambda value: value.strip() or "4M"),
            ("mirror_max_fps", tr("Max FPS"), self._as_int(30)),
        )
        for column, (key, label, convert) in enumerate(fields):
            note(body, label, self.fonts).grid(row=0, column=column, sticky="w")
            var = ctk.StringVar(value=str(config.get(key)))
            var.trace_add("write", lambda *_a, k=key, v=var, c=convert: config.set(k, c(v.get())))
            ctk.CTkEntry(body, textvariable=var, height=30).grid(
                row=1, column=column, sticky="ew", padx=(0, 0 if column == 2 else theme.GAP)
            )

        switches = (
            ("mirror_stay_awake", tr("Keep the phone awake")),
            ("mirror_turn_screen_off", tr("Turn the phone screen off")),
            ("mirror_always_on_top", tr("Window always on top")),
        )
        for row, (key, label) in enumerate(switches, start=2):
            self._switch(body, key, label).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(theme.GAP if row == 2 else 3, 0)
            )

    def _build_general(self) -> None:
        config = self.app.config_store
        card = Card(self, tr("General"), self.fonts)
        card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(theme.GAP, 0))
        body = card.body
        body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(body, text=tr("Screenshot folder"), font=self.fonts.body, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, theme.PAD)
        )
        self.shot_dir_var = ctk.StringVar(value=str(config.get("screenshot_dir")))
        ctk.CTkEntry(body, textvariable=self.shot_dir_var, state="readonly", height=30).grid(
            row=0, column=1, sticky="ew"
        )
        button(body, tr("Browse…"), self._choose_screenshot_dir, width=90).grid(
            row=0, column=2, padx=(theme.GAP, 0)
        )

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(theme.GAP + 2, 0))
        self._switch(
            row, "fast_control", tr("Fast control (instant keys and clipboard)"),
            command=self.app.apply_fast_control,
        ).grid(row=0, column=0, sticky="w", padx=(0, 24))
        self._switch(row, "kill_adb_on_exit", tr("Stop the ADB server on exit")).grid(
            row=0, column=1, sticky="w"
        )

    def _build_log(self) -> None:
        card = Card(self, tr("Log"), self.fonts)
        card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(theme.GAP, 0))
        card.body.grid_columnconfigure(0, weight=1)
        card.body.grid_rowconfigure(0, weight=1)
        self.log_text = ctk.CTkTextbox(card.body, height=80, wrap="word", font=self.fonts.mono)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        if self.app.log_lines:
            self.log_text.insert("end", "\n".join(self.app.log_lines) + "\n")
            self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _switch(self, parent, key: str, label: str, command=None) -> ctk.CTkSwitch:
        """Interruttore legato a un'impostazione: la scelta vale subito."""
        config = self.app.config_store
        var = ctk.BooleanVar(value=bool(config.get(key)))

        def changed() -> None:
            config.set(key, var.get())
            if command is not None:
                command()

        return ctk.CTkSwitch(parent, text=label, variable=var, command=changed, font=self.fonts.body)

    @staticmethod
    def _as_int(fallback: int):
        def convert(value: str) -> int:
            try:
                return max(0, int(value.strip()))
            except ValueError:
                return fallback

        return convert

    # -------------------------------------------------------------- registro

    def append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------- strumenti

    def refresh_tools(self) -> None:
        app = self.app
        state = tools.status()
        for key, info in state.items():
            if info.present and info.path is not None:
                try:
                    shown = info.path.relative_to(APP_DIR)
                except ValueError:
                    shown = info.path
                self.tool_labels[key].configure(text=f"OK  ·  {shown}", text_color=theme.OK)
            else:
                self.tool_labels[key].configure(text=tr("Missing"), text_color=theme.ERROR)
        app.adb.refresh_path()
        app.log(tr("Tools check: ") + ", ".join(f"{k}={v.text}" for k, v in state.items()))
        if any(info.present for info in state.values()):
            app.tasks.run(self._read_versions, self._show_versions, lambda _exc: None)

    def _read_versions(self) -> dict[str, str]:
        """Legge le versioni degli eseguibili (in background: sono chiamate a processi)."""
        app = self.app
        versions = {}
        if app.adb.available:
            versions["adb"] = app.adb.version()
        if app.scrcpy.available:
            versions["scrcpy"] = app.scrcpy.version_string()
        return versions

    def _show_versions(self, versions: dict[str, str]) -> None:
        for key, version in versions.items():
            label = self.tool_labels[key]
            current = label.cget("text")
            if version and current.startswith("OK") and "(v" not in current:
                label.configure(text=f"{current}  (v{version})")

    def install_tools(self, keys: list[str] | None) -> None:
        app = self.app
        targets = keys if keys is not None else ["adb", "scrcpy"]
        if not targets or self._installing:
            return
        self._installing = True
        # adb.exe e scrcpy.exe in esecuzione impedirebbero di sostituire le cartelle.
        app.suspend_adb()
        app.status(tr("Downloading tools…"))
        self.progress.set(0)

        last = [-1]

        def progress(label: str, done: int, total: int) -> None:
            percent = done * 100 // total if total > 0 else -1
            if percent != last[0] or total <= 0:
                last[0] = percent
                app.tasks.post(self._progress, label, done, total)

        def job() -> list[str]:
            if app.adb.available:
                app.adb.kill_server()
            return tools.install(targets, progress)

        def finish() -> None:
            self._installing = False
            app.resume_adb()
            self.refresh_tools()

        def done(messages: list[str]) -> None:
            self.progress.set(1)
            for message in messages:
                app.log(message)
            finish()
            app.status(tr("Tools ready."))

        def failed(exc: BaseException) -> None:
            self.progress.set(0)
            finish()
            app.error(tr("Tools download"), exc)

        app.tasks.run(job, done, failed)

    def _progress(self, label: str, done: int, total: int) -> None:
        if total > 0:
            self.progress.set(done / total)
            self.app.status(f"{label}: {done // 1024} / {total // 1024} KB")
        else:
            self.app.status(f"{label}…")

    def _restart_adb(self) -> None:
        app = self.app
        if not app.adb.available:
            app.error("ADB", tr("adb.exe is not in tools/."))
            return
        app.status(tr("Restarting the ADB server…"))
        # Il server viene riavviato da solo dal thread che segue i dispositivi.
        app.tasks.run(
            app.adb.kill_server,
            lambda _r: (app.log(tr("ADB server restarted.")), app.status(tr("ADB server restarted."))),
        )

    # ---------------------------------------------------------- impostazioni

    def _choose_screenshot_dir(self) -> None:
        folder = filedialog.askdirectory(
            title=tr("Folder for screenshots"),
            initialdir=self.shot_dir_var.get() or str(APP_DIR),
            parent=self.app,
        )
        if folder:
            self.shot_dir_var.set(folder)
            self.app.config_store.set("screenshot_dir", folder)
