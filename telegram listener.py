"""Captures MercuryEdge signals live (and backfills history) from Telegram.
First run asks for your phone number + login code and saves data/session.session."""
import asyncio
import os
import pandas as pd
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import config
import db
from signal_parser import parse_message

API_ID = int(os.getenv("TG_API_ID") or 0)
API_HASH = os.getenv("TG_API_HASH", "")
CHANNEL = os.getenv("TG_CHANNEL", "")
SESSION = str(config.DATA_DIR / "session")


def _client():
    # TG_SESSION (a string secret) lets this run headless, e.g. on GitHub Actions
    ss = os.getenv("TG_SESSION")
    return TelegramClient(StringSession(ss) if ss else SESSION, API_ID, API_HASH)


def _handle(msg):
    text = msg.message or ""
    if "MERCURYEDGE" not in text.upper():
        return 0
    return db.insert_signals(parse_message(text, pd.Timestamp(msg.date)))


async def _run(backfill):
    ch = int(CHANNEL) if CHANNEL.lstrip("-").isdigit() else CHANNEL
    async with _client() as client:
        if backfill:
            n = 0
            async for m in client.iter_messages(ch, limit=backfill):
                n += _handle(m)
            print(f"Backfill: {n} new setups saved")
        print(f"Listening to {CHANNEL} ... (Ctrl+C to stop)")

        @client.on(events.NewMessage(chats=ch))
        async def on_new(event):
            n = _handle(event.message)
            if n:
                print(f"{pd.Timestamp.now(tz='UTC'):%F %T} saved {n} new setups")

        await client.run_until_disconnected()


def main(backfill=0):
    if not (API_ID and API_HASH and CHANNEL):
        raise SystemExit("Set TG_API_ID, TG_API_HASH and TG_CHANNEL in .env")
    asyncio.run(_run(backfill))


async def _pull(limit):
    ch = int(CHANNEL) if CHANNEL.lstrip("-").isdigit() else CHANNEL
    async with _client() as client:
        n = 0
        async for m in client.iter_messages(ch, limit=limit):
            n += _handle(m)
        print(f"Pulled last {limit} messages: {n} new setups saved")


def pull(limit=100):
    """One-shot fetch (no listening) - used by the scheduled GitHub job."""
    if not (API_ID and API_HASH and CHANNEL):
        raise SystemExit("Set TG_API_ID, TG_API_HASH and TG_CHANNEL")
    asyncio.run(_pull(limit))
