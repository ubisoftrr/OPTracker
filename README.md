# OP17 Verfügbarkeits-Tracker

Überwacht Produktseiten von Shops und meldet per **E-Mail** und **Telegram**, sobald sich der Verfügbarkeitsstatus ändert (z.B. "ausverkauft" → "verfügbar").

## 1. Installation

```bash
pip install -r requirements.txt
```

(Python 3.9+ empfohlen)

## 2. Konfiguration (`config.json`)

### Produkte
Unter `"products"` kannst du beliebig viele Produktseiten eintragen (Name + URL). Die 5 Beispiele sind aktuelle OP17-Vorbestell-Links (2 davon aus der Schweiz: The Mana Shop, HOLYGRADE). Ergänze/entferne nach Belieben.

### Keywords
`unavailable_keywords` und `available_keywords` bestimmen, wie der Status erkannt wird. Falls ein Shop nicht korrekt erkannt wird, schau dir den Seitentext an (z.B. per Browser "Seitenquelltext anzeigen") und ergänze das passende Wort/Phrase in der jeweiligen Liste.

### E-Mail einrichten (Beispiel Gmail)
1. Google-Konto → Sicherheit → "App-Passwörter" aktivieren (2FA muss an sein)
2. Neues App-Passwort erstellen, in `config.json` unter `sender_password` eintragen
3. `sender_email` = dein Gmail, `recipient_email` = wohin die Meldung soll

Andere Anbieter: `smtp_server`/`smtp_port` entsprechend anpassen (z.B. Outlook: `smtp-mail.outlook.com`, Port 587).

### Telegram einrichten
1. In Telegram mit **@BotFather** chatten → `/newbot` → Namen vergeben → du erhältst einen **Bot Token**
2. Mit deinem neuen Bot einmal `/start` schreiben (damit er dir schreiben darf)
3. Deine **Chat-ID** herausfinden: `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` im Browser öffnen, nachdem du dem Bot geschrieben hast → `chat.id` im JSON ablesen
4. Beides in `config.json` unter `telegram` eintragen

Falls du nur einen Kanal willst: den anderen einfach auf `"enabled": false` setzen.

## 3. Ausführen

**Einmaliger Test-Check:**
```bash
python tracker.py --once
```

**Dauerbetrieb** (prüft alle `check_interval_minutes`, Standard 15 Min.):
```bash
python tracker.py
```

Beim allerersten Durchlauf wird nur der Ausgangsstatus gespeichert (keine Meldung), damit du nicht sofort eine Nachricht für den aktuellen Zustand bekommst. Ab dem zweiten Check gibt's bei jeder Statusänderung eine Meldung.

Der Status wird in `state.json` gespeichert (wird automatisch erstellt).

## 4. Dauerhaft laufen lassen — auch wenn dein PC aus ist (GitHub Actions)

Das ist die empfohlene Variante: läuft komplett in der Cloud, kostenlos, unabhängig von deinem Rechner.

### Einmalige Einrichtung

1. **GitHub-Account** erstellen (falls noch keiner vorhanden): [github.com](https://github.com)

2. **Neues Repository** erstellen, z.B. `op17-tracker` — kann **privat** sein (empfohlen, da URLs/Konfiguration drin sind)

3. Alle Projektdateien in dieses Repository hochladen (inkl. des Ordners `.github/workflows/tracker.yml` — der muss genau in diesem Pfad liegen). Am einfachsten über die GitHub-Weboberfläche: "Add file" → "Upload files" → alle Dateien + Ordnerstruktur reinziehen.

   Falls du Git installiert hast, geht's auch per Terminal:
   ```bash
   cd op17_tracker
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/DEIN-USERNAME/op17-tracker.git
   git push -u origin main
   ```

4. **Wichtig — Zugangsdaten NICHT in `config.json` eintragen**, wenn du sie hochlädst. Stattdessen als **GitHub Secrets** hinterlegen (sicherer, nicht öffentlich einsehbar, auch bei privatem Repo empfehlenswert):

   Im Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**, und diese 5 Secrets anlegen:
   - `EMAIL_SENDER` → deine Absender-E-Mail
   - `EMAIL_PASSWORD` → dein App-Passwort
   - `EMAIL_RECIPIENT` → wohin die Meldung soll
   - `TELEGRAM_BOT_TOKEN` → dein Bot-Token
   - `TELEGRAM_CHAT_ID` → deine Chat-ID

   Diese Secrets überschreiben automatisch die Platzhalter in `config.json` — die Datei kann also mit den `DEIN_...`-Platzhaltern hochgeladen werden, das ist kein Problem.

5. **Actions aktivieren:** Im Repo auf den Tab **Actions** klicken → falls gefragt, Workflows aktivieren.

6. **Testen:** Tab **Actions** → "OP17 Tracker" auswählen → **Run workflow** (manueller Start-Button) → Lauf abwarten und Log prüfen, ob alles grün ist.

### Was danach automatisch passiert

- Der Workflow läuft automatisch **alle 15 Minuten** (Zeitplan steht in `.github/workflows/tracker.yml`, per Cron-Syntax anpassbar)
- Bei einer Statusänderung bekommst du E-Mail + Telegram — unabhängig davon, ob dein PC an oder aus ist
- Der erkannte Status wird nach jedem Lauf automatisch als `state.json` zurück ins Repo committet, damit der nächste Lauf weiss, was sich geändert hat

### Intervall ändern
In `.github/workflows/tracker.yml` die Zeile `cron: "*/15 * * * *"` anpassen (z.B. `*/30 * * * *` für 30 Min.). GitHub Actions ist bei kostenlosen Konten ausreichend grosszügig limitiert für diesen Anwendungsfall (wenige Läufe à Sekunden, alle 15 Min.).

---

## Alternative: Lokal laufen lassen (nur wenn PC an ist)

Falls du es doch lieber lokal betreiben willst:

- **Windows:** Task Planer, Aufgabe die `python tracker.py --once` alle 15 Min. ausführt
- **Mac/Linux:** Cronjob, z.B. `*/15 * * * * cd /pfad/zum/projekt && python3 tracker.py --once`
- **Alternative:** `python tracker.py` (ohne `--once`) einfach in einem Terminal/Screen/tmux dauerhaft laufen lassen

## Hinweise
- Manche Shops nutzen JavaScript, um den Warenkorb-Button erst nachträglich zu laden – dann liefert der einfache HTML-Abruf ggf. nicht den echten Status. Falls ein Shop dauerhaft "unbekannt" zeigt, sag Bescheid, dann bauen wir für diesen Shop eine spezifische Erkennung (CSS-Selektor) statt der generischen Keyword-Suche.
- Bitte nicht zu kurze Check-Intervalle wählen (z.B. nicht unter 5 Min.), um die Shops nicht unnötig zu belasten bzw. nicht geblockt zu werden.
