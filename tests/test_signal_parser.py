from datetime import datetime, timezone

import db
from signal_parser import parse_export


BATCHES = ("OVERNIGHT", "MORNING", "AFTERNOON", "EVENING")


def make_message(batch):
    return f"""🧠 MERCURYEDGE
{batch} SIGNAL • 1 SETUP
━━━━━━━━━━━━━━━━━━━━
SETUP #1
BUY EURUSD @ 1.1000
TP1: 1.1100
TP2: 1.1200
SL: 1.0900
SCORE: 78/100
HIT RATE: 62%
ANALOGUES: 55
REGIME: BULLISH / NORMAL
CONFIRMATION: +1
Timestamp: 2026-10-09 10:30
Paper/research signals only.
"""


def test_parser_recognizes_all_four_batch_labels():
    for batch in BATCHES:
        parsed = parse_export(make_message(batch))
        assert len(parsed) == 1
        assert parsed[0]["batch"] == batch
        assert parsed[0]["symbol"] == "EURUSD"
        assert parsed[0]["direction"] == "BUY"
        assert parsed[0]["entry"] == 1.1
        assert parsed[0]["tp1"] == 1.11
        assert parsed[0]["tp2"] == 1.12
        assert parsed[0]["sl"] == 1.09


def test_batch_is_persisted_in_database_for_each_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test-audit.db")
    parsed = []
    for batch in BATCHES:
        row = parse_export(make_message(batch))[0]
        # Unique timestamps keep each sample independent in the UNIQUE index.
        row["ts_utc"] = datetime(
            2026, 10, 9, 10, 30 + BATCHES.index(batch), tzinfo=timezone.utc
        ).isoformat()
        parsed.append(row)

    inserted = db.insert_signals(parsed)
    assert inserted == 4
    rows = db.open_signals()
    assert {row["batch"] for row in rows} == set(BATCHES)
