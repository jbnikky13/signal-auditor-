"""Candle storage. Yahoo 1m only covers ~7 days, so every fetch is merged into a local cache.
Broker/TradingView CSV imports are stored separately and always win over Yahoo on overlaps."""
import pandas as pd
import config

KEEP = ["High", "Low", "Close"]


def _utc_index(idx):
    idx = pd.to_datetime(idx)
    return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")


def _read(path):
    if not path.exists():
        return pd.DataFrame(columns=KEEP)
    df = pd.read_csv(path, index_col=0)
    df.index = _utc_index(df.index)
    return df[KEEP]


def _merge(a, b):
    df = pd.concat([a, b])
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_yahoo(sym):
    """Use the same canonical ticker map and candle provider as MercuryEdge."""
    from datetime import datetime, timedelta, timezone
    from market_data import get_candles
    end = datetime.now(timezone.utc)
    frame = get_candles(sym, end - timedelta(days=7), end, interval="1m")
    if frame is None or frame.empty:
        return pd.DataFrame(columns=KEEP)
    frame = frame.rename(columns={c: c.capitalize() for c in frame.columns})
    return frame[KEEP].dropna()


def load(sym, refresh=True):
    ypath = config.CANDLE_DIR / f"{sym}.csv"
    ipath = config.CANDLE_DIR / f"{sym}.import.csv"
    ycache = _read(ypath)
    if refresh:
        try:
            ycache = _merge(ycache, fetch_yahoo(sym))
            ycache.to_csv(ypath)
        except Exception as e:
            print(f"[warn] {sym}: yahoo fetch failed: {e}")
    return _merge(ycache, _read(ipath))


def import_csv(sym, path, tz="UTC"):
    """TradingView / MT5 / Dukascopy CSV with time + high/low/close columns.
    tz = timezone of naive timestamps (MT5 uses broker server time!)."""
    raw = pd.read_csv(path, sep=None, engine="python")
    cols = {c.lower().strip("<> "): c for c in raw.columns}
    if "date" in cols and "time" in cols:
        t = pd.to_datetime(raw[cols["date"]].astype(str) + " " + raw[cols["time"]].astype(str))
    else:
        key = next(k for k in ("time", "datetime", "timestamp", "date") if k in cols)
        s = raw[cols[key]]
        t = pd.to_datetime(s, unit="s", utc=True) if pd.api.types.is_numeric_dtype(s) else pd.to_datetime(s)
    t = pd.DatetimeIndex(t)
    t = t.tz_localize(tz) if t.tz is None else t
    df = pd.DataFrame({k: raw[cols[k.lower()]].values for k in KEEP}, index=t.tz_convert("UTC"))
    ipath = config.CANDLE_DIR / f"{sym}.import.csv"
    _merge(_read(ipath), df).to_csv(ipath)
    print(f"Imported {len(df)} candles for {sym}")
