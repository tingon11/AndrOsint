# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Pagina Controllo: mirroring, tasti, appunti e screenshot."""

from __future__ import annotations

import datetime as dt
import io
import os
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from ... import remote, winclip
from ...adb import is_ascii
from ...i18n import N_, tr
from .. import theme
from ..dialogs import messagebox
from ..widgets import Card, button, follow_width, note
from .base import Page

KEYS = (
    (N_("Back"), remote.KEY_BACK),
    ("Home", remote.KEY_HOME),
    (N_("Recents"), remote.KEY_APP_SWITCH),
    (N_("Lock"), remote.KEY_POWER),
    ("Vol −", remote.KEY_VOLUME_DOWN),
    ("Vol +", remote.KEY_VOLUME_UP),
)

PREVIEW_MAX = 1400  # lato lungo dell'anteprima tenuta in memoria


class ControlPage(Page):
    def build(self) -> None:
        self.grid_columnconfigure(0, weight=3, uniform="col")
        self.grid_columnconfigure(1, weight=2, uniform="col")
        self.grid_rowconfigure(1, weight=1)

        self._preview: Image.Image | None = None
        self._last_png: bytes | None = None
        self._last_path: Path | None = None
        self._resize_job: str | None = None

        self._build_screen()
        self._build_clipboard()
        self._build_screenshot()

    # -- schermo e tasti -----------------------------------------------------

    def _build_screen(self) -> None:
        card = Card(self, tr("Screen and keys"), self.fonts)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, theme.GAP))
        body = card.body
        for column in range(len(KEYS)):
            body.grid_columnconfigure(column, weight=1, uniform="key")

        half = len(KEYS) // 2
        self.mirror_btn = button(body, tr("Start mirroring"), self._toggle_mirror, primary=True)
        self.mirror_btn.grid(row=0, column=0, columnspan=half, sticky="ew", padx=(0, 4))
        button(body, tr("Wake screen"), lambda: self._key(tr("Wake screen"), remote.KEY_WAKEUP)).grid(
            row=0, column=half, columnspan=len(KEYS) - half, sticky="ew", padx=(4, 0)
        )

        for column, (label, keycode) in enumerate(KEYS):
            button(body, tr(label), lambda l=label, k=keycode: self._key(tr(l), k), width=60).grid(
                row=1,
                column=column,
                sticky="ew",
                pady=(theme.GAP, 0),
                padx=(0 if column == 0 else 3, 0 if column == len(KEYS) - 1 else 3),
            )

    def _toggle_mirror(self) -> None:
        app = self.app
        if app.scrcpy.is_running():
            app.scrcpy.stop()
            self.mirror_btn.configure(text=tr("Start mirroring"))
            app.status(tr("Mirroring closed."))
            return

        device = app.require_device()
        if device is None:
            return
        if not app.scrcpy.available:
            app.error("scrcpy", tr("scrcpy.exe is not in tools/. Download it from the Tools page."))
            return

        config = app.config_store
        options = {
            key: config.get(key)
            for key in (
                "mirror_max_size",
                "mirror_bitrate",
                "mirror_max_fps",
                "mirror_stay_awake",
                "mirror_turn_screen_off",
                "mirror_always_on_top",
            )
        }
        serial = device.serial

        def ok(_result) -> None:
            self.mirror_btn.configure(text=tr("Stop mirroring"))
            app.status(tr("Mirroring started."))
            app.log(tr("scrcpy started for {serial}").format(serial=serial))
            self.after(1500, self._watch_mirror)

        app.status(tr("Starting mirroring…"))
        app.tasks.run(
            lambda: app.scrcpy.start(serial, options), ok, lambda exc: app.error("Mirroring", exc)
        )

    def _watch_mirror(self) -> None:
        """Si accorge di quando la finestra di scrcpy viene chiusa, e del perche'."""
        scrcpy = self.app.scrcpy
        if scrcpy.is_running():
            self.after(1000, self._watch_mirror)
            return
        self.mirror_btn.configure(text=tr("Start mirroring"))
        problem = scrcpy.last_error()
        if problem:
            self.app.error("Mirroring", problem)
        else:
            self.app.status(tr("Mirroring ended."))

    def _key(self, label: str, keycode: int) -> None:
        app = self.app
        device = app.require_device()
        if device is None:
            return
        serial = device.serial
        app.tasks.run(
            lambda: app.remote.key(serial, keycode),
            lambda _r: app.status(tr("Key sent: {key}").format(key=label)),
            lambda exc: app.error(tr("Send key"), exc),
            lane="input",
        )

    # -- appunti -------------------------------------------------------------

    def _build_clipboard(self) -> None:
        card = Card(self, tr("Clipboard"), self.fonts)
        card.grid(row=1, column=0, sticky="nsew", padx=(0, theme.GAP), pady=(theme.GAP, 0))
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.clip_text = ctk.CTkTextbox(body, height=90, wrap="word", font=self.fonts.mono)
        self.clip_text.grid(row=0, column=0, sticky="nsew")
        self.clip_text.bind("<Control-Return>", lambda _e: (self._paste(), "break")[1])

        main = ctk.CTkFrame(body, fg_color="transparent")
        main.grid(row=1, column=0, sticky="ew", pady=(theme.GAP, 0))
        main.grid_columnconfigure((0, 1), weight=1, uniform="main")
        button(main, tr("Paste on phone"), self._paste, primary=True).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        button(main, tr("Copy from phone"), self._copy, primary=True).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        extra = ctk.CTkFrame(body, fg_color="transparent")
        extra.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        extra.grid_columnconfigure((0, 1, 2), weight=1, uniform="extra")
        button(extra, tr("From PC clipboard"), self._from_pc).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        button(extra, tr("To PC clipboard"), self._to_pc).grid(row=0, column=1, sticky="ew", padx=4)
        button(extra, tr("Clear"), lambda: self.clip_text.delete("1.0", "end")).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        self.sync_var = ctk.BooleanVar(value=bool(self.app.config_store.get("clip_autosync")))
        ctk.CTkSwitch(
            body,
            text=tr("Automatically sync the clipboard between PC and phone"),
            variable=self.sync_var,
            command=self._toggle_sync,
            font=self.fonts.body,
        ).grid(row=3, column=0, sticky="w", pady=(theme.GAP + 2, 0))

        hint = note(
            body,
            tr(
                "“Paste on phone” writes the text into the active field (Ctrl+Enter). With sync "
                "enabled, what you copy on the PC can be pasted on the phone and vice versa, even "
                "without mirroring."
            ),
            self.fonts,
        )
        hint.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        follow_width(hint, body)

    def _text(self) -> str:
        return self.clip_text.get("1.0", "end-1c")

    def _set_text(self, text: str) -> None:
        self.clip_text.delete("1.0", "end")
        self.clip_text.insert("1.0", text)

    def _toggle_sync(self) -> None:
        app = self.app
        enabled = self.sync_var.get()
        app.config_store.set("clip_autosync", enabled)
        if not enabled:
            app.status(tr("Clipboard sync disabled."))
        elif app.current is not None and app.remote.fast(app.current.serial):
            app.status(tr("Clipboard sync enabled."))
        else:
            app.status(tr("Sync starts when fast control is active."))

    def _from_pc(self) -> None:
        text = self.app.clip_get()
        if not text:
            self.app.status(tr("The PC clipboard is empty or contains no text."))
            return
        self._set_text(text)
        self.app.status(tr("Text loaded from the PC clipboard."))

    def _to_pc(self) -> None:
        text = self._text()
        if not text:
            self.app.status(tr("Nothing to copy."))
            return
        if self.app.clip_set(text):
            self.app.status(tr("Text copied to the PC clipboard."))

    def _paste(self) -> None:
        app = self.app
        device = app.require_device()
        if device is None:
            return
        text = self._text()
        if not text.strip():
            app.status(tr("No text to send."))
            return
        serial = device.serial
        if not app.remote.fast(serial) and not is_ascii(text):
            proceed = messagebox.askyesno(
                tr("Non-ASCII characters"),
                tr(
                    "Fast control is not active and 'adb input text' cannot always type "
                    "accented letters, emoji and other non-ASCII characters.\n\n"
                    "Try anyway?"
                ),
                parent=app,
            )
            if not proceed:
                return

        def ok(through_clipboard: bool) -> None:
            if through_clipboard:
                app.status(tr("Text pasted on the phone."))
            else:
                app.status(tr("Text typed on the phone via ADB."))

        app.note_sent_to_phone(text)
        app.status(tr("Sending the text to the phone…"))
        app.tasks.run(
            lambda: app.remote.paste(serial, text),
            ok,
            lambda exc: app.error(tr("Paste on phone"), exc),
            lane="input",
        )

    def _copy(self) -> None:
        app = self.app
        device = app.require_device()
        if device is None:
            return
        serial = device.serial
        fast = app.remote.fast(serial)

        def ok(text: str) -> None:
            if text:
                self._set_text(text)
                app.clip_set(text, from_phone=True)
                app.status(tr("Text copied from the phone: it is also in the PC clipboard."))
                return
            app.status(tr("No text received from the phone."))
            if fast:
                message = tr(
                    "The phone clipboard is empty.\n\n"
                    "Select the text on the phone, or copy it, and try again."
                )
            else:
                message = tr(
                    "Without fast control Android does not allow reading the clipboard "
                    "(access restricted since Android 10).\n\n"
                    "Enable “Fast control” on the Tools page, or use mirroring: with Ctrl+C "
                    "in the scrcpy window the text reaches the PC clipboard."
                )
            messagebox.showinfo(tr("Copy from phone"), message, parent=app)

        app.status(tr("Copying from the phone…"))
        app.tasks.run(
            lambda: app.remote.copy(serial),
            ok,
            lambda exc: app.error(tr("Copy from phone"), exc),
            lane="input",
        )

    # -- screenshot ----------------------------------------------------------

    def _build_screenshot(self) -> None:
        card = Card(self, "Screenshot", self.fonts)
        card.grid(row=0, column=1, rowspan=2, sticky="nsew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        bar = ctk.CTkFrame(body, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure((0, 1, 2), weight=1, uniform="shot")
        button(bar, tr("Capture"), self._take, primary=True, width=70).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        button(bar, tr("Copy"), self._copy_image, width=70).grid(row=0, column=1, sticky="ew", padx=4)
        button(bar, tr("Folder"), self._open_folder, width=70).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        self.shot_clip_var = ctk.BooleanVar(value=bool(self.app.config_store.get("shot_to_clipboard")))
        ctk.CTkSwitch(
            body,
            text=tr("Copy to the PC clipboard right away"),
            variable=self.shot_clip_var,
            command=lambda: self.app.config_store.set("shot_to_clipboard", self.shot_clip_var.get()),
            font=self.fonts.body,
        ).grid(row=1, column=0, sticky="w", pady=(theme.GAP + 2, theme.GAP))

        # Il riquadro ha dimensioni decise dal layout, non dall'immagine che contiene.
        self.preview_box = ctk.CTkFrame(body, fg_color=theme.INPUT, corner_radius=4)
        self.preview_box.grid(row=2, column=0, sticky="nsew")
        self.preview_box.grid_propagate(False)
        self.preview_label = ctk.CTkLabel(
            self.preview_box,
            text=tr("No screenshot.\nPress “Capture”."),
            font=self.fonts.small,
            text_color=theme.MUTED,
            cursor="hand2",
        )
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")
        self.preview_label.bind("<Button-1>", lambda _e: self._open_last())
        self.preview_box.bind("<Configure>", self._on_preview_resize)

        self.shot_caption = note(body, "", self.fonts)
        self.shot_caption.grid(row=3, column=0, sticky="ew", pady=(4, 0))

    def _folder(self) -> Path:
        folder = Path(str(self.app.config_store.get("screenshot_dir")))
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _take(self) -> None:
        app = self.app
        device = app.require_device()
        if device is None:
            return
        try:
            folder = self._folder()
        except OSError as exc:
            app.error(tr("Screenshot folder"), exc)
            return
        serial = device.serial
        to_clipboard = self.shot_clip_var.get() and winclip.AVAILABLE

        def job():
            data = app.adb.screenshot(serial)
            target = unique_path(folder, dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
            target.write_bytes(data)
            copied = False
            if to_clipboard:
                try:
                    winclip.set_image(data)
                    copied = True
                except (winclip.ClipboardError, OSError):
                    pass
            return target, data, make_preview(data), copied

        def ok(result) -> None:
            target, data, preview, copied = result
            self._last_path, self._last_png, self._preview = target, data, preview
            self._render_preview()
            self.shot_caption.configure(text=target.name)
            saved = (
                tr("Screenshot saved and copied to the PC clipboard: {name}")
                if copied
                else tr("Screenshot saved: {name}")
            )
            app.status(saved.format(name=target.name))
            app.log(f"Screenshot: {target}")

        app.status(tr("Capturing screenshot…"))
        app.tasks.run(job, ok, lambda exc: app.error("Screenshot", exc))

    def _copy_image(self) -> None:
        app = self.app
        data = self._last_png
        if data is None:
            app.status(tr("No screenshot to copy: press “Capture”."))
            return
        app.tasks.run(
            lambda: winclip.set_image(data),
            lambda _r: app.status(tr("Screenshot copied to the PC clipboard.")),
            lambda exc: app.error(tr("Copy screenshot"), exc),
        )

    def _open_folder(self) -> None:
        try:
            os.startfile(str(self._folder()))  # noqa: S606 - apre Esplora risorse
        except (OSError, AttributeError) as exc:
            self.app.error(tr("Opening folder"), exc)

    def _open_last(self) -> None:
        path = self._last_path
        if path is None or not path.is_file():
            return
        try:
            os.startfile(str(path))  # noqa: S606 - apre il visualizzatore immagini
        except (OSError, AttributeError) as exc:
            self.app.error(tr("Opening screenshot"), exc)

    def _on_preview_resize(self, _event) -> None:
        if self._preview is None:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self._render_preview)

    def _render_preview(self) -> None:
        """Adatta l'anteprima al riquadro mantenendone le proporzioni."""
        self._resize_job = None
        image = self._preview
        if image is None:
            return
        scale = theme.scaling(self)
        room_w = self.preview_box.winfo_width() / scale - 12
        room_h = self.preview_box.winfo_height() / scale - 12
        if room_w < 20 or room_h < 20:
            return
        ratio = min(room_w / image.width, room_h / image.height)
        size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
        self.preview_label.configure(
            text="", image=ctk.CTkImage(light_image=image, dark_image=image, size=size)
        )


def make_preview(png: bytes) -> Image.Image:
    """Copia ridotta dello screenshot: il PNG intero sarebbe lento da ridisegnare."""
    with Image.open(io.BytesIO(png)) as image:
        preview = image.convert("RGB")
    preview.thumbnail((PREVIEW_MAX, PREVIEW_MAX), Image.LANCZOS)
    return preview


def unique_path(folder: Path, stem: str, suffix: str = ".png") -> Path:
    """Evita di sovrascrivere screenshot acquisiti nello stesso secondo."""
    candidate = folder / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = folder / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate
