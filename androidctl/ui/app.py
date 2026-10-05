# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Finestra principale di AndrOsint."""

from __future__ import annotations

import datetime as dt
import threading
import time
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from .. import APP_NAME, CREDITS, __version__, apkinfo, i18n, paths, tools, winclip
from ..adb import Adb, Device
from ..bridge import Bridge, BridgeError, app_labels
from ..config import Config
from ..i18n import N_, tr
from ..library import PackageLibrary
from ..remote import Remote
from ..scrcpy import Scrcpy
from . import frameless, shell, theme
from .dialogs import messagebox
from .pages.apps import AppsPage
from .pages.base import Page
from .pages.contacts import ContactsPage
from .pages.control import ControlPage
from .pages.install import InstallPage
from .pages.tools import ToolsPage
from .tasks import Tasks
from .widgets import retranslate_all

# chiave, etichetta, glifo (Segoe Fluent Icons), pagina
PAGES: tuple[tuple[str, str, str, type[Page]], ...] = (
    ("control", N_("Control"), "\ue8ea", ControlPage),
    ("apps", N_("Apps"), "\ue71d", AppsPage),
    ("install", N_("Install APK"), "\ue896", InstallPage),
    ("contacts", N_("Contacts"), "\ue77b", ContactsPage),
    ("tools", N_("Tools"), "\ue713", ToolsPage),
)

DEFAULT_SIZE = "1180x760"
MIN_SIZE = (960, 640)
COLLAPSE_BELOW = 1060     # larghezza finestra sotto cui la barra laterale si comprime
PAGE_HEADER_ABOVE = 700   # altezza finestra sopra cui si mostra il titolo della pagina
SUBTITLE_ABOVE = 1240     # larghezza finestra sopra cui l'intestazione mostra il sottotitolo
SHORTCUT_ABOVE = 1150     # larghezza finestra sopra cui il piede ricorda la scorciatoia
DEVICE_MENU = (170, 236)  # larghezza del menu del dispositivo: minima e normale
SYNC_MS = 400            # controllo degli appunti del PC; quelli del telefono ogni due giri
SYNC_TEXT_MAX = 100_000  # oltre questa lunghezza il testo non viene sincronizzato
LOG_MAX = 500
BRIDGE_RETRIES = 3

NO_DEVICE = N_("No device")
NO_DEVICE_HINT = N_("Connect the phone via USB and enable USB debugging in Developer options.")


