"""One-off cleanup after the parser/symbol-map fix.

1. Deletes signals whose levels are impossible (e.g. TP1 == entry), which is
   what the old comma bug produced for NASDAQ / SPX / DJI / XAUUSD.
2. Clears NO_DATA / DATA_GAP / DATA_MISMATCH results so they are settled again
   with the new symbol map. Real results (TP/SL) are never touched.

Usage:
    python repair.py            # dry run, prints what would change
    python repair.py --apply
Then:
    python run.py pull --limit 300   # re-ingest the bad rows, parsed correctly
    python run.py settle
"""
import sys
import db
from signal_parser import levels_ok

apply = "--apply" in sys.argv

with db.connect() as con:
    rows = con.execute("SELECT id, symbol, direction, entry, tp1, tp2, sl FROM signals").fetchall()
    bad = [r for r in rows if not levels_ok(r["direction"], r["entry"], r["tp1"], r["tp2"], r["sl"])]
    print(f"{len(bad)} signals with invalid levels:")
    for r in bad:
        print(f"  #{r['id']} {r['direction']} {r['symbol']} entry={r['entry']} tp1={r['tp1']} tp2={r['tp2']} sl={r['sl']}")

    redo = con.execute(
        "SELECT s.id, s.symbol, r.outcome FROM results r JOIN signals s ON s.id=r.signal_id "
        "WHERE r.outcome IN ('NO_DATA','DATA_GAP','DATA_MISMATCH')").fetchall()
    bad_ids = {r["id"] for r in bad}
    redo = [r for r in redo if r["id"] not in bad_ids]
    print(f"{len(redo)} valid signals with no-data results to re-settle:")
    for r in redo:
        print(f"  #{r['id']} {r['symbol']} ({r['outcome']})")

    if apply:
        for r in bad:
            con.execute("DELETE FROM results WHERE signal_id=?", (r["id"],))
            con.execute("DELETE FROM signals WHERE id=?", (r["id"],))
        for r in redo:
            con.execute("DELETE FROM results WHERE signal_id=?", (r["id"],))
        print("Applied.")
    else:
        print("Dry run. Re-run with --apply to make changes.")
