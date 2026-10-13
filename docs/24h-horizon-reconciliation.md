# 24-hour horizon reconciliation — provisional review

Review date: 2026-10-13  
Canonical source: `data/audit-results.csv`  
Policy: `MAX_HOURS=24` (merged to main in PR #2)  
Status: **timestamp-based provisional review only; not a candle-verified resettlement**.

## Why the canonical outcomes were not overwritten

The existing CSV stores outcomes and timestamps, but not the underlying minute OHLC candles. The candle cache is excluded from Git by `.gitignore` (`data/candles/*.csv`), and the Signal Auditor fetches only a rolling ~7-day Yahoo 1-minute window. The reviewed set includes signals from Sep 29–Oct 5, older than that rolling window as of Oct 13. The PR CI run had no candle artifact. Consequently, a fresh run cannot reconstruct the full historical paths for all records, and old labels must not be rewritten as if independently verified.

Import original broker/MT5/TradingView/Dukascopy minute candles for the relevant symbols and timestamps. For MT5 exports, supply the broker server timezone. Preserve the original files and record provider, timezone, instrument/ticker, and export time. Re-settle with the production spread, first-touch ordering, signal-candle exclusion, gap checks, and 24-hour cutoff.

## Provisional 24-hour review of the 11 horizon-affected records

See `data/24h-horizon-review-provisional.csv`. The timestamp-based interpretation is:
- IDs 11 and 219: TP1 occurred before expiry, but the recorded SL occurred after expiry; provisional result is `TP1_ONLY`.
- IDs 124, 121, 127, 128, 126, 125, 517, 519, and 520: the recorded outcome event (and, where present, TP1) occurs after the 24-hour cutoff; provisional result is `NO_RESOLUTION` pending candle verification.

This is not proof that every minute inside the window has valid coverage. Candle gaps, feed identity, spreads, and same-candle touches still need to be checked.

## Provisional baseline recalculation

The CSV contains 55 records: 53 with existing decided outcomes and 2 `DATA_MISMATCH` records. Reclassifying only the 11 horizon-affected records from their stored timestamps gives:

| Provisional class | Count |
|---|---:|
| TP2 | 13 |
| SL | 21 |
| TP1_THEN_SL | 5 |
| TP1_ONLY | 5 |
| NO_RESOLUTION | 9 |
| DATA_MISMATCH | 2 |
| Total | 55 |

Of the 44 provisionally resolved, non-mismatch records, TP1 was reached in 23 (52.3%). A simplified TP1-exit model based on each record's target distance relative to its stop distance gives +5.508R total / +0.125R per resolved trade. A simplified TP2-only model, excluding TP1_ONLY and NO_RESOLUTION records, gives +3.343R total / +0.086R per 39 eligible records.

These are **not verified live returns**. They use stored event timestamps and simplified fixed-R assumptions; they do not include execution/slippage/commission differences, partial-exit implementation, or candle-path verification. Do not use them to change live filters until candle-level resettlement and a chronological out-of-sample baseline are complete.

## NASDAQ feed mismatch

Rows 123 and 129 remain excluded. Signal Auditor's canonical `NASDAQ` mapping resolves to Yahoo `^IXIC`, matching MercuryEdge's current production config. The stored feed observations (~30,924 and ~31,019) differ materially from signal entries (~27,313 and ~27,439), which appear consistent with a different Nasdaq instrument/quote source. Do not silently remap the live strategy: identify the original signal provider/ticker first, then either map to the same instrument or retain `DATA_MISMATCH`.

## CADJPY reconciliation

Signal Auditor record 1223 is a CADJPY SELL at 06:56:33 UTC, entry 110.86, SL 110.99, marked SL at 08:45 UTC. MercuryEdge's journal contains a closely matching CADJPY SELL in the 06:00 UTC batch (entry 110.863998, SL 110.989818), still marked OPEN in that snapshot. Entry/stop match closely, but the timestamps differ by 56m33s. Treat it as a likely related setup, not a proven duplicate. Confirm Telegram publication time and inspect the archived CADJPY candles plus spread/first-touch rules before changing either ledger.

## Candle archive needed to finish

For each of the 11 horizon records and CADJPY, supply one-minute OHLC candles from shortly before the signal through at least the 24-hour cutoff (and enough adjacent data to test gaps/feed scale). Prioritize:
- Sep 29–Oct 6: USDCAD, GBPJPY, VIX, EURGBP, SPX, UKOIL
- Oct 7–10: RUSSELL2000, DXY, COPPER
- Oct 13: CADJPY
- NASDAQ: original source/ticker/quote evidence for rows 123 and 129; candles alone cannot resolve the instrument identity.

Accepted import format: timestamp/date+time and High, Low, Close columns (Open is recommended for provenance and later audit). Preserve the original timezone; convert only using the stated source timezone.
