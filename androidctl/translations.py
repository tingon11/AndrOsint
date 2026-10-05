# AndrOsint — telecomando Android da PC.  Copyright (C) 2026 Andrea Cumini <andrea@osintinfo.net>
# SPDX-License-Identifier: GPL-3.0-only
# GNU GPL v3 con termini aggiuntivi (attribuzione dell'autore): vedi LICENSE e NOTICE.
"""Traduzione italiana dei testi dell'interfaccia.

La chiave e' il testo inglese cosi' come compare nel codice (in tr() e N_()),
il valore la sua traduzione. I segnaposto tra graffe vanno lasciati identici.
scripts/check_i18n.py segnala le voci mancanti e quelle non piu' usate.
"""

from __future__ import annotations

IT: dict[str, str] = {
    # ---------------------------------------------------------------- avvio
    "Cannot start the interface: {error}\n\n"
    "Install the dependencies with:\n"
    "    python -m pip install -r requirements.txt":
        "Impossibile avviare l'interfaccia: {error}\n\n"
        "Installa le dipendenze con:\n"
        "    python -m pip install -r requirements.txt",

    # ------------------------------------------------------------------ adb
    "Connected": "Connesso",
    "Unauthorized": "Non autorizzato",
    "Unknown": "Sconosciuto",
    "adb.exe not found in tools/. Use the Tools page to download it.":
        "adb.exe non trovato in tools/. Usa la scheda Strumenti per scaricarlo.",
    "adb did not respond within {seconds} seconds.": "adb non ha risposto entro {seconds} secondi.",
    "adb returned exit code {code}": "adb ha restituito il codice {code}",
    "Installation aborted: time limit exceeded.": "Installazione interrotta: tempo massimo superato.",
    "Uninstall failed.": "Disinstallazione non riuscita.",
    "adb forward did not return a port: {output}": "adb forward non ha restituito una porta: {output}",
    "Invalid phone number.": "Numero di telefono non valido.",
    "Screenshot failed: the device did not return a valid PNG.":
        "Screenshot non riuscito: il dispositivo non ha restituito un PNG valido.",

    # ------------------------------------------------- controllo rapido, scrcpy
    "Cannot determine the scrcpy version.": "Versione di scrcpy non determinabile.",
    "Could not start the control channel: {error}":
        "Avvio del canale di controllo non riuscito: {error}",
    "exit code {code}": "codice {code}",
    "scrcpy-server exited immediately: {detail}": "scrcpy-server si è chiuso subito: {detail}",
    "scrcpy-server did not respond in time.": "scrcpy-server non ha risposto in tempo.",
    "app list failed: {error}": "elenco delle app non riuscito: {error}",
    "scrcpy-server did not return the list. {detail}":
        "scrcpy-server non ha restituito l'elenco. {detail}",
    "scrcpy.exe not found in tools/. Use the Tools page to download it.":
        "scrcpy.exe non trovato in tools/. Usa la scheda Strumenti per scaricarlo.",
    "Cannot start scrcpy: {error}": "Impossibile avviare scrcpy: {error}",

    # ------------------------------------------------ download degli strumenti
    "Missing": "Mancante",
    "Downloading {label}": "Download {label}",
    "Download of {label} failed: {error}": "Download di {label} non riuscito: {error}",
    "Invalid archive: suspicious path '{member}'.":
        "Archivio non valido: percorso sospetto '{member}'.",
    "The downloaded file is not a valid zip archive.":
        "Il file scaricato non è un archivio zip valido.",
    "Cannot update '{name}': files in use. Close the mirroring and try again.":
        "Impossibile aggiornare '{name}': file in uso. Chiudi il mirroring e riprova.",
    "Extracting ADB": "Estrazione ADB",
    "The downloaded package does not contain adb.exe.":
        "Il pacchetto scaricato non contiene adb.exe.",
    "adb.exe is missing after extraction.": "adb.exe non risulta presente dopo l'estrazione.",
    "Cannot reach the official scrcpy releases: {error}\nDownload manually from {url}":
        "Impossibile contattare le release ufficiali di scrcpy: {error}\n"
        "Scarica manualmente da {url}",
    "No Windows package found in the latest scrcpy release.\n"
    "Download manually from {url}":
        "Nessun pacchetto Windows trovato nell'ultima release di scrcpy.\n"
        "Scarica manualmente da {url}",
    "Looking for the latest scrcpy release": "Ricerca ultima release scrcpy",
    "Extracting scrcpy": "Estrazione scrcpy",
    "The downloaded package does not contain scrcpy.exe.":
        "Il pacchetto scaricato non contiene scrcpy.exe.",
    "scrcpy.exe is missing after extraction.":
        "scrcpy.exe non risulta presente dopo l'estrazione.",
    "ADB installed: {path}": "ADB installato: {path}",
    "scrcpy installed: {path}": "scrcpy installato: {path}",
    "Unknown tool: {key}": "Strumento sconosciuto: {key}",

    # ------------------------------------------------------ appunti di Windows
    "The Windows clipboard is in use by another program.":
        "Gli appunti di Windows sono occupati da un altro programma.",
    "Not enough memory for the clipboard.": "Memoria insufficiente per gli appunti.",
    "Clipboard memory not accessible.": "Memoria degli appunti non accessibile.",
    "Writing to the clipboard failed.": "Scrittura negli appunti non riuscita.",
    "Clipboard available on Windows only.": "Appunti disponibili solo su Windows.",

    # ------------------------------------------- installazione ed estrazione
    "the app is already installed: enable “Update if already installed”.":
        "l'app è già installata: attiva «Aggiorna se già installata».",
    "the phone has a newer version: enable “Allow older version” "
    "or uninstall the app first.":
        "sul telefono c'è una versione più recente: attiva «Consenti versione precedente» "
        "oppure disinstalla prima l'app.",
    "the signature differs from the installed app: uninstall it and try again.":
        "la firma è diversa da quella dell'app già installata: disinstallala e riprova.",
    "not enough space on the phone.": "spazio insufficiente sul telefono.",
    "the package is not compatible with the phone's processor: download the "
    "right variant (usually arm64-v8a).":
        "il pacchetto non è compatibile con il processore del telefono: scarica la "
        "variante giusta (di solito arm64-v8a).",
    "the package requires a newer Android version than the phone's.":
        "il pacchetto richiede una versione di Android più recente di quella del telefono.",
    "the package is too old for this Android version.":
        "il pacchetto è troppo vecchio per questa versione di Android.",
    "installation blocked by the phone: in Developer options enable "
    "“Install via USB” and confirm the prompt shown on the screen.":
        "installazione bloccata dal telefono: nelle Opzioni sviluppatore attiva "
        "«Installa tramite USB» e conferma la richiesta che compare sullo schermo.",
    "installation cancelled on the phone.": "installazione annullata sul telefono.",
    "this APK is only part of the app: the full package is needed "
    "(.apks, .xapk or .apkm).":
        "questo APK è solo una parte dell'app: serve il pacchetto completo "
        "(.apks, .xapk oppure .apkm).",
    "invalid or corrupted package: download it again.":
        "pacchetto non valido o danneggiato: scaricalo di nuovo.",
    "the file is not a valid APK: download it again.":
        "il file non è un APK valido: scaricalo di nuovo.",
    "unsigned or corrupted package: download it again.":
        "pacchetto non firmato o danneggiato: scaricalo di nuovo.",
    "blocked by the phone's security check (Play Protect).":
        "bloccata dalla verifica di sicurezza del telefono (Play Protect).",
    "test-only package, cannot be installed normally.":
        "pacchetto di sola prova (test-only), non installabile normalmente.",
    "unknown error.": "errore sconosciuto.",
    "the file no longer exists.": "il file non esiste più.",
    "the file is empty: the download did not complete.":
        "il file è vuoto: il download non è andato a buon fine.",
    "Installing…": "Installazione…",
    "Installed": "Installata",
    "Installed ({count} APKs)": "Installata ({count} APK)",
    "corrupted or invalid archive: download it again.":
        "archivio danneggiato o non valido: scaricalo di nuovo.",
    "the archive contains no APK.": "l'archivio non contiene alcun APK.",
    "Extracting…": "Estrazione…",
    "Copying OBB data…": "Copia dei dati OBB…",
    " (OBB data not copied: unknown destination)":
        " (dati OBB non copiati: destinazione sconosciuta)",
    "invalid package name: {package}": "nome di pacchetto non valido: {package}",
    "the app is not installed on the phone.": "l'app non risulta installata sul telefono.",
    "Reading the app on the phone…": "Lettura dell'app sul telefono…",
    "Copying {index} of {total}: {name}…": "Copia {index} di {total}: {name}…",
    "copy of {name} failed: {error}": "copia di {name} non riuscita: {error}",
    "copy of {name} failed: empty file.": "copia di {name} non riuscita: file vuoto.",
    "Building the package…": "Creazione del pacchetto…",

    # ------------------------------------------------------- dialoghi, guscio
    "CONFIRM": "CONFERMA",
    "WARNING": "ATTENZIONE",
    "ERROR": "ERRORE",
    "Yes": "Sì",
    "MODULES": "MODULI",

    # ---------------------------------------------------- finestra principale
    "Control": "Controllo",
    "Apps": "App",
    "Install APK": "Installa APK",
    "Contacts": "Rubrica",
    "Tools": "Strumenti",
    "No device": "Nessun dispositivo",
    "Connect the phone via USB and enable USB debugging in Developer options.":
        "Collega il telefono via USB e attiva il Debug USB nelle Opzioni sviluppatore.",
    "Operation failed": "Operazione non riuscita",
    "DEVICE": "DISPOSITIVO",
    "Ready.": "Pronto.",
    "Ctrl+1..{count}  switch module": "Ctrl+1..{count}  cambia modulo",
    "{app}  /  MODULE {index:02d}": "{app}  /  MODULO {index:02d}",
    "ERROR - {title}: {message}": "ERRORE - {title}: {message}",
    "Error: {title}": "Errore: {title}",
    "INTERNAL ERROR": "ERRORE INTERNO",
    "Internal error: details in the Log (Tools page).":
        "Errore interno: dettagli nel Registro (pagina Strumenti).",
    "Connect an Android phone via USB with USB debugging enabled.":
        "Collega un telefono Android via USB con il Debug USB attivo.",
    "Device not ready": "Dispositivo non pronto",
    "The device state is '{state}'.\n\n"
    "If it is unauthorized, unlock the phone and confirm the "
    "\"Allow USB debugging?\" prompt, choosing to authorize this computer.":
        "Il dispositivo risulta '{state}'.\n\n"
        "Se è non autorizzato, sblocca il telefono e conferma la richiesta "
        "\"Consentire il debug USB?\" scegliendo di autorizzare questo computer.",
    "PC clipboard not available: {error}": "Appunti del PC non disponibili: {error}",
    "Phone clipboard copied to the PC.": "Appunti del telefono copiati sul PC.",
    " and ": " e ",
    "Missing tools": "Strumenti mancanti",
    "{names} not found in the tools/ folder.\n\n"
    "Download now from the official sources "
    "(Google platform-tools / Genymobile scrcpy releases)?\n\n"
    "The download stays in the application folder: no system-wide installation "
    "and no change to PATH.":
        "{names} non risulta presente nella cartella tools/.\n\n"
        "Vuoi scaricarlo ora dalle sorgenti ufficiali "
        "(Google platform-tools / release Genymobile scrcpy)?\n\n"
        "Il download resta nella cartella dell'applicazione: nessuna installazione "
        "di sistema e nessuna modifica al PATH.",
    "ADB missing: download it from the Tools page.":
        "ADB mancante: scaricalo dalla pagina Strumenti.",
    "Refreshing devices…": "Aggiornamento dei dispositivi…",
    "List refreshed.": "Elenco aggiornato.",
    "ADB is missing: download it from the Tools page.":
        "ADB non è presente: scaricalo dalla pagina Strumenti.",
    "Device not authorized: unlock the phone and confirm "
    "\"Allow USB debugging?\" for this computer.":
        "Dispositivo non autorizzato: sblocca il telefono e conferma "
        "\"Consentire il debug USB?\" da questo computer.",
    "Device state: {state}.": "Stato del dispositivo: {state}.",
    "Device ready: {device}": "Dispositivo pronto: {device}",
    "Fast control active on {serial} (instant keys and clipboard).":
        "Controllo rapido attivo su {serial} (tasti e appunti immediati).",
    "Fast control not available, using ADB: {error}":
        "Controllo rapido non disponibile, si usa ADB: {error}",
    "Fast control dropped several times: continuing with ADB.":
        "Controllo rapido interrotto più volte: si prosegue con ADB.",
    "FAST CONTROL": "CONTROLLO RAPIDO",
    "STANDARD ADB": "ADB STANDARD",
    "App names not available: {error}": "Nomi delle app non disponibili: {error}",

    # ------------------------------------------------------- pagina Controllo
    "Back": "Indietro",
    "Recents": "Recenti",
    "Lock": "Blocca",
    "Screen and keys": "Schermo e tasti",
    "Start mirroring": "Avvia mirroring",
    "Stop mirroring": "Chiudi mirroring",
    "Wake screen": "Accendi schermo",
    "Mirroring closed.": "Mirroring chiuso.",
    "scrcpy.exe is not in tools/. Download it from the Tools page.":
        "scrcpy.exe non presente in tools/. Scaricalo dalla pagina Strumenti.",
    "Mirroring started.": "Mirroring avviato.",
    "scrcpy started for {serial}": "scrcpy avviato per {serial}",
    "Starting mirroring…": "Avvio del mirroring…",
    "Mirroring ended.": "Mirroring terminato.",
    "Key sent: {key}": "Tasto inviato: {key}",
    "Send key": "Invio tasto",
    "Clipboard": "Appunti",
    "Paste on phone": "Incolla sul telefono",
    "Copy from phone": "Copia dal telefono",
    "From PC clipboard": "Dagli appunti del PC",
    "To PC clipboard": "Agli appunti del PC",
    "Clear": "Pulisci",
    "Automatically sync the clipboard between PC and phone":
        "Sincronizza automaticamente gli appunti tra PC e telefono",
    "“Paste on phone” writes the text into the active field (Ctrl+Enter). With sync "
    "enabled, what you copy on the PC can be pasted on the phone and vice versa, even "
    "without mirroring.":
        "«Incolla sul telefono» scrive il testo nel campo attivo (Ctrl+Invio). Con la "
        "sincronizzazione attiva, ciò che copi sul PC si incolla sul telefono e viceversa, "
        "anche senza mirroring.",
    "Clipboard sync disabled.": "Sincronizzazione degli appunti disattivata.",
    "Clipboard sync enabled.": "Sincronizzazione degli appunti attiva.",
    "Sync starts when fast control is active.":
        "La sincronizzazione parte quando è attivo il controllo rapido.",
    "The PC clipboard is empty or contains no text.":
        "Gli appunti del PC sono vuoti o non contengono testo.",
    "Text loaded from the PC clipboard.": "Testo caricato dagli appunti del PC.",
    "Nothing to copy.": "Niente da copiare.",
    "Text copied to the PC clipboard.": "Testo copiato negli appunti del PC.",
    "No text to send.": "Nessun testo da inviare.",
    "Non-ASCII characters": "Caratteri non ASCII",
    "Fast control is not active and 'adb input text' cannot always type "
    "accented letters, emoji and other non-ASCII characters.\n\n"
    "Try anyway?":
        "Il controllo rapido non è attivo e 'adb input text' non sempre riesce a "
        "digitare lettere accentate, emoji e altri caratteri non ASCII.\n\n"
        "Provare comunque?",
    "Text pasted on the phone.": "Testo incollato sul telefono.",
    "Text typed on the phone via ADB.": "Testo digitato sul telefono via ADB.",
    "Sending the text to the phone…": "Invio del testo al telefono…",
    "Text copied from the phone: it is also in the PC clipboard.":
        "Testo copiato dal telefono: è anche negli appunti del PC.",
    "No text received from the phone.": "Nessun testo ricevuto dal telefono.",
    "The phone clipboard is empty.\n\n"
    "Select the text on the phone, or copy it, and try again.":
        "Gli appunti del telefono sono vuoti.\n\n"
        "Seleziona il testo sul telefono, oppure copialo, e riprova.",
    "Without fast control Android does not allow reading the clipboard "
    "(access restricted since Android 10).\n\n"
    "Enable “Fast control” on the Tools page, or use mirroring: with Ctrl+C "
    "in the scrcpy window the text reaches the PC clipboard.":
        "Senza controllo rapido Android non permette di leggere gli appunti "
        "(accesso limitato da Android 10).\n\n"
        "Attiva «Controllo rapido» nella pagina Strumenti, oppure usa il mirroring: "
        "con Ctrl+C nella finestra scrcpy il testo arriva negli appunti del PC.",
    "Copying from the phone…": "Copia dal telefono…",
    "Capture": "Scatta",
    "Copy": "Copia",
    "Folder": "Cartella",
    "Copy to the PC clipboard right away": "Copia subito negli appunti del PC",
    "No screenshot.\nPress “Capture”.": "Nessuno screenshot.\nPremi «Scatta».",
    "Screenshot folder": "Cartella screenshot",
    "Screenshot saved and copied to the PC clipboard: {name}":
        "Screenshot salvato e copiato negli appunti del PC: {name}",
    "Screenshot saved: {name}": "Screenshot salvato: {name}",
    "Capturing screenshot…": "Acquisizione screenshot…",
    "No screenshot to copy: press “Capture”.": "Nessuno screenshot da copiare: premi «Scatta».",
    "Screenshot copied to the PC clipboard.": "Screenshot copiato negli appunti del PC.",
    "Copy screenshot": "Copia screenshot",
    "Opening folder": "Apertura cartella",
    "Opening screenshot": "Apertura screenshot",

    # ------------------------------------------------------------- pagina App
    "Search by name or package…": "Cerca per nome o package…",
    "System apps": "App di sistema",
    "Refresh list": "Aggiorna elenco",
    "Name": "Nome",
    "Version": "Versione",
    "Launchable": "Avviabile",
    "Saved on PC": "Salvata nel PC",
    "Open": "Apri",
    "Close": "Chiudi",
    "Uninstall": "Disinstalla",
    "Extract APK": "Estrai APK",
    "“Extract APK” copies the app's package (APK, splits and OBB data) to the PC, "
    "into the folder of the Install APK page, from which it can be reinstalled on "
    "another phone. The “Saved on PC” column shows which apps are already there: green "
    "for the same version as the phone, orange for a different one. Names in brackets "
    "are derived from the package: the phone exposes no name for apps without an icon.":
        "«Estrai APK» copia sul PC il pacchetto dell'app (APK, split e dati OBB) nella cartella "
        "della pagina Installa APK, da cui si reinstalla su un altro telefono. La colonna "
        "«Salvata nel PC» dice quali app sono già lì: in verde la stessa versione del telefono, "
        "in arancione una versione diversa. I nomi tra parentesi sono ricavati dal package: il "
        "telefono non espone un nome per le app senza icona.",
    "Reading the installed applications and their names…":
        "Lettura delle applicazioni installate e dei loro nomi…",
    "{count} applications found, {named} with a visible name.":
        "{count} applicazioni trovate, {named} con il nome visibile.",
    "Application list": "Elenco applicazioni",
    "yes": "sì",
    "{shown} of {total} apps  ·  {saved} saved on PC":
        "{shown} di {total} app  ·  {saved} salvate nel PC",
    "✔  {saved} (phone: {phone})": "✔  {saved} (telefono: {phone})",
    "Select an application from the list.": "Seleziona un'applicazione dall'elenco.",
    "Starting {package}…": "Avvio di {package}…",
    "Started: {package}": "Avviata: {package}",
    "Starting application": "Avvio applicazione",
    "Closing {package}…": "Chiusura di {package}…",
    "Closed: {package}": "Chiusa: {package}",
    "Closing application": "Chiusura applicazione",
    "Uninstall application": "Disinstalla applicazione",
    "Uninstall {name} from the phone?\n\n{package}\n\n"
    "The application's data will be deleted.":
        "Disinstallare {name} dal telefono?\n\n{package}\n\n"
        "I dati dell'applicazione verranno eliminati.",
    "Uninstalled: {name}": "Disinstallata: {name}",
    "Uninstalled {package}": "Disinstallata {package}",
    "Uninstalling {package}…": "Disinstallazione di {package}…",
    "Uninstallation": "Disinstallazione",
    "{name} extracted to {file} ({size}): you will find it on the Install APK page.":
        "{name} estratta in {file} ({size}): la trovi nella pagina Installa APK.",
    "Extracted {package} -> {path}": "Estratto {package} -> {path}",
    "Extraction of {name}": "Estrazione di {name}",
    "Extracting {name}…": "Estrazione di {name}…",

    # ---------------------------------------------------- pagina Installa APK
    "Waiting": "In attesa",
    "Packages folder": "Cartella dei pacchetti",
    "Browse…": "Sfoglia…",
    "Open folder": "Apri cartella",
    "Update if already installed": "Aggiorna se già installata",
    "Allow older version": "Consenti versione precedente",
    "Grant permissions right away": "Concedi subito i permessi",
    "Automatically install new packages saved in this folder":
        "Installa automaticamente i nuovi pacchetti salvati in questa cartella",
    "Package": "Pacchetto",
    "Type": "Tipo",
    "Size": "Dimensione",
    "Status": "Stato",
    "Install selected": "Installa selezionati",
    "Install all": "Installa tutti",
    "Add files…": "Aggiungi file…",
    "Refresh": "Aggiorna",
    "Where to download packages:": "Dove scaricare i pacchetti:",
    "Save .apk, .apks, .xapk or .apkm files in the folder above. When available, "
    "prefer the app's official site and the arm64-v8a variant. Packages extracted from "
    "a phone with “Extract APK” (Apps page) also land here, ready to be reinstalled "
    "on another one.":
        "Salva i file .apk, .apks, .xapk o .apkm nella cartella qui sopra. Quando esiste, "
        "preferisci il sito ufficiale dell'app e la variante arm64-v8a. Qui arrivano anche i "
        "pacchetti estratti da un telefono con «Estrai APK» (pagina App), da reinstallare "
        "su un altro.",
    "Folder of the downloaded packages": "Cartella dei pacchetti scaricati",
    "Packages to install": "Pacchetti da installare",
    "Android packages": "Pacchetti Android",
    "All files": "Tutti i file",
    "No new package among the chosen files.": "Nessun nuovo pacchetto tra i file scelti.",
    "{count} packages": "{count} pacchetti",
    "No package in the folder": "Nessun pacchetto nella cartella",
    "(name not readable)": "(nome non leggibile)",
    "Select one or more packages from the list.": "Seleziona uno o più pacchetti dall'elenco.",
    "No package to install: save one in the folder.":
        "Nessun pacchetto da installare: salvane uno nella cartella.",
    "Queued": "In coda",
    "Preparing…": "Preparazione…",
    "Installed {name} ({file}): {summary}": "Installato {name} ({file}): {summary}",
    "Installation of {name} ({file}) failed: {error}":
        "Installazione di {name} ({file}) non riuscita: {error}",
    "Installation finished: {good} succeeded": "Installazione terminata: {good} riuscite",
    ", {failed} failed (reason in the Status column)":
        ", {failed} non riuscite (motivo nella colonna Stato)",
    "Installing: {done} of {total}…": "Installazione in corso: {done} di {total}…",
    "Automatic installation enabled: save a package in the folder.":
        "Installazione automatica attiva: salva un pacchetto nella cartella.",
    "Automatic installation disabled.": "Installazione automatica disattivata.",
    "Automatic installation: {files}": "Installazione automatica: {files}",

    # --------------------------------------------------------- pagina Rubrica
    "Number to enter": "Numero da inserire",
    "Number": "Numero",
    "Name (optional)": "Nome (facoltativo)",
    "Actions on the phone": "Azioni sul telefono",
    "New pre-filled contact": "Nuovo contatto precompilato",
    "Open Contacts": "Apri Contatti",
    "Open dialer with number": "Apri tastierino con numero",
    "Type number on phone": "Digita numero sul telefono",
    "The number is pre-filled in Android's new-contact screen: saving must be "
    "confirmed on the phone. The contacts database is never modified directly. "
    "“Open dialer” does not start the call.":
        "Il numero viene precompilato nella schermata Android di creazione contatto: il "
        "salvataggio va confermato sul telefono. Il database dei contatti non viene "
        "modificato direttamente. «Apri tastierino» non avvia la chiamata.",
    "Enter a phone number.": "Inserisci un numero di telefono.",
    "New-contact screen opened on the phone.": "Schermata nuovo contatto aperta sul telefono.",
    "New contact": "Nuovo contatto",
    "Contacts app opened.": "Applicazione Contatti aperta.",
    "Opening Contacts": "Apertura Contatti",
    "Dialer opened with the number.": "Tastierino aperto con il numero.",
    "Opening dialer": "Apertura tastierino",
    "Number typed on the phone.": "Numero digitato sul telefono.",
    "Typing number": "Digitazione numero",

    # ------------------------------------------------------- pagina Strumenti
    "Local tools (tools/ folder)": "Strumenti locali (cartella tools/)",
    "Check": "Verifica",
    "Download / Update": "Scarica / Aggiorna",
    "Restart ADB": "Riavvia ADB",
    "Max resolution (px)": "Risoluzione max (px)",
    "Video bitrate": "Bitrate video",
    "Max FPS": "FPS max",
    "Keep the phone awake": "Mantieni il telefono sveglio",
    "Turn the phone screen off": "Spegni lo schermo del telefono",
    "Window always on top": "Finestra sempre in primo piano",
    "General": "Generali",
    "Fast control (instant keys and clipboard)": "Controllo rapido (tasti e appunti immediati)",
    "Stop the ADB server on exit": "Arresta il server ADB alla chiusura",
    "Log": "Registro",
    "Tools check: ": "Verifica strumenti: ",
    "Downloading tools…": "Download strumenti in corso…",
    "Tools ready.": "Strumenti pronti.",
    "Tools download": "Download strumenti",
    "adb.exe is not in tools/.": "adb.exe non presente in tools/.",
    "Restarting the ADB server…": "Riavvio del server ADB…",
    "ADB server restarted.": "Server ADB riavviato.",
    "Folder for screenshots": "Cartella per gli screenshot",
}
