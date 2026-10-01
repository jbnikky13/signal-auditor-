# Signal Auditor

Signal Auditor captures MercuryEdge-style trading signals, stores them in SQLite, fetches 1-minute market candles, and determines which level was touched first.

It is **paper analysis only**. It does not place trades.

## Repository layout

```
.github/workflows/audit.yml  # scheduled GitHub Actions job
config.py                    # configuration and symbol mappings
signal_parser.py             # MercuryEdge message parser
telegram_listener.py         # Telegram capture via Telethon StringSession
data.py                      # candle fetching/import/cache
db.py                        # SQLite schema and persistence
settle.py                    # first-touch settlement engine
report.py                    # audit statistics
notify.py                    # optional Telegram report delivery
run.py                       # command-line entry point
signals.txt                  # optional manual signal export
data/                        # runtime data; generated locally/Actions
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then fill in the Telegram values if automatic capture is wanted.

## Commands

```bash
python run.py ingest signals.txt
python run.py pull --limit 200
python run.py settle
python run.py report --csv data/audit-results.csv
python run.py daily
```

## GitHub Actions

The workflow is intentionally located at:

```
.github/workflows/audit.yml
```

It runs:
- manually with **Run workflow**
- every 4 hours
- when the core audit code/workflow changes

Required repository **Secrets**:
- `TG_API_ID`
- `TG_API_HASH`
- `TG_CHANNEL`
- `TG_SESSION`

Optional secrets:
- `BOT_TOKEN`
- `BOT_CHAT_ID`

Optional repository **Variables**:
- `EXPORT_TZ`
- `SPREAD_PIPS`
- `MAX_HOURS`

The workflow has `contents: write` permission so it can persist audit outputs.

## Settlement rules

- The signal timestamp is the event timestamp.
- The minute containing publication is skipped; evaluation starts on the following minute.
- TP1/TP2/SL are evaluated using OHLC data.
- A candle touching TP1 and SL before TP1 resolution is marked ambiguous.
- A candle touching TP2 and SL after TP1 is marked ambiguous.
- Missing/gapped/mismatched data is not silently converted into a win or loss.
- Shorts include the configured spread adjustment.
- Imported broker/TradingView candles override Yahoo candles on overlapping timestamps.

## Data limitations

Yahoo 1-minute history is limited. For older signals, import broker/TradingView/MT5 candles:

```bash
python run.py import-csv EURUSD export.csv --tz UTC
python run.py settle --redo
```

For MT5 exports, pass the broker-server timezone for naive timestamps.

## Outcomes

`TP2`, `TP1_THEN_SL`, `TP1_ONLY`, `SL`, `AMBIGUOUS_SL_TP1_SAME_CANDLE`, `TP1_THEN_AMBIGUOUS`, `OPEN`, `NO_RESOLUTION`, `NO_DATA`, `DATA_GAP`, `DATA_MISMATCH`.

No financial execution is performed.