class App(ctk.CTk):
    """Finestra unica: intestazione, barra laterale e pagina corrente."""

    def __init__(self) -> None:
        self.config_store = Config()
        i18n.set_language(self.config_store.get("language"))
        theme.apply()
        super().__init__()

        self.title(APP_NAME)
        self.minsize(*MIN_SIZE)
        try:
            self.geometry(str(self.config_store.get("geometry")) or DEFAULT_SIZE)
        except tk.TclError:
            self.geometry(DEFAULT_SIZE)
        theme.set_icon(self)
        # senza barra del titolo di sistema: l'intestazione fa da barra
        self.frameless = frameless.make_frameless(self, border_color=theme.BORDER)

        self.fonts = theme.Fonts()
        theme.style_tables(self)

        self.adb = Adb()
        self.scrcpy = Scrcpy(self.adb)
        self.tasks = Tasks(
            self,
            on_crash=lambda exc: self.error(tr("Operation failed"), exc),
            on_bug=self._bug,
        )
        self.bridge = Bridge(
            self.adb,
            on_clipboard=lambda text: self.tasks.post(self._device_clipboard, text),
            on_closed=lambda serial: self.tasks.post(self._bridge_closed, serial),
        )
        self.remote = Remote(self.adb, self.bridge)
        self.library = PackageLibrary(apkinfo.system_language())

        self.devices: list[Device] = []
        self.current: Device | None = None
        self._signature: list[tuple[str, str]] | None = None
        self._stop = threading.Event()
        self.log_lines: list[str] = []
        self.pages: dict[str, Page] = {}
        self._page_key = ""
        self._busy_shown = False
        self._layout_job: str | None = None

        self._bridge_pending = ""
        self._bridge_failures = 0
        self._labels: dict[str, dict[str, str]] = {}  # seriale -> package -> nome visibile

        # Sincronizzazione degli appunti
        self._sync_active = False
        self._sync_since = 0.0
        self._sync_tick_count = 0
        self._pc_sequence = 0
        self._device_text: str | None = None
        self._last_synced = ""

        self._build()
        self._hint(tr(NO_DEVICE_HINT))
        self.show_page("control")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        for index, (key, _label, _glyph, _cls) in enumerate(PAGES, start=1):
            self.bind(f"<Control-Key-{index}>", lambda _e, k=key: self.show_page(k))
        self.bind("<F5>", lambda _e: self.refresh_devices())
        self.bind("<Configure>", self._on_configure, add="+")

        self.after(60, self._startup)
        self.after(SYNC_MS, self._sync_tick)
        self.after(150, self._busy_tick)

    # ------------------------------------------------------------ costruzione

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._rule(self, horizontal=True).grid(row=1, column=0, sticky="ew")

        body = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(2, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.rail = shell.NavRail(
            body, self.fonts, [(key, tr(label), glyph) for key, label, glyph, _cls in PAGES],
            on_select=self.show_page,
        )
        self.rail.grid(row=0, column=0, sticky="ns")
        self._rule(body, horizontal=False).grid(row=0, column=1, sticky="ns")

        main = ctk.CTkFrame(body, fg_color=theme.BG, corner_radius=0)
        main.grid(row=0, column=2, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # titolo della pagina: percorso in piccolo e nome in grande
        self.page_head = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
        self.page_head.grid(row=0, column=0, sticky="ew", padx=22, pady=(14, 0))
        self.crumb_label = ctk.CTkLabel(
            self.page_head, text="", anchor="w", font=self.fonts.caption,
            text_color=theme.TEXT_FAINT, height=14,
        )
        self.crumb_label.pack(anchor="w")
        self.title_label = ctk.CTkLabel(
            self.page_head, text="", anchor="w", font=self.fonts.page, text_color=theme.TEXT
        )
        self.title_label.pack(anchor="w")

        self.hint_label = ctk.CTkLabel(
            main, text="", font=self.fonts.small, text_color=theme.WARN, anchor="w", justify="left"
        )
        self.hint_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(8, 0))
        self.hint_label.grid_remove()

        self.content = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
        self.content.grid(row=2, column=0, sticky="nsew", padx=14, pady=(10, 12))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._rule(self, horizontal=True).grid(row=3, column=0, sticky="ew")
        self._build_footer()

    @staticmethod
    def _rule(parent, horizontal: bool) -> ctk.CTkFrame:
        """Filetto di separazione da un pixel."""
        size = {"height": 1} if horizontal else {"width": 1}
        return ctk.CTkFrame(parent, fg_color=theme.BORDER, corner_radius=0, **size)

    def _build_header(self) -> None:
        """Intestazione: logo, dispositivo, stato. Fa anche da barra del titolo."""
        header = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0, height=50)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(2, weight=1)
        header.grid_rowconfigure(0, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(18, 0))
        logo = theme.logo(17)
        if logo is not None:
            name = ctk.CTkLabel(brand, text="", image=logo)
        else:
            name = ctk.CTkLabel(brand, text=APP_NAME.upper(), font=(theme.mono_font(), 15, "bold"))
        name.pack(side="left")
        version = ctk.CTkLabel(brand, text=f"   v{__version__}", font=(theme.mono_font(), 10),
                               text_color=theme.TEXT_DIM)
        version.pack(side="left", pady=(3, 0))
        self._subtitle = ctk.CTkLabel(brand, text="  \u00b7  android controller",
                                      font=(theme.mono_font(), 10), text_color=theme.TEXT_FAINT)

        # dispositivo selezionato
        chip = ctk.CTkFrame(header, fg_color=theme.PANEL, corner_radius=4, border_width=1,
                            border_color=theme.BORDER, height=32)
        chip.grid(row=0, column=1, sticky="w", padx=(20, 0))
        tag = ctk.CTkLabel(chip, text=tr("DEVICE"), font=self.fonts.caption,
                           text_color=theme.TEXT_FAINT)
        tag.pack(side="left", padx=(10, 6), pady=2)
        self.device_menu = ctk.CTkOptionMenu(
            chip, values=[tr(NO_DEVICE)], width=DEVICE_MENU[1], height=24, dynamic_resizing=False,
            fg_color=theme.PANEL, button_color=theme.PANEL, button_hover_color=theme.HOVER,
            font=self.fonts.bold, dropdown_font=self.fonts.body,
            command=self._on_device_selected,
        )
        self.device_menu.pack(side="left", pady=3)
        self.device_menu.set(tr(NO_DEVICE))
        self.device_menu.configure(state="disabled")
        has_icons = bool(theme.icon_font())
        ctk.CTkButton(
            chip, text=shell.GLYPH_REFRESH if has_icons else "↻", width=28, height=24,
            corner_radius=4, fg_color="transparent", hover_color=theme.HOVER,
            text_color=theme.TEXT_DIM, font=self.fonts.icon(12), command=self.refresh_devices,
        ).pack(side="left", padx=(2, 4))

        spacer = ctk.CTkFrame(header, fg_color="transparent", height=1)
        spacer.grid(row=0, column=2, sticky="ew")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=3, sticky="e", padx=(0, 12))
        self.mode_label = ctk.CTkLabel(right, text="", font=self.fonts.caption,
                                       text_color=theme.TEXT_DIM)
        self.mode_label.pack(side="left", padx=(0, 14))
        self.state_dot = ctk.CTkLabel(right, text="\u25cf", font=(theme.mono_font(), 12),
                                      text_color=theme.TEXT_FAINT)
        self.state_dot.pack(side="left", padx=(0, 6))
        self.state_label = ctk.CTkLabel(right, text=tr(NO_DEVICE), font=self.fonts.bold,
                                        text_color=theme.TEXT_SOFT)
        self.state_label.pack(side="left")
        self.language_switch = shell.LanguageSwitch(
            right, self.fonts, list(i18n.LANGUAGES), i18n.language(), self.set_language
        )
        self.language_switch.pack(side="left", padx=(14, 0))

        self._brand, self._chip, self._window_buttons = brand, chip, None
        if self.frameless:
            self._window_buttons = shell.window_buttons(self, header, self._on_close)
            self._window_buttons.grid(row=0, column=4, sticky="ne", padx=(4, 0))
            for widget in (header, brand, name, version, self._subtitle, spacer, right, tag,
                           self.mode_label, self.state_dot, self.state_label):
                frameless.enable_drag(self, widget)

    def _build_footer(self) -> None:
        """Piede: messaggio di stato a sinistra; a destra telefono collegato e crediti."""
        footer = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0, height=26)
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_rowconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(footer, text=tr("Ready."), font=self.fonts.small,
                                         text_color=theme.TEXT_SOFT, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=(16, 8))
        self.busy_bar = ctk.CTkProgressBar(footer, mode="indeterminate", width=90, height=4)
        self.busy_bar.grid(row=0, column=1, padx=(0, 14))
        self.busy_bar.grid_remove()
        self.info_label = ctk.CTkLabel(footer, text="", font=self.fonts.tiny,
                                       text_color=theme.TEXT_DIM)
        self.info_label.grid(row=0, column=2, sticky="e", padx=(0, 16))
        shortcut = tr("Ctrl+1..{count}  switch module").format(count=len(PAGES))
        self._shortcut_label = ctk.CTkLabel(footer, text=shortcut, font=self.fonts.tiny,
                                            text_color=theme.TEXT_FAINT)
        self._shortcut_label.grid(row=0, column=3, sticky="e", padx=(0, 16))
        # Dicitura di paternita' (vedi NOTICE): sempre visibile, in ogni pagina e a ogni larghezza.
        ctk.CTkLabel(footer, text=CREDITS, font=self.fonts.tiny, text_color=theme.TEXT_DIM).grid(
            row=0, column=4, sticky="e", padx=(0, 16))

    # ------------------------------------------------------------- navigazione

    def show_page(self, key: str) -> None:
        if key == self._page_key:
            return
        page = self.ensure_page(key)
        previous = self.pages.get(self._page_key)
        if previous is not None:
            # Solo la pagina visibile partecipa al layout: il ridimensionamento resta fluido.
            previous.grid_remove()
        page.grid()
        self.rail.select(key)
        index = next(i for i, entry in enumerate(PAGES, start=1) if entry[0] == key)
        self.crumb_label.configure(
            text=tr("{app}  /  MODULE {index:02d}").format(app=APP_NAME.upper(), index=index)
        )
        self.title_label.configure(text=tr(PAGES[index - 1][1]))
        self._page_key = key
        page.on_show()

    def ensure_page(self, key: str) -> Page:
        """Restituisce la pagina, costruendola se non e' mai stata aperta."""
        page = self.pages.get(key)
        if page is None:
            cls = next(entry[3] for entry in PAGES if entry[0] == key)
            page = self.pages[key] = cls(self)
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()
        return page

    def _on_configure(self, event) -> None:
        if event.widget is self:
            self._schedule_layout()

    def _schedule_layout(self) -> None:
        """Riadatta il guscio tra un momento: richieste ravvicinate ne fanno una sola."""
        if self._layout_job is not None:
            self.after_cancel(self._layout_job)
        self._layout_job = self.after(120, self._apply_layout)

    def _apply_layout(self) -> None:
        """Adatta il guscio alle dimensioni della finestra."""
        self._layout_job = None
        scale = theme.window_scaling(self)
        width, height = self.winfo_width() / scale, self.winfo_height() / scale
        if self.rail.user_choice is None:
            self.rail.set_collapsed(width < COLLAPSE_BELOW)
        if height >= PAGE_HEADER_ABOVE:
            self.page_head.grid()
        else:
            self.page_head.grid_remove()
        wide = width >= SUBTITLE_ABOVE
        if wide and not self._subtitle.winfo_ismapped():
            self._subtitle.pack(side="left", pady=(3, 0))
        elif not wide and self._subtitle.winfo_ismapped():
            self._subtitle.pack_forget()
        if width >= SHORTCUT_ABOVE:
            self._shortcut_label.grid()
        else:
            self._shortcut_label.grid_remove()  # lo spazio serve al messaggio di stato
        self._fit_header(width, scale)

    def _fit_header(self, width: float, scale: float) -> None:
        """Fa stare l'intestazione nella finestra, qualunque sia la lingua.

        Quando lo spazio non basta si stringe prima il menu del dispositivo, poi si
        rinuncia alla modalita' di controllo: i pulsanti della finestra, all'estrema
        destra, non devono mai finire fuori.
        """
        narrow, full = DEVICE_MENU
        self._brand.update_idletasks()  # il sottotitolo puo' essere appena cambiato

        def wide(widget) -> float:
            return widget.winfo_reqwidth() / scale

        needed = (
            18 + wide(self._brand)
            + 20 + wide(self._chip) - self.device_menu.cget("width") + full
            + wide(self.mode_label) + 14
            + wide(self.state_dot) + 6 + wide(self.state_label)
            + 14 + wide(self.language_switch) + 12
            + (4 + wide(self._window_buttons) if self._window_buttons is not None else 0)
        )
        overflow = needed + 12 - width  # 12: un minimo di respiro tra dispositivo e stato
        menu_width = int(min(full, max(narrow, full - overflow)))
        if menu_width != self.device_menu.cget("width"):
            self.device_menu.configure(width=menu_width)
        fits = overflow <= full - narrow
        if fits and not self.mode_label.winfo_manager():
            self.mode_label.pack(side="left", padx=(0, 14), before=self.state_dot)
        elif not fits and self.mode_label.winfo_manager():
            self.mode_label.pack_forget()

    # -------------------------------------------------------------- helper UI

    def status(self, message: str) -> None:
        self.status_label.configure(text=message)

    def log(self, message: str) -> None:
        line = f"[{dt.datetime.now():%H:%M:%S}] {message}"
        self.log_lines.append(line)
        del self.log_lines[:-LOG_MAX]
        page = self.pages.get("tools")
        if page is not None:
            page.append_log(line)

    def error(self, title: str, exc: BaseException | str) -> None:
        message = str(exc) or exc.__class__.__name__
        self.log(tr("ERROR - {title}: {message}").format(title=title, message=message))
        self.status(tr("Error: {title}").format(title=title))
        messagebox.showerror(title, message, parent=self)

    def _bug(self, trace: str) -> None:
        """Errore imprevisto in una callback: va nel registro, senza fermare l'app."""
        self.log(tr("INTERNAL ERROR") + "\n" + trace.rstrip())
        self.status(tr("Internal error: details in the Log (Tools page)."))

    def _busy_tick(self) -> None:
        """Mostra l'indicatore di attivita' finche' ci sono lavori in corso."""
        if self._stop.is_set():
            return
        busy = self.tasks.busy
        if busy != self._busy_shown:
            self._busy_shown = busy
            if busy:
                self.busy_bar.grid()
                self.busy_bar.start()
            else:
                self.busy_bar.stop()
                self.busy_bar.grid_remove()
        self.after(150, self._busy_tick)

    def require_device(self) -> Device | None:
        """Restituisce il dispositivo selezionato, se pronto all'uso."""
        device = self.current
        if device is None:
            messagebox.showinfo(
                tr(NO_DEVICE),
                tr("Connect an Android phone via USB with USB debugging enabled."),
                parent=self,
            )
            return None
        if not device.ready:
            messagebox.showwarning(
                tr("Device not ready"),
                tr(
                    "The device state is '{state}'.\n\n"
                    "If it is unauthorized, unlock the phone and confirm the "
                    "\"Allow USB debugging?\" prompt, choosing to authorize this computer."
                ).format(state=device.state_text),
                parent=self,
            )
            return None
        return device

    # --------------------------------------------------------- appunti del PC

    def clip_get(self) -> str:
        try:
            if winclip.AVAILABLE:
                return winclip.get_text()
            return self.clipboard_get()
        except (winclip.ClipboardError, tk.TclError):
            return ""

    def clip_set(self, text: str, from_phone: bool = False) -> bool:
        """Scrive negli appunti del PC.

        Con `from_phone` il testo arriva dal telefono: la sincronizzazione non
        deve rimandarglielo indietro.
        """
        try:
            if winclip.AVAILABLE:
                winclip.set_text(text)
            else:
                self.clipboard_clear()
                self.clipboard_append(text)
        except (winclip.ClipboardError, tk.TclError) as exc:
            self.status(tr("PC clipboard not available: {error}").format(error=exc))
            return False
        if from_phone:
            self._last_synced = text
            self._pc_sequence = winclip.sequence()
        return True

    def note_sent_to_phone(self, text: str) -> None:
        """Il testo e' stato appena scritto sugli appunti del telefono da noi."""
        self._last_synced = text

    # ------------------------------------------- sincronizzazione degli appunti

    def _sync_tick(self) -> None:
        if self._stop.is_set():
            return
        self.after(SYNC_MS, self._sync_tick)

        device = self.current
        active = (
            bool(self.config_store.get("clip_autosync"))
            and device is not None
            and device.ready
            and self.bridge.connected_to(device.serial)
        )
        if not active:
            self._sync_active = False
            return
        if not self._sync_active:
            # Appena attivata: quello che c'e' gia' negli appunti fa solo da
            # riferimento, non viene copiato da una parte all'altra.
            self._sync_active = True
            self._sync_since = time.monotonic()
            self._sync_tick_count = 0
            self._device_text = None
            self._pc_sequence = winclip.sequence()

        self._sync_tick_count += 1
        sequence = winclip.sequence()
        if sequence != self._pc_sequence:
            self._pc_sequence = sequence
            text = self.clip_get()
            if text and len(text) <= SYNC_TEXT_MAX and text != self._last_synced:
                self._last_synced = text
                self.tasks.run(
                    lambda: self.bridge.set_clipboard(text),
                    on_error=lambda _exc: None,
                    lane="input",
                )

        if self._sync_tick_count % 2 == 0:
            try:
                self.bridge.poll_clipboard()
            except BridgeError:
                pass

    def _device_clipboard(self, text: str) -> None:
        """Il telefono ha comunicato il contenuto dei propri appunti."""
        if not self._sync_active:
            return
        if self._device_text is None and time.monotonic() - self._sync_since < 1.5:
            self._device_text = text
            return
        if text == (self._device_text or ""):
            return
        self._device_text = text
        if not text or text == self._last_synced:
            return
        if self.clip_set(text, from_phone=True):
            self.status(tr("Phone clipboard copied to the PC."))

    # ---------------------------------------------------------------- lingua

    def set_language(self, code: str) -> None:
        """Cambia lingua a programma aperto: i testi a schermo vengono ritradotti subito."""
        if code == i18n.language():
            return
        code = i18n.set_language(code)
        self.config_store.set("language", code)
        self.config_store.save()
        self.language_switch.select(code)
        retranslate_all(self)
        if not self.devices:
            # Le voci del menu non sono un testo del widget: vanno riscritte a mano.
            self.device_menu.configure(values=[tr(NO_DEVICE)])
            self.device_menu.set(tr(NO_DEVICE))
        self._schedule_layout()  # i testi dell'intestazione hanno cambiato larghezza

    # ---------------------------------------------------------------- avvio

    def _startup(self) -> None:
        absent = tools.missing()
        if absent:
            names = tr(" and ").join({"adb": "ADB", "scrcpy": "scrcpy"}[k] for k in absent)
            answer = messagebox.askyesno(
                tr("Missing tools"),
                tr(
                    "{names} not found in the tools/ folder.\n\n"
                    "Download now from the official sources "
                    "(Google platform-tools / Genymobile scrcpy releases)?\n\n"
                    "The download stays in the application folder: no system-wide installation "
                    "and no change to PATH."
                ).format(names=names),
                parent=self,
            )
            if answer:
                self.show_page("tools")
                self.pages["tools"].install_tools(absent)

        threading.Thread(
            target=self.adb.track_devices,
            args=(lambda found: self.tasks.post(self._update_devices, found), self._stop),
            name="apc-devices",
            daemon=True,
        ).start()

        if self.config_store.get("install_auto"):
            # La sorveglianza della cartella pacchetti vive nella pagina Installa.
            self.after(800, lambda: self.ensure_page("install"))

    # ----------------------------------------------------------- dispositivi

    def refresh_devices(self) -> None:
        """Rilegge l'elenco su richiesta (di norma arriva da solo, in tempo reale)."""
        if not self.adb.available:
            self.status(tr("ADB missing: download it from the Tools page."))
            return
        self.status(tr("Refreshing devices…"))
        self.tasks.run(
            self.adb.devices,
            lambda found: (self._update_devices(found, force=True), self.status(tr("List refreshed."))),
            lambda exc: self.log(f"adb devices: {exc}"),
        )

    def _update_devices(self, found: list[Device], force: bool = False) -> None:
        signature = [(d.serial, d.state) for d in found]
        if signature == self._signature and not force:
            return
        self._signature = signature

        # I dettagli gia' letti (produttore, versione) restano validi per lo stesso seriale.
        known = {d.serial: d for d in self.devices}
        for device in found:
            old = known.get(device.serial)
            if old is not None and old.state == device.state:
                device.model = device.model or old.model
                device.manufacturer, device.android, device.sdk = old.manufacturer, old.android, old.sdk
        self.devices = found

        previous = self.current
        wanted = previous.serial if previous else str(self.config_store.get("last_serial"))
        match = next((d for d in found if d.serial == wanted), None) or (found[0] if found else None)

        if found:
            self.device_menu.configure(values=[d.label for d in found], state="normal")
            self.device_menu.set(match.label)
        else:
            self.device_menu.configure(values=[tr(NO_DEVICE)], state="disabled")
            self.device_menu.set(tr(NO_DEVICE))

        self._select(match, force=force)

    def _on_device_selected(self, label: str) -> None:
        match = next((d for d in self.devices if d.label == label), None)
        if match is not None:
            self._select(match)

    def _select(self, device: Device | None, force: bool = False) -> None:
        previous = self.current
        self.current = device
        changed = (
            force
            or (previous is None) != (device is None)
            or (device is not None and (previous.serial, previous.state) != (device.serial, device.state))
        )
        if not changed:
            return

        if device is None:
            self._show_state(tr(NO_DEVICE), theme.TEXT_FAINT)
            self.info_label.configure(text="")
            self._hint(
                tr(NO_DEVICE_HINT)
                if self.adb.available
                else tr("ADB is missing: download it from the Tools page.")
            )
        else:
            self.config_store.set("last_serial", device.serial)
            self._show_device(device)

        ready = device is not None and device.ready
        if ready:
            self._start_bridge(device.serial)
        else:
            self._stop_bridge()
        self._notify_device()

    def _notify_device(self) -> None:
        device = self.current if self.current is not None and self.current.ready else None
        for page in self.pages.values():
            page.on_device(device)

    def _show_device(self, device: Device) -> None:
        self._show_state(device.state_text, theme.OK if device.ready else theme.WARN)

        if device.state == "unauthorized":
            self.info_label.configure(text=device.label)
            self._hint(
                tr(
                    "Device not authorized: unlock the phone and confirm "
                    "\"Allow USB debugging?\" for this computer."
                )
            )
            return
        if not device.ready:
            self.info_label.configure(text=device.label)
            self._hint(tr("Device state: {state}.").format(state=device.state_text))
            return

        self._hint("")
        self._show_info(device)
        if device.android:
            return

        serial = device.serial

        def ok(info: dict[str, str]) -> None:
            current = self.current
            if current is None or current.serial != serial:
                return
            current.model = info["model"] or current.model
            current.manufacturer = info["manufacturer"]
            current.android = info["android"]
            current.sdk = info["sdk"]
            self._show_info(current)
            self.status(tr("Device ready: {device}").format(device=current.label))

        self.tasks.run(
            lambda: self.adb.device_info(serial), ok, lambda exc: self.log(f"getprop: {exc}")
        )

    def _show_info(self, device: Device) -> None:
        parts = [device.model or "-"]
        if device.manufacturer:
            parts.append(device.manufacturer)
        if device.android:
            android = f"Android {device.android}"
            if device.sdk:
                android += f" (API {device.sdk})"
            parts.append(android)
        self.info_label.configure(text="  ·  ".join(parts).upper())

    def _hint(self, text: str) -> None:
        if text:
            self.hint_label.configure(text=text)
            self.hint_label.grid()
        else:
            self.hint_label.grid_remove()

    def _show_state(self, text: str, color: str) -> None:
        """Stato della connessione nell'intestazione: spia colorata e testo."""
        self.state_dot.configure(text_color=color)
        self.state_label.configure(
            text=text, text_color=theme.TEXT if color == theme.OK else theme.TEXT_SOFT
        )
        self._schedule_layout()

    # --------------------------------------------------- canale di controllo

    def _start_bridge(self, serial: str) -> None:
        """Apre il canale diretto (tasti e appunti istantanei), se abilitato e possibile."""
        if self.bridge.connected_to(serial):
            self._show_mode(True)
            return
        self._show_mode(False)
        if not self.config_store.get("fast_control") or self._bridge_pending == serial:
            return
        jar = paths.scrcpy_server_path()
        if jar is None:
            return
        self._bridge_pending = serial

        def job() -> None:
            self.bridge.start(serial, jar, self.scrcpy.version_string())

        def ok(_result) -> None:
            self._bridge_pending = ""
            current = self.current
            if current is None or current.serial != serial or not current.ready:
                self._stop_bridge()
                return
            self._bridge_failures = 0
            self._show_mode(True)
            self.log(
                tr("Fast control active on {serial} (instant keys and clipboard).").format(serial=serial)
            )

        def failed(exc: BaseException) -> None:
            self._bridge_pending = ""
            self._show_mode(False)
            self.log(tr("Fast control not available, using ADB: {error}").format(error=exc))

        self.tasks.run(job, ok, failed, lane="bridge")

    def _stop_bridge(self) -> None:
        self._show_mode(False)
        if self.bridge.serial:
            self.tasks.run(self.bridge.stop, on_error=lambda _exc: None, lane="bridge")

    def _bridge_closed(self, serial: str) -> None:
        """Il canale si e' chiuso da solo: se il telefono c'e' ancora, lo si riapre."""
        self._show_mode(False)
        current = self.current
        if current is None or not current.ready or current.serial != serial:
            return
        if self._bridge_failures >= BRIDGE_RETRIES:
            self.log(tr("Fast control dropped several times: continuing with ADB."))
            return
        self._bridge_failures += 1

        def retry() -> None:
            current = self.current
            if current is not None and current.ready and current.serial == serial:
                self._start_bridge(serial)

        self.after(2000, retry)

    def apply_fast_control(self) -> None:
        """Applica subito la scelta fatta nelle impostazioni."""
        device = self.current
        if device is None or not device.ready:
            return
        if self.config_store.get("fast_control"):
            self._bridge_failures = 0
            self._start_bridge(device.serial)
        else:
            self._stop_bridge()

    def _show_mode(self, fast: bool) -> None:
        device = self.current
        if device is None or not device.ready:
            self.mode_label.configure(text="")
        elif fast:
            self.mode_label.configure(text=tr("FAST CONTROL"), text_color=theme.ACCENT)
        else:
            self.mode_label.configure(text=tr("STANDARD ADB"), text_color=theme.TEXT_DIM)
        self._schedule_layout()

    # ------------------------------------------------------- nomi delle app

    def app_labels(self, serial: str, refresh: bool = False) -> dict[str, str]:
        """Nomi visibili delle app del telefono (da chiamare in background).

        Vuoto se scrcpy non e' disponibile: si resta ai nomi derivati dal package.
        """
        if not refresh and serial in self._labels:
            return self._labels[serial]
        jar = paths.scrcpy_server_path()
        if jar is None:
            return {}
        try:
            labels = app_labels(self.adb, jar, self.scrcpy.version_string(), serial)
        except BridgeError as exc:
            self.tasks.post(self.log, tr("App names not available: {error}").format(error=exc))
            return {}
        self._labels[serial] = labels
        return labels

    def forget_labels(self, serial: str) -> None:
        """Dopo un'installazione o disinstallazione i nomi vanno riletti."""
        self._labels.pop(serial, None)

    def packages_dir(self) -> Path:
        return Path(str(self.config_store.get("packages_dir")))

    # ----------------------------------------------- aggiornamento strumenti

    def suspend_adb(self) -> None:
        """Libera gli eseguibili in tools/ prima di sostituirli."""
        self.adb.paused = True
        self.scrcpy.stop()
        self.bridge.stop()
        self._show_mode(False)

    def resume_adb(self) -> None:
        self.adb.refresh_path()
        self.adb.paused = False
        self._signature = None

    # --------------------------------------------------------------- uscita

    def _on_close(self) -> None:
        self._stop.set()
        self.tasks.close()
        for page in self.pages.values():
            try:
                page.on_close()
            except Exception:  # noqa: BLE001 - la chiusura non deve mai fallire
                pass
        try:
            if self.state() == "normal":
                self.config_store.set("geometry", self.geometry().split("+")[0])
        except tk.TclError:
            pass
        self.config_store.save()
        self.scrcpy.stop()
        kill_server = bool(self.config_store.get("kill_adb_on_exit"))
        self.bridge.stop(keep_forward=kill_server)
        if kill_server:
            self.adb.kill_server_detached()
        self.destroy()


def run() -> None:
    App().mainloop()
