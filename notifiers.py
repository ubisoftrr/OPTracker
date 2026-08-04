"""
Benachrichtigungs-Funktionen: E-Mail (SMTP) und Telegram (Bot API).
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests


def send_email(config: dict, subject: str, body: str) -> None:
    """Sendet eine E-Mail über SMTP (z.B. Gmail mit App-Passwort)."""
    email_cfg = config["email"]
    if not email_cfg.get("enabled"):
        return

    msg = MIMEMultipart()
    msg["From"] = email_cfg["sender_email"]
    msg["To"] = email_cfg["recipient_email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
            server.starttls(context=context)
            server.login(email_cfg["sender_email"], email_cfg["sender_password"])
            server.sendmail(
                email_cfg["sender_email"],
                email_cfg["recipient_email"],
                msg.as_string(),
            )
        print(f"[E-Mail] Gesendet: {subject}")
    except Exception as e:
        print(f"[E-Mail] Fehler beim Senden: {e}")


def send_telegram(config: dict, text: str) -> None:
    """Sendet eine Nachricht über einen Telegram-Bot."""
    tg_cfg = config["telegram"]
    if not tg_cfg.get("enabled"):
        return

    url = f"https://api.telegram.org/bot{tg_cfg['bot_token']}/sendMessage"
    payload = {"chat_id": tg_cfg["chat_id"], "text": text}

    try:
        resp = requests.post(url, data=payload, timeout=15)
        if resp.status_code == 200:
            print("[Telegram] Nachricht gesendet")
        else:
            print(f"[Telegram] Fehler: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[Telegram] Fehler beim Senden: {e}")


def notify_all(config: dict, subject: str, body: str) -> None:
    """Schickt die Meldung über alle aktivierten Kanäle raus."""
    send_email(config, subject, body)
    send_telegram(config, f"{subject}\n\n{body}")
