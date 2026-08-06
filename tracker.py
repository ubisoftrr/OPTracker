"""
OP17 Verfügbarkeits-Tracker
============================
Prüft periodisch die in config.json hinterlegten Produktseiten und
benachrichtigt per E-Mail/Telegram, sobald sich der Status ändert
(insbesondere: ausverkauft -> verfügbar).

Nutzung:
    python tracker.py            # läuft dauerhaft im konfigurierten Intervall
    python tracker.py --once     # führt nur einen einzelnen Check aus
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from notifiers import notify_all

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8,fr;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def load_config() -> dict:
    """
    Lädt config.json (Produkte, Keywords) und überschreibt sensible Felder
    mit Umgebungsvariablen, falls vorhanden (z.B. in GitHub Actions über
    Secrets gesetzt). Für lokale Nutzung reicht es, die Werte direkt in
    config.json einzutragen.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    env_map = {
        ("email", "sender_email"): "EMAIL_SENDER",
        ("email", "sender_password"): "EMAIL_PASSWORD",
        ("email", "recipient_email"): "EMAIL_RECIPIENT",
        ("telegram", "bot_token"): "TELEGRAM_BOT_TOKEN",
        ("telegram", "chat_id"): "TELEGRAM_CHAT_ID",
    }

    for (section, key), env_var in env_map.items():
        value = os.environ.get(env_var)
        if value:
            config[section][key] = value

    return config


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_status(url: str, config: dict) -> str:
    """
    Lädt eine Shop-Seite (i.d.R. eine One-Piece-Kategorieseite) und prüft:
    1. Ist überhaupt ein Zielprodukt (OP17 / 3rd Anniversary Set) gelistet?
    2. Falls ja: wie ist der Verfügbarkeitsstatus?

    Rückgabe z.B.: "nicht gelistet", "gelistet - verfügbar",
    "gelistet - ausverkauft", "gelistet - status unklar", "fehler"
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "?"
        print(f"  Fehler beim Abrufen von {url}: HTTP {status_code}")
        return f"fehler (HTTP {status_code})"
    except requests.exceptions.Timeout:
        print(f"  Fehler beim Abrufen von {url}: Zeitüberschreitung")
        return "fehler (timeout)"
    except Exception as e:
        print(f"  Fehler beim Abrufen von {url}: {e}")
        return "fehler"

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True).lower()

    target_kw = config["target_keywords"]
    unavailable_kw = config["unavailable_keywords"]
    available_kw = config["available_keywords"]

    is_listed = any(kw in text for kw in target_kw)
    if not is_listed:
        return "nicht gelistet"

    is_unavailable = any(kw in text for kw in unavailable_kw)
    is_available = any(kw in text for kw in available_kw)

    # "ausverkauft" schlägt "verfügbar", falls beide Begriffe irgendwo auf
    # der Seite vorkommen (z.B. weil andere Produkte auf derselben Seite
    # noch verfügbar sind) -> im Zweifel eher konservativ einstufen.
    if is_unavailable and not is_available:
        return "gelistet - ausverkauft"
    if is_available and not is_unavailable:
        return "gelistet - verfügbar"
    return "gelistet - status unklar"


def run_check(config: dict, state: dict) -> dict:
    print(f"\n=== Check um {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    for shop in config["shops"]:
        name = shop["name"]
        url = shop["url"]

        new_status = check_status(url, config)
        old_entry = state.get(url, {})
        old_status = old_entry.get("status")

        print(f"  {name}: {old_status} -> {new_status}")

        is_error = new_status.startswith("fehler")

        if is_error:
            # Fehler (Bot-Schutz, Timeout, temporär down, ...) überschreiben
            # den zuletzt bekannten ECHTEN Status nicht. So lösen kurzzeitige
            # Abrufprobleme keine falschen "Statusänderung"-Meldungen aus,
            # wenn die Seite beim nächsten Check wieder normal antwortet.
            state[url] = {
                "name": name,
                "status": old_status,  # unverändert lassen
                "last_error": new_status,
                "last_checked": datetime.now().isoformat(),
            }
            continue

        # Beim allerersten erfolgreichen Check nur Status speichern, nicht
        # benachrichtigen, damit man nicht sofort für den Ausgangszustand
        # eine Meldung bekommt.
        first_check = old_status is None

        # Bei jeder ECHTEN Statusänderung benachrichtigen (neu gelistet,
        # verfügbar, ausverkauft, nicht mehr gelistet, ...). Fehler lösen
        # das hier NICHT aus, weil sie oben per "continue" komplett
        # übersprungen werden und den gespeicherten Status nie verändern.
        if not first_check and new_status != old_status:
            if new_status == "gelistet - verfügbar":
                subject = f"✅ JETZT VERFÜGBAR: {name}"
            elif new_status == "nicht gelistet":
                subject = f"⚠️ Nicht mehr gelistet: {name}"
            elif old_status in (None, "nicht gelistet"):
                subject = f"🆕 Neu gelistet: {name}"
            else:
                subject = f"🔔 Statusänderung: {name}"

            body = (
                f"Shop: {name}\n"
                f"Neuer Status: {new_status}\n"
                f"Vorheriger Status: {old_status}\n"
                f"Link: {url}\n"
                f"Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            notify_all(config, subject, body)

        state[url] = {
            "name": name,
            "status": new_status,
            "last_checked": datetime.now().isoformat(),
        }

    save_state(state)
    return state


def main():
    parser = argparse.ArgumentParser(description="OP17 Verfügbarkeits-Tracker")
    parser.add_argument(
        "--once", action="store_true", help="Nur einen einzelnen Check ausführen"
    )
    args = parser.parse_args()

    config = load_config()
    state = load_state()

    if args.once:
        run_check(config, state)
        return

    interval_seconds = config["check_interval_minutes"] * 60
    print(f"Starte Dauerbetrieb, Intervall: {config['check_interval_minutes']} Min.")
    while True:
        state = run_check(config, state)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
