# AndrOsint

[English](README.md) · **Italiano**

Telecomando desktop per un telefono Android reale collegato al PC via USB:
copia e incolla tra PC e telefono, screenshot, installazione di app a partire
dai pacchetti scaricati, mirroring dello schermo.

**Autore: Andrea Cumini — [www.osintinfo.net](https://www.osintinfo.net) — andrea@osintinfo.net**

Interfaccia in Python con **customtkinter**, nello stesso stile di TagFaces
(tema scuro Seity); ADB e scrcpy sono usati come programmi **standalone**
nella cartella `tools/`.

Non è un software di digital forensics: niente casi, niente chain of custody,
niente database, niente audit, niente telemetria, niente cloud.

## Requisiti

- Windows 10/11
- Python 3.10 o superiore (con Tkinter, incluso nell'installer ufficiale)
- Un telefono Android con **Debug USB** attivo nelle Opzioni sviluppatore

Dipendenze Python (`requirements.txt`): `customtkinter` e `pillow`.

```bash
python -m pip install -r requirements.txt
```

## Avvio

```bash
python main.py
```

Oppure con doppio clic su `Avvia.bat` (avvia senza finestra console e usa il
virtualenv `.venv` se presente).

## Lingua

L'interfaccia è in **inglese** (predefinita) oppure in **italiano**. Si cambia
con le sigle **EN / IT** in alto a destra, accanto ai pulsanti della finestra:
il cambio è immediato, senza riavviare, e la scelta è salvata in `config.json`.
Restano nella lingua in cui sono nati solo il registro e gli esiti già scritti
nelle tabelle. In questo documento pagine e pulsanti sono indicati con i nomi
dell'interfaccia italiana.

Nel codice i testi sono in inglese; la traduzione italiana è in
`androidctl/translations.py`. Dopo aver aggiunto o cambiato un testo,
`scripts/check_i18n.py` segnala le traduzioni mancanti o non più usate.

## Eseguibile unico

Per avere un solo `AndrOsint.exe` da usare senza Python installato:

```bash
.venv\Scripts\python.exe scripts\build_exe.py
```

Lo script installa PyInstaller nel virtualenv se manca e produce
`dist/AndrOsint.exe` (un file, senza console, con l'icona e le proprietà del
file). ADB e scrcpy non sono dentro l'eseguibile: li cerca nella cartella
`tools/` accanto a sé e, se mancano, propone di scaricarli. Accanto
all'eseguibile finiscono anche `config.json`, `apk/` e `screenshots/`.

## Primo avvio

Al primo avvio l'applicazione verifica la presenza di ADB e scrcpy in `tools/`.
Se manca qualcosa propone il download automatico dalle sorgenti ufficiali:

| Strumento | Origine |
|---|---|
| ADB (platform-tools) | `https://dl.google.com/android/repository/platform-tools-latest-windows.zip` (pacchetto ufficiale Google) |
| scrcpy | ultima release ufficiale di [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy/releases/latest) |

Il download viene estratto dentro `tools/`:

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

Il PATH di Windows **non** viene modificato e non servono privilegi di
amministratore. Gli stessi controlli sono richiamabili in qualsiasi momento
dalla pagina **Strumenti** (pulsanti *Verifica* e *Scarica / Aggiorna*).

Se il download automatico non è possibile (rete chiusa, proxy), basta scaricare
manualmente i due pacchetti e scompattarli nei percorsi indicati sopra.

## Perché è reattiva

- **Nessun comando nel thread dell'interfaccia.** Ogni chiamata ad ADB gira in
  background; tasti e installazioni hanno una coda propria, così restano in
  ordine senza bloccare il resto.
- **Dispositivi in tempo reale.** L'applicazione resta in ascolto sul server ADB
  (`track-devices`): collegare o scollegare il telefono si vede subito, senza
  interrogazioni periodiche.
- **Controllo rapido.** `adb shell input keyevent` avvia una JVM sul telefono a
  ogni pressione (oltre mezzo secondo). Quando scrcpy è presente in `tools/`,
  l'applicazione avvia `scrcpy-server` senza video né audio e gli parla con il
  protocollo di controllo di scrcpy: i tasti arrivano in pochi millisecondi e
  gli appunti si leggono e si scrivono per intero, Unicode compreso. Lo stato è
  mostrato accanto al dispositivo (*Controllo rapido* / *ADB standard*); se il
  canale non è disponibile si ripiega da soli sui comandi ADB.
- **Pagine costruite al primo uso** e tabelle native (`ttk.Treeview`) che
  reggono centinaia di righe senza rallentare.
- **Layout adattivo**: riquadri e colonne delle tabelle si ridistribuiscono con
  la finestra; sotto una certa larghezza la barra laterale si riduce alle sole
  icone (o lo si sceglie con il pulsante in basso).

## Aspetto

Lo stile è quello di TagFaces: tema scuro con un solo colore d'accento, finestra
senza barra del titolo (l'intestazione con il logo fa da barra: si trascina, il
doppio clic massimizza, restano Aero Snap e il ridimensionamento dai bordi),
navigazione laterale con le icone di Windows, titoli dei riquadri in maiuscolo,
dialoghi scuri al posto di quelli di sistema.

Il logo è la scritta bicolore **AndrOsint** nel carattere Panchang Semibold, e
l'icona il quadrato scuro con le iniziali. Sono file già pronti in
`androidctl/ui/assets/`: per usare il programma il carattere non serve. Per
rigenerarli (altro nome, altro colore) si modifica `scripts/make_brand.py` e lo
si lancia su un PC con Panchang installato:

```bash
.venv\Scripts\python.exe scripts\make_brand.py
```

Scorciatoie: `Ctrl+1…5` cambia pagina, `F5` rilegge i dispositivi,
`Ctrl+Invio` nel riquadro Appunti incolla sul telefono.

## Funzioni

### Dispositivo
Modello, produttore, versione Android (con API level) e stato della connessione.
Con più telefoni collegati si sceglie quale controllare dal menu a tendina. Se il
telefono risulta *Non autorizzato*, l'applicazione lo segnala e ricorda di
confermare sul telefono la richiesta "Consentire il debug USB?".

### Controllo
- **Avvia mirroring**: apre la finestra scrcpy per vedere e comandare il
  telefono con mouse e tastiera. La configurazione è pensata per un basso
  consumo di CPU/GPU (risoluzione ridotta, bitrate contenuto, FPS limitati,
  audio disattivato); i parametri si cambiano dalla pagina Strumenti.
- **Accendi schermo** e tasti **Indietro / Home / Recenti / Blocca / Volume**.
- **Appunti** (copia e incolla):
  - *Incolla sul telefono* scrive il testo nel campo attivo del telefono;
  - *Copia dal telefono* copia la selezione fatta sul telefono e la porta nel
    riquadro e negli appunti del PC;
  - *Sincronizza automaticamente*: ciò che copi sul PC si incolla sul telefono
    e viceversa, anche senza mirroring. È disattivata per impostazione
    predefinita perché tutto ciò che copi sul PC (password comprese) finisce
    anche sul telefono.
- **Screenshot**: acquisito via ADB (`exec-out screencap`, con fallback
  `screencap` + `pull`), salvato subito sul PC, mostrato in anteprima e, se
  attivo l'interruttore, copiato come immagine negli appunti di Windows, pronto
  da incollare in un documento o in una chat.

### App
Elenco delle applicazioni installate con nome e package name, ricerca testuale,
avvio, chiusura, disinstallazione (con conferma) ed **estrazione del pacchetto**.
Le app di sistema si possono includere con l'apposito interruttore.

**Estrai APK** copia sul PC il pacchetto di un'app installata, nella cartella
della pagina Installa APK (predefinita `apk/`), con il nome dell'app nel nome
del file, ad esempio `Calcolatrice (com.sec.android.app.popupcalculator) 10.0.00.41.apk`:

- un'app in un solo APK ha estensione `.apk`;
- un'app a più APK (split per processore, densità, lingua) o con dati OBB
  diventa un archivio `.apks`, che la pagina Installa APK sa reinstallare.

La colonna **Salvata nel PC** dice quali app hanno già un pacchetto nella
cartella: in verde con la stessa versione del telefono, in arancione con una
versione diversa (il pacchetto salvato è più vecchio o più nuovo). Si aggiorna
da sola dopo ogni estrazione e ogni volta che si torna sulla pagina, così si
vede subito cosa resta da salvare. Estrarre di nuovo un'app già salvata nella
stessa versione sostituisce il file.

È il percorso consigliato per copiare un'app da un telefono all'altro: la si
installa nel modo tradizionale (Play Store) sul primo, la si estrae, e con il
secondo telefono collegato la si installa dalla pagina Installa APK. Il
pacchetto è identico a quello distribuito dallo store, firma compresa. Vale
quello che vale per ogni copia di un'app: le app a pagamento e quelle legate a
un account restano soggette alle rispettive licenze.

- L'avvio usa il normale intent di lancio (`am start -n <componente>`), con
  fallback su `monkey` quando l'activity non è risolvibile.
- La chiusura usa `am force-stop`, la disinstallazione `adb uninstall`.
- La colonna **Nome** mostra il nome che l'utente vede sul telefono, nella
  lingua del telefono. ADB da solo non lo espone: lo fornisce `scrcpy-server`
  in modalità elenco (`list_apps`), lo stesso componente del controllo rapido,
  per tutte le app avviabili. Le app senza icona (servizi, provider) non hanno
  un nome visibile: per loro compare, tra parentesi, un nome ricavato dal
  package. Senza scrcpy in `tools/` restano i nomi derivati per tutte.

### Installa APK
Installa sul telefono i pacchetti scaricati sul PC.

1. Scarica il pacchetto dell'app (vedi sotto dove).
2. Salvalo nella **cartella dei pacchetti** (predefinita `apk/`, accanto
   all'applicazione; si cambia con *Sfoglia…*). In alternativa *Aggiungi file…*.
3. *Installa selezionati* oppure *Installa tutti*. L'esito di ogni pacchetto
   compare nella colonna **Stato**, con la causa in chiaro se qualcosa non va.

Con **Installa automaticamente i nuovi pacchetti** attivo basta salvare il file
nella cartella: l'installazione parte da sola appena il download è completo e il
telefono è collegato (i pacchetti già presenti non vengono toccati).

La colonna **App** mostra nome e versione letti dentro il pacchetto (manifest
binario e tabella delle risorse, nella lingua di Windows quando l'app è
tradotta), così si sa cosa si sta installando anche quando il nome del file
non lo dice; `.xapk` e `.apkm` li dichiarano nei propri metadati.

Formati riconosciuti:

| Formato | Contenuto | Come viene installato |
|---|---|---|
| `.apk` | pacchetto singolo | `adb install` |
| `.apks`, `.xapk`, `.apkm` | APK base + APK divisi (processore, densità, lingua), eventuali dati OBB | estratti, scelti gli split adatti al telefono, `adb install-multiple`; gli OBB vengono copiati in `Android/obb/` |

Opzioni: *Aggiorna se già installata* (`-r`), *Consenti versione precedente*
(`-d`), *Concedi subito i permessi* (`-g`).

**Dove scaricare i pacchetti**

| Sito | Cosa offre |
|---|---|
| Sito ufficiale dell'app | quando lo sviluppatore pubblica l'APK (es. Telegram, Signal, WhatsApp): è la fonte da preferire |
| [APKMirror](https://www.apkmirror.com/) | APK originali delle app del Play Store, con firma verificata; i pacchetti multipli sono `.apkm` |
| [F-Droid](https://f-droid.org/) | app open source, compilate dai sorgenti |
| [APKPure](https://apkpure.com/) | alternativa per app e giochi, spesso in formato `.xapk` |

Scegli la variante **arm64-v8a** (adatta alla quasi totalità dei telefoni) e,
se chiesta, la densità `nodpi`. Evita siti che propongono versioni "mod" o
"sbloccate": sono la via più comune per installare malware.

Su alcuni telefoni (Xiaomi, Oppo, Vivo) va attivata anche l'opzione
*Installa tramite USB* nelle Opzioni sviluppatore.

Con il mirroring aperto resta valida anche la via di scrcpy: trascinando un
`.apk` sulla finestra lo si installa, trascinando un altro file lo si copia in
`/sdcard/Download`.

### Rubrica
Non c'è una rubrica interna al programma. C'è solo un aiuto all'inserimento:

- il numero si incolla dagli appunti del PC;
- **Nuovo contatto precompilato** apre la schermata Android di creazione
  contatto con numero (e nome) già inseriti — il salvataggio va confermato
  sul telefono;
- **Apri Contatti** apre l'app Contatti;
- **Apri tastierino con numero** apre il dialer con il numero inserito (non
  avvia la chiamata);
- **Digita numero sul telefono** scrive il numero nel campo attivo.

Il database interno dei contatti non viene mai modificato direttamente: si usano
solo intent pubblici Android.

### Strumenti
Stato di ADB e scrcpy, download/aggiornamento, riavvio del server ADB, cartella
di destinazione degli screenshot, parametri del mirroring (risoluzione massima,
bitrate, FPS, mantieni sveglio, spegni schermo, finestra in primo piano),
controllo rapido e registro delle operazioni. Ogni scelta vale subito ed è
salvata in `config.json` accanto all'applicazione.

*Arresta il server ADB alla chiusura* è disattivato di default: lasciare il
server in esecuzione rende immediato l'avvio successivo. Va attivato se si
vuole che alla chiusura non resti alcun processo `adb.exe`.

## Screenshot

Salvati nella cartella configurata (predefinita `screenshots/`), con nome
basato su data e ora:

```
screenshots/
  2026-08-30_11-32-15.png
  2026-08-30_11-34-42.png
```

Se due screenshot cadono nello stesso secondo viene aggiunto un suffisso
numerico.

## Note sugli appunti

- **Con il controllo rapido** (stato *Controllo rapido* accanto al dispositivo)
  gli appunti del telefono si leggono e si scrivono direttamente: funzionano
  lettere accentate, emoji e testi su più righe, in entrambe le direzioni.
  *Incolla sul telefono* sostituisce gli appunti del telefono con il testo
  inviato e lo incolla nel campo attivo.
- **Senza controllo rapido** (scrcpy assente o disattivato dalle impostazioni)
  si ripiega su ADB: *Incolla sul telefono* digita il testo con
  `adb shell input text`, affidabile solo per i caratteri ASCII, e *Copia dal
  telefono* di norma non riesce, perché da Android 10 la shell non può leggere
  gli appunti.
- **Con il mirroring** valgono anche le scorciatoie di scrcpy: Ctrl+C e Ctrl+V
  nella finestra del telefono.

## Struttura del progetto

```
main.py                 avvio dell'applicazione
Avvia.bat               avvio senza finestra console
requirements.txt        dipendenze Python
androidctl/
  paths.py              percorsi dell'app e ricerca degli eseguibili in tools/
  config.py             impostazioni su config.json
  i18n.py               lingua dell'interfaccia (inglese predefinito, italiano)
  translations.py       traduzione italiana dei testi
  process.py            esecuzione processi senza finestre console
  adb.py                wrapper ADB (dispositivi, app, installazione, screenshot)
  bridge.py             canale di controllo diretto via scrcpy-server (tasti, appunti)
  remote.py             tasti e appunti: canale diretto, con ripiego su ADB
  installer.py          installazione di .apk / .apks / .xapk / .apkm, estrazione dal telefono
  apkinfo.py            nome, package e versione letti da un pacchetto (manifest binario, resources.arsc)
  library.py            indice dei pacchetti nella cartella del PC, condiviso dalle pagine App e Installa APK
  winclip.py            appunti di Windows (testo e immagini)
  scrcpy.py             avvio/arresto del mirroring
  tools.py              verifica e download di ADB e scrcpy
  ui/
    app.py              finestra principale, dispositivi, sincronizzazione appunti
    tasks.py            lavori in background e ritorno dei risultati alla GUI
    theme.py            palette, caratteri, tema CustomTkinter, stile delle tabelle
    shell.py            barra laterale, cambio lingua e pulsanti della finestra
    frameless.py        finestra senza barra del titolo (Windows)
    dialogs.py          dialoghi scuri (sostituiscono tkinter.messagebox)
    widgets.py          riquadri, pulsanti, tabelle
    assets/             logo e icona (generati da scripts/make_brand.py)
    pages/              una pagina per voce della barra laterale
scripts/
  make_brand.py         rigenera logo e icona dal carattere Panchang
  build_exe.py          compila dist/AndrOsint.exe con PyInstaller
  check_i18n.py         controlla che ogni testo abbia la traduzione italiana
tools/                  ADB e scrcpy locali (scaricati dall'app)
apk/                    pacchetti da installare (cartella predefinita)
screenshots/            destinazione predefinita degli screenshot
config.json             impostazioni (creato al primo salvataggio)
```

## Limiti volutamente accettati

Il programma usa solo comandi ADB pubblici e il server di scrcpy, che gira con
i permessi della shell ADB. Non implementa recupero di dati cancellati, bypass
di protezioni, root, exploit o accesso a dati protetti dal sistema, e richiede
un dispositivo sbloccato con Debug USB autorizzato dall'utente.

## Licenza e crediti

AndrOsint è software libero, rilasciato sotto **GNU General Public License
versione 3** con termini aggiuntivi: vedi [LICENSE](LICENSE) e [NOTICE](NOTICE).
Lo puoi usare, studiare, modificare e ridistribuire, a patto che le versioni
derivate restino sotto la stessa licenza. È distribuito senza alcuna garanzia.

I termini aggiuntivi (GPL-3 §7), scritti per esteso in `NOTICE`:

- **Attribuzione obbligatoria**: ogni copia e ogni versione modificata deve
  conservare le note di copyright e la dicitura di paternità
  « Andrea Cumini - andrea@osintinfo.net - www.osintinfo.net », visibile
  nell'interfaccia (la riga dei crediti nella barra di stato, in fondo alla
  finestra) e nella documentazione.
- **Versioni modificate**: vanno indicate come diverse dall'originale.
- **Nome e logo**: una versione modificata distribuita ad altri deve usare un
  nome e un logo diversi.

Copyright © 2026 Andrea Cumini — [www.osintinfo.net](https://www.osintinfo.net) — andrea@osintinfo.net

I programmi di terze parti scaricati a runtime nella cartella `tools/`
(ADB / platform-tools di Google, scrcpy di Genymobile) hanno licenze proprie e
non fanno parte di questo repository.
