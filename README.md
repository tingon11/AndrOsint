# AndrOsint

**English** · [Italiano](README.it.md)

A desktop remote control for a real Android phone connected to the PC over
USB: copy and paste between PC and phone, screenshots, installing apps from
downloaded packages, screen mirroring.

**Author: Andrea Cumini — [www.osintinfo.net](https://www.osintinfo.net) — andrea@osintinfo.net**

The interface is written in Python with **customtkinter**, in the same style
as TagFaces (the Seity dark theme); ADB and scrcpy are used as **standalone**
programs in the `tools/` folder.

It is not digital forensics software: no cases, no chain of custody, no
database, no audit trail, no telemetry, no cloud.

## Requirements

- Windows 10/11
- Python 3.10 or later (with Tkinter, included in the official installer)
- An Android phone with **USB debugging** enabled in Developer options

Python dependencies (`requirements.txt`): `customtkinter` and `pillow`.

```bash
python -m pip install -r requirements.txt
```

## Running

```bash
python main.py
```

Or double-click `Avvia.bat` (it starts without a console window and uses the
`.venv` virtualenv if present).

## Language

The interface is in **English** (default) or **Italian**. Switch with the
**EN / IT** labels at the top right, next to the window buttons: the change is
immediate, with no restart, and the choice is saved in `config.json`. Only the
log and the results already written in the tables stay in the language they
were produced in. In this document pages and buttons are referred to by their
names in the English interface.

In the code the texts are in English; the Italian translation is in
`androidctl/translations.py`. After adding or changing a text,
`scripts/check_i18n.py` reports missing or no longer used translations.

## Single executable

To get a single `AndrOsint.exe` that runs without Python installed:

```bash
.venv\Scripts\python.exe scripts\build_exe.py
```

The script installs PyInstaller into the virtualenv if it is missing and
produces `dist/AndrOsint.exe` (one file, no console, with the icon and the
file properties). ADB and scrcpy are not inside the executable: it looks for
them in the `tools/` folder next to itself and, if they are missing, offers to
download them. `config.json`, `apk/` and `screenshots/` also end up next to
the executable.

## First start

At first start the application checks that ADB and scrcpy are present in
`tools/`. If something is missing it offers to download it automatically from
the official sources:

| Tool | Source |
|---|---|
| ADB (platform-tools) | `https://dl.google.com/android/repository/platform-tools-latest-windows.zip` (official Google package) |
| scrcpy | latest official release of [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy/releases/latest) |

The download is extracted into `tools/`:

```
tools/
  platform-tools/
    adb.exe
    ...
  scrcpy/
    scrcpy.exe
    scrcpy-server
    ...
```

The Windows PATH is **not** modified and no administrator privileges are
needed. The same checks can be run at any time from the **Tools** page
(*Check* and *Download / Update* buttons).

If the automatic download is not possible (closed network, proxy), just
download the two packages manually and unpack them into the paths shown above.

## Why it is responsive

- **No command runs in the interface thread.** Every ADB call runs in the
  background; keys and installations each have their own queue, so they stay
  in order without blocking the rest.
- **Devices in real time.** The application listens to the ADB server
  (`track-devices`): plugging or unplugging the phone shows up immediately,
  with no polling.
- **Fast control.** `adb shell input keyevent` starts a JVM on the phone at
  every key press (over half a second). When scrcpy is present in `tools/`,
  the application starts `scrcpy-server` with no video and no audio and talks
  to it using scrcpy's control protocol: keys arrive in a few milliseconds and
  the clipboard is read and written in full, Unicode included. The state is
  shown next to the device (*Fast control* / *Standard ADB*); if the channel is
  not available the application falls back to ADB commands by itself.
- **Pages built on first use** and native tables (`ttk.Treeview`) that handle
  hundreds of rows without slowing down.
- **Adaptive layout**: panels and table columns are redistributed with the
  window; below a certain width the sidebar shrinks to icons only (or you
  choose that with the button at the bottom).

## Look

The style is that of TagFaces: a dark theme with a single accent colour, a
window without a title bar (the header with the logo acts as the bar: it can
be dragged, a double click maximizes, Aero Snap and resizing from the edges
still work), side navigation with Windows icons, panel titles in capitals,
dark dialogs instead of the system ones.

The logo is the two-colour **AndrOsint** wordmark set in Panchang Semibold,
and the icon is the dark square with the initials. They are ready-made files
in `androidctl/ui/assets/`: the font is not needed to use the program. To
regenerate them (another name, another colour) edit `scripts/make_brand.py`
and run it on a PC with Panchang installed:

```bash
.venv\Scripts\python.exe scripts\make_brand.py
```

Shortcuts: `Ctrl+1…5` switches page, `F5` re-reads the devices, `Ctrl+Enter`
in the Clipboard panel pastes on the phone.

## Features

### Device
Model, manufacturer, Android version (with API level) and connection state.
With several phones connected, choose which one to control from the drop-down
menu. If the phone shows as *Unauthorized*, the application says so and
reminds you to confirm the "Allow USB debugging?" prompt on the phone.

### Control
- **Start mirroring**: opens the scrcpy window to see and control the phone
  with mouse and keyboard. The configuration is meant for low CPU/GPU usage
  (reduced resolution, moderate bitrate, limited FPS, audio off); the
  parameters are changed from the Tools page.
- **Wake screen** and the **Back / Home / Recents / Lock / Volume** keys.
- **Clipboard** (copy and paste):
  - *Paste on phone* writes the text into the phone's active field;
  - *Copy from phone* copies the selection made on the phone and brings it
    into the panel and the PC clipboard;
  - *Automatically sync*: what you copy on the PC can be pasted on the phone
    and vice versa, even without mirroring. It is off by default because
    everything you copy on the PC (passwords included) also ends up on the
    phone.
- **Screenshot**: captured via ADB (`exec-out screencap`, falling back to
  `screencap` + `pull`), saved to the PC right away, shown as a preview and,
  if the switch is on, copied as an image to the Windows clipboard, ready to
  paste into a document or a chat.

### Apps
List of the installed applications with name and package name, text search,
start, close, uninstall (with confirmation) and **package extraction**.
System apps can be included with the dedicated switch.

**Extract APK** copies the package of an installed app to the PC, into the
folder of the Install APK page (default `apk/`), with the app's name in the
file name, for example `Calculator (com.sec.android.app.popupcalculator) 10.0.00.41.apk`:

- an app made of a single APK gets the `.apk` extension;
- an app made of several APKs (splits by processor, density, language) or
  with OBB data becomes an `.apks` archive, which the Install APK page can
  reinstall.

The **Saved on PC** column shows which apps already have a package in the
folder: green with the same version as the phone, orange with a different
version (the saved package is older or newer). It updates by itself after
each extraction and every time you return to the page, so you can see at once
what is left to save. Extracting again an app already saved in the same
version replaces the file.

This is the recommended way to copy an app from one phone to another: install
it the usual way (Play Store) on the first, extract it, and with the second
phone connected install it from the Install APK page. The package is
identical to the one distributed by the store, signature included. What holds
for any copy of an app holds here too: paid apps and apps tied to an account
remain subject to their licenses.

- Starting uses the normal launch intent (`am start -n <component>`), falling
  back to `monkey` when the activity cannot be resolved.
- Closing uses `am force-stop`, uninstalling uses `adb uninstall`.
- The **Name** column shows the name the user sees on the phone, in the
  phone's language. ADB alone does not expose it: it is provided by
  `scrcpy-server` in list mode (`list_apps`), the same component used by fast
  control, for all launchable apps. Apps without an icon (services,
  providers) have no visible name: for them a name derived from the package
  is shown, in brackets. Without scrcpy in `tools/` all names are derived ones.

### Install APK
Installs on the phone the packages downloaded to the PC.

1. Download the app's package (see below where).
2. Save it in the **packages folder** (default `apk/`, next to the
   application; change it with *Browse…*). Alternatively use *Add files…*.
3. *Install selected* or *Install all*. The outcome of each package appears
   in the **Status** column, with the cause in plain words if something goes
   wrong.

With **Automatically install new packages saved in this folder** on, just
save the file in the folder: installation starts by itself as soon as the
download is complete and the phone is connected (packages already there are
not touched).

The **App** column shows the name and version read from inside the package
(binary manifest and resource table, in the Windows language when the app is
translated), so you know what you are installing even when the file name does
not say; `.xapk` and `.apkm` declare them in their own metadata.

Supported formats:

| Format | Content | How it is installed |
|---|---|---|
| `.apk` | single package | `adb install` |
| `.apks`, `.xapk`, `.apkm` | base APK + split APKs (processor, density, language), optional OBB data | extracted, the splits suited to the phone are chosen, `adb install-multiple`; OBB files are copied to `Android/obb/` |

Options: *Update if already installed* (`-r`), *Allow older version* (`-d`),
*Grant permissions right away* (`-g`).

**Where to download packages**

| Site | What it offers |
|---|---|
| The app's official site | when the developer publishes the APK (e.g. Telegram, Signal, WhatsApp): the source to prefer |
| [APKMirror](https://www.apkmirror.com/) | original APKs of Play Store apps, with verified signature; multi-APK packages are `.apkm` |
| [F-Droid](https://f-droid.org/) | open source apps, built from source |
| [APKPure](https://apkpure.com/) | an alternative for apps and games, often in `.xapk` format |

Choose the **arm64-v8a** variant (suitable for almost all phones) and, if
asked, the `nodpi` density. Avoid sites offering "mod" or "unlocked"
versions: they are the most common way to install malware.

On some phones (Xiaomi, Oppo, Vivo) the *Install via USB* option must also be
enabled in Developer options.

With mirroring open the scrcpy way also remains available: dragging an `.apk`
onto the window installs it, dragging another file copies it to
`/sdcard/Download`.

### Contacts
The program has no address book of its own. It only helps with entering a
number:

- the number is pasted from the PC clipboard;
- **New pre-filled contact** opens Android's new-contact screen with the
  number (and name) already filled in — saving must be confirmed on the
  phone;
- **Open Contacts** opens the Contacts app;
- **Open dialer with number** opens the dialer with the number entered (it
  does not start the call);
- **Type number on phone** writes the number into the active field.

The internal contacts database is never modified directly: only public
Android intents are used.

### Tools
State of ADB and scrcpy, download/update, restarting the ADB server, the
screenshot destination folder, mirroring parameters (maximum resolution,
bitrate, FPS, keep awake, turn screen off, window on top), fast control and
the operations log. Every choice applies immediately and is saved in
`config.json` next to the application.

*Stop the ADB server on exit* is off by default: leaving the server running
makes the next start immediate. Turn it on if you want no `adb.exe` process to
be left when the application closes.

## Screenshots

Saved in the configured folder (default `screenshots/`), named by date and
time:

```
screenshots/
  2026-08-30_11-32-15.png
  2026-08-30_11-34-42.png
```

If two screenshots fall in the same second a numeric suffix is added.

## Notes on the clipboard

- **With fast control** (state *Fast control* next to the device) the phone
  clipboard is read and written directly: accented letters, emoji and
  multi-line texts work, in both directions. *Paste on phone* replaces the
  phone clipboard with the text sent and pastes it into the active field.
- **Without fast control** (scrcpy missing or turned off in the settings) the
  application falls back to ADB: *Paste on phone* types the text with
  `adb shell input text`, reliable only for ASCII characters, and *Copy from
  phone* usually fails, because since Android 10 the shell cannot read the
  clipboard.
- **With mirroring** scrcpy's shortcuts also apply: Ctrl+C and Ctrl+V in the
  phone window.

## Project structure

```
main.py                 application entry point
Avvia.bat               start without a console window
requirements.txt        Python dependencies
androidctl/
  paths.py              application paths and lookup of the executables in tools/
  config.py             settings in config.json
  i18n.py               interface language (English by default, Italian)
  translations.py       Italian translation of the texts
  process.py            running processes without console windows
  adb.py                ADB wrapper (devices, apps, installation, screenshots)
  bridge.py             direct control channel through scrcpy-server (keys, clipboard)
  remote.py             keys and clipboard: direct channel, falling back to ADB
  installer.py          installing .apk / .apks / .xapk / .apkm, extraction from the phone
  apkinfo.py            name, package and version read from a package (binary manifest, resources.arsc)
  library.py            index of the packages in the PC folder, shared by the Apps and Install APK pages
  winclip.py            Windows clipboard (text and images)
  scrcpy.py             starting/stopping the mirroring
  tools.py              checking and downloading ADB and scrcpy
  ui/
    app.py              main window, devices, clipboard sync
    tasks.py            background jobs and delivery of the results to the GUI
    theme.py            palette, fonts, CustomTkinter theme, table style
    shell.py            sidebar, language switch and window buttons
    frameless.py        window without a title bar (Windows)
    dialogs.py          dark dialogs (replacing tkinter.messagebox)
    widgets.py          panels, buttons, tables
    assets/             logo and icon (generated by scripts/make_brand.py)
    pages/              one page per sidebar entry
scripts/
  make_brand.py         regenerates logo and icon from the Panchang font
  build_exe.py          builds dist/AndrOsint.exe with PyInstaller
  check_i18n.py         checks that every text has its Italian translation
tools/                  local ADB and scrcpy (downloaded by the app)
apk/                    packages to install (default folder)
screenshots/            default destination of the screenshots
config.json             settings (created at the first save)
```

## Deliberately accepted limits

The program uses only public ADB commands and the scrcpy server, which runs
with the permissions of the ADB shell. It does not implement recovery of
deleted data, bypassing of protections, root, exploits or access to data
protected by the system, and it requires an unlocked device with USB
debugging authorized by the user.

## License and credits

AndrOsint is free software, released under the **GNU General Public License
version 3** with additional terms: see [LICENSE](LICENSE) and [NOTICE](NOTICE).
You may use, study, modify and redistribute it, provided that derived
versions remain under the same license. It comes with no warranty.

The additional terms (GPL-3 §7), set out in full in `NOTICE`:

- **Mandatory attribution**: every copy and every modified version must
  preserve the copyright notices and the author attribution
  "Andrea Cumini - andrea@osintinfo.net - www.osintinfo.net", visible in the
  interface (the credits line in the status bar at the bottom of the window)
  and in the documentation.
- **Modified versions**: they must be marked as different from the original.
- **Name and logo**: a modified version distributed to others must use a
  different name and logo.

Copyright © 2026 Andrea Cumini — [www.osintinfo.net](https://www.osintinfo.net) — andrea@osintinfo.net

Third-party programs downloaded at runtime into the `tools/` folder (ADB /
platform-tools by Google, scrcpy by Genymobile) have their own licenses and
are not part of this repository.
