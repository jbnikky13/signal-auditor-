import sqlite3
from contextlib import contextmanager
import pandas as pd
from config import DB_PATH
from signal_parser import levels_ok

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL, batch TEXT, setup_no INTEGER,
  symbol TEXT, direction TEXT, entry REAL, tp1 REAL, tp2 REAL, sl REAL,
  score INTEGER, hit_rate REAL, analogues INTEGER, regime TEXT,
  confirmation INTEGER, agreement INTEGER,
  UNIQUE(ts_utc, symbol, direction, entry)
);
CREATE TABLE IF NOT EXISTS results(
  signal_id INTEGER PRIMARY KEY REFERENCES signals(id),
  outcome TEXT, final INTEGER, t_hit_utc TEXT, mins REAL, tp1_t_utc TEXT,
  mae_pips REAL, mfe_pips REAL, back_to_entry INTEGER, note TEXT, checked_at TEXT
);
"""

COLS = ["ts_utc", "batch", "setup_no", "symbol", "direction", "entry", "tp1", "tp2",
        "sl", "score", "hit_rate", "analogues", "regime", "confirmation", "agreement"]


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


META = ["batch", "setup_no", "score", "hit_rate", "analogues", "regime", "confirmation", "agreement"]


def insert_signals(sigs):
    """Insert new signals. For signals already stored, back-fill/correct the
    descriptive fields (score, hit rate, regime, ...) without touching levels
    or results. A None never overwrites an existing value."""
    n = 0
    with connect() as con:
        for s in sigs:
            cur = con.execute(
                f"INSERT OR IGNORE INTO signals({','.join(COLS)}) VALUES({','.join('?'*len(COLS))})",
                [s.get(c) for c in COLS])
            n += cur.rowcount
            con.execute(
                "UPDATE signals SET " + ",".join(f"{c}=COALESCE(?,{c})" for c in META) +
                " WHERE ts_utc=? AND symbol=? AND direction=? AND entry=?",
                [s.get(c) for c in META] + [s["ts_utc"], s["symbol"], s["direction"], s["entry"]])
    return n


def open_signals(redo=False):
    q = "SELECT s.* FROM signals s LEFT JOIN results r ON r.signal_id=s.id"
    if not redo:
        q += " WHERE r.signal_id IS NULL OR r.final=0"
    with connect() as con:
        return [dict(r) for r in con.execute(q + " ORDER BY s.ts_utc")]


def save_result(signal_id, r):
    ts = lambda v: v.isoformat() if v is not None else None
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO results VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (signal_id, r["outcome"], int(r["final"]), ts(r.get("t_hit")), r.get("mins"),
             ts(r.get("tp1_t")), r.get("mae_pips"), r.get("mfe_pips"),
             None if r.get("back_to_entry") is None else int(r["back_to_entry"]),
             r.get("note", "")))


def results_df():
    with connect() as con:
        return pd.read_sql_query(
            "SELECT s.*, r.outcome, r.final, r.t_hit_utc, r.mins, r.tp1_t_utc, r.mae_pips, "
            "r.mfe_pips, r.back_to_entry, r.note FROM signals s "
            "JOIN results r ON r.signal_id=s.id ORDER BY s.ts_utc", con)


def purge_invalid():
    """Delete signals whose levels are impossible (e.g. TP1 == entry), such as
    rows created by the old comma-parsing bug, along with their results."""
    with connect() as con:
        rows = con.execute("SELECT id, direction, entry, tp1, tp2, sl FROM signals").fetchall()
        bad = [r["id"] for r in rows if not levels_ok(r["direction"], r["entry"], r["tp1"], r["tp2"], r["sl"])]
        for i in bad:
            con.execute("DELETE FROM results WHERE signal_id=?", (i,))
            con.execute("DELETE FROM signals WHERE id=?", (i,))
    return len(bad)
