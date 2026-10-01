import os
import requests
import config  # noqa: F401  (loads .env)


def send(text):
    tok, chat = os.getenv("BOT_TOKEN"), os.getenv("BOT_CHAT_ID")
    if not tok or not chat:
        return False
    for i in range(0, len(text), 3500):
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id": chat, "text": text[i:i + 3500]}, timeout=20)
    return True
