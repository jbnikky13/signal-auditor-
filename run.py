#!/usr/bin/env python3
"""
python run.py ingest signals.txt            # load pasted Telegram text
python run.py listen [--backfill 200]       # capture live from Telegram
python run.py pull [--limit 100]            # one-shot fetch of recent messages
python run.py import-csv EURUSD file.csv --tz UTC   # broker/TradingView candles
python run.py settle [--redo] [--no-fetch]  # fetch candles + settle open signals
python run.py report [--csv out.csv]
python run.py daily                         # settle + report + push to your bot
"""
import argparse
import config
import db
import data
import report
import notify
import settle as st
from signal_parser import parse_export


def cmd_ingest(a):
    sigs = parse_export(open(a.file, encoding="utf-8").read(), a.tz or config.EXPORT_TZ)
    print(f"Parsed {len(sigs)} setups, {db.insert_signals(sigs)} new")


def cmd_settle(a):
    sigs = db.open_signals(redo=a.redo)
    if not sigs:
        print("Nothing to settle")
        return []
    candles = {}
    for sym in sorted({s["symbol"] for s in sigs}):
        try:
            candles[sym] = data.load(sym, refresh=not a.no_fetch)
        except Exception as e:
            print(f"[warn] {sym}: {e}")
            candles[sym] = None
    newly = []
    for s in sigs:
        r = st.settle(s, candles.get(s["symbol"]), config.SPREAD_PIPS, config.MAX_HOURS)
        db.save_result(s["id"], r)
        print(f"{s['ts_utc'][:16]}  {s['symbol']:7} {s['direction']:4} -> {r['outcome']}"
              f"{'' if r['final'] else ' (open)'}  {r['note']}")
        if r["final"]:
            newly.append(f"{s['symbol']} {s['direction']} @ {s['entry']}: {r['outcome']}")
    return newly


def cmd_report(a):
    txt = report.build()
    print(txt)
    if a.csv:
        db.results_df().to_csv(a.csv, index=False)
        print(f"\nSaved {a.csv}")
    return txt


def cmd_daily(a):
    a.redo, a.no_fetch = False, False
    newly = cmd_settle(a)
    a.csv = None
    txt = cmd_report(a)
    if newly:
        notify.send("Newly settled:\n" + "\n".join(newly) + "\n\n" + txt)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest"); p.add_argument("file"); p.add_argument("--tz"); p.set_defaults(f=cmd_ingest)
    p = sub.add_parser("settle"); p.add_argument("--redo", action="store_true"); p.add_argument("--no-fetch", action="store_true"); p.set_defaults(f=cmd_settle)
    p = sub.add_parser("report"); p.add_argument("--csv"); p.set_defaults(f=cmd_report)
    p = sub.add_parser("daily"); p.set_defaults(f=cmd_daily)
    p = sub.add_parser("import-csv"); p.add_argument("symbol"); p.add_argument("file"); p.add_argument("--tz", default="UTC")
    p.set_defaults(f=lambda a: data.import_csv(a.symbol.upper(), a.file, a.tz))
    p = sub.add_parser("listen"); p.add_argument("--backfill", type=int, default=0)
    p.set_defaults(f=lambda a: __import__("telegram_listener").main(a.backfill))
    p = sub.add_parser("pull"); p.add_argument("--limit", type=int, default=100)
    p.set_defaults(f=lambda a: __import__("telegram_listener").pull(a.limit))
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
