# Signal Auditor

Captures trading signals, pulls 1-minute candles, and records which level was
touched FIRST (TP1, TP2 or SL). A candle that touches both TP and SL is marked
AMBIGUOUS, never guessed.

## Setup
    python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env      # then edit it

## Use
    python run.py ingest signals.txt        # paste Telegram text (with the header lines) into a file
    python run.py settle                    # fetch candles + settle
    python run.py report

## Automatic capture
    python run.py listen --backfill 200     # needs TG_API_ID / TG_API_HASH / TG_CHANNEL in .env

## Schedule (every 4 hours; Yahoo 1m data only goes back ~7 days)
    0 */4 * * * cd /path/to/signal_auditor && ./venv/bin/python run.py daily >> data/log.txt 2>&1
Windows: Task Scheduler -> run `venv\Scripts\python.exe run.py daily` every 4 hours.

## Better data
    python run.py import-csv EURUSD export.csv --tz UTC
    python run.py settle --redo
Imported candles override Yahoo. MT5 timestamps are broker server time; pass its timezone.

## Outcomes
TP2 | TP1_THEN_SL | TP1_ONLY | SL | AMBIGUOUS_SL_TP1_SAME_CANDLE | TP1_THEN_AMBIGUOUS
OPEN | NO_RESOLUTION | NO_DATA | DATA_GAP | DATA_MISMATCH (feed price differs from signal entry,
e.g. spot vs futures; import broker candles instead)

Signals are assumed filled at the stated entry on the minute after publication.
Shorts exit on the ask (feed + SPREAD_PIPS). Paper analysis only, not financial advice.
