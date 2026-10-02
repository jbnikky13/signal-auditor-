"""Read MercuryEdge signals from Telegram and store normalized setups.

The authenticated Telegram user session is used to read the conversation with
TG_CHANNEL (which may be a bot username such as @MercuryEdgeSignalsBot).
"""
import asyncio
import os
from datetime import timezone

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

    # Accept a raw Telethon StringSession and tolerate accidental copying of
    # the printed "TG_SESSION:" label or surrounding whitespace/quotes.
    session = session.strip()
    if session.startswith("TG_SESSION:"):
        session = session.split(":", 1)[1].strip()
    session = session.strip('"').strip("'").strip()

    if len(session) < 50:
        raise RuntimeError(
            "TG_SESSION looks incomplete. Store only the long StringSession value "
            "from Colab, without 'TG_SESSION:' or quotes."
        )

    try:
        return TelegramClient(StringSession(session), int(api_id), api_hash)
    except Exception as exc:
        raise RuntimeError(
            "TG_SESSION is not a valid Telethon StringSession. Regenerate it in "
            "Colab and replace the GitHub secret with the raw session string."
        ) from exc


def _source():
    source = os.getenv("TG_CHANNEL")
    if not source:
        raise RuntimeError("TG_CHANNEL is required")
    # Accept either @username or username.
    return source.strip()


async def _pull(limit):
    client = _client()
    await client.start()
    try:
        source = _source()

        # Resolve the source explicitly. This supports a public bot username
        # such as @MercuryEdgeSignalsBot as well as a channel username.
        entity = await client.get_entity(source)

        messages = []
        async for msg in client.iter_messages(entity, limit=limit):
            if not msg.message:
                continue
            messages.append(msg)

        messages.reverse()
        total = 0

        for msg in messages:
            sigs = parse_export(msg.message, config.EXPORT_TZ)
            if not sigs:
                continue

            # Telegram's message timestamp is authoritative for the signal.
            ts = msg.date.astimezone(timezone.utc).isoformat()
            for signal in sigs:
                signal["ts_utc"] = ts

            total += insert_signals(sigs)

        print(
            f"Telegram source={source}: scanned {len(messages)} messages; "
            f"inserted {total} new signals"
        )
        return total
    finally:
        await client.disconnect()


def pull(limit=100):
    return asyncio.run(_pull(limit))


def main(backfill=0):
    return pull(backfill or 100)
