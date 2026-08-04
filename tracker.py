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
    )
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
    Lädt die Seite und bestimmt den Status anhand von Schlüsselwörtern.
    Rückgabe: "verfügbar", "ausverkauft" oder "unbekannt"
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Fehler beim Abrufen von {url}: {e}")
        return "fehler"

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True).lower()

    unavailable_kw = config["unavailable_keywords"]
    available_kw = config["available_keywords"]

    is_unavailable = any(kw in text for kw in unavailable_kw)
    is_available = any(kw in text for kw in available_kw)

    # "nicht verfügbar" schlägt "verfügbar" -> zuerst negative Keywords prüfen
    if is_unavailable:
        return "ausverkauft"
    if is_available:
        return "verfügbar"
    return "unbekannt"


def run_check(config: dict, state: dict) -> dict:
    print(f"\n=== Check um {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    for product in config["products"]:
        name = product["name"]
        url = product["url"]

        new_status = check_status(url, config)
        old_status = state.get(url, {}).get("status")

        print(f"  {name}: {old_status} -> {new_status}")

        # Beim allerersten Check nur Status speichern, nicht benachrichtigen,
        # damit man nicht sofort für den Ausgangszustand eine Meldung bekommt.
        first_check = url not in state

        if not first_check and new_status != old_status:
            subject = f"🔔 Statusänderung: {name}"
            body = (
                f"Produkt: {name}\n"
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
