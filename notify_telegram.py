"""Send the latest audit results to the configured Telegram bot chat."""
import os
from pathlib import Path

import requests

MAX_MESSAGE = 4096


def _required():
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("BOT_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("BOT_TOKEN and BOT_CHAT_ID are required for Telegram delivery")
    return token, chat_id


def _send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": text[:MAX_MESSAGE],
        "disable_web_page_preview": True,
    }, timeout=30)
    r.raise_for_status()


def _send_document(token, chat_id, path, caption):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(path, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption[:1024]},
            files={"document": (Path(path).name, f, "text/plain")},
            timeout=60,
        )
    r.raise_for_status()


def main():
    token, chat_id = _required()
    report = Path("data/audit-report.txt")
    csv = Path("data/audit-results.csv")

    if not report.exists():
        raise RuntimeError("data/audit-report.txt was not generated")

    text = report.read_text(encoding="utf-8").strip()
    _send_message(token, chat_id, "📊 SIGNAL AUDITOR\n\n" + text)

    if csv.exists():
        _send_document(token, chat_id, csv, "Signal Auditor detailed results (CSV)")

    print("Audit report delivered to Telegram.")


if __name__ == "__main__":
    main()
