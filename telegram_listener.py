"""Telegram capture for GitHub Actions and local use.

Uses Telethon StringSession so a pre-authenticated session can run headlessly.
"""
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

import config
from db import insert_signals
from signal_parser import parse_export

def _client():
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    session = os.getenv("TG_SESSION")
    if not api_id or not api_hash or not session:
        raise RuntimeError("TG_API_ID, TG_API_HASH and TG_SESSION are required")
    return TelegramClient(StringSession(session), int(api_id), api_hash)

def _channel():
    channel = os.getenv("TG_CHANNEL")
    if not channel:
        raise RuntimeError("TG_CHANNEL is required")
    return channel

async def _pull(limit):
    client = _client()
    await client.start()
    try:
        messages = []
        async for msg in client.iter_messages(_channel(), limit=limit):
            if not msg.message:
                continue
            messages.append(msg)
        messages.reverse()
        total = 0
        for msg in messages:
            sigs = parse_export(msg.message, config.EXPORT_TZ)
            # Telegram's message timestamp is authoritative for the signal event.
            ts = msg.date.astimezone(__import__("datetime").timezone.utc).isoformat()
            for s in sigs:
                s["ts_utc"] = ts
            total += insert_signals(sigs)
        print(f"Telegram: scanned {len(messages)} messages; inserted {total} new signals")
        return total
    finally:
        await client.disconnect()

def pull(limit=100):
    import asyncio
    return asyncio.run(_pull(limit))

def main(backfill=0):
    return pull(backfill or 100)
