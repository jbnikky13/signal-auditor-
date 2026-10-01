"""Parses MercuryEdge-style signal messages into dicts."""
import re
import pandas as pd

HDR = re.compile(r"MercuryEdge,\s*\[(\w{3,9} \d{1,2}, \d{4}) at (\d{1,2}:\d{2})\]")
F = {
    "core": re.compile(r"\b(BUY|SELL)\s+([A-Z0-9]+)\s*@\s*([\d.]+)"),
    "tp1": re.compile(r"TP1\.?\s*([\d.]+)"),
    "tp2": re.compile(r"TP2\.?\s*([\d.]+)"),
    "sl": re.compile(r"\bSL\.?\s*([\d.]+)"),
    "score": re.compile(r"SCORE\.?\s*(\d+)\s*/\s*100"),
    "hit": re.compile(r"hit rate\.?\s*([\d.]+)\s*%", re.I),
    "ana": re.compile(r"Analogues\.?\s*(\d+)", re.I),
    "regime": re.compile(r"Regime\.?\s*([A-Z]+\s*/\s*[A-Z]+)"),
    "conf": re.compile(r"Confirmation\.?\s*([+-]?\d+)", re.I),
    "agree": re.compile(r"Agreement\.?\s*(\d+)\s*%", re.I),
}


def _num(s):
    return float(s.rstrip(".")) if s else None


def _g(key, blk, cast=str):
    m = F[key].search(blk)
    return cast(m.group(1)) if m else None


def parse_message(text, ts_utc):
    """text: one full signal message. ts_utc: tz-aware UTC timestamp of the message."""
    ts_utc = pd.Timestamp(ts_utc)
    ts_utc = ts_utc.tz_localize("UTC") if ts_utc.tzinfo is None else ts_utc.tz_convert("UTC")
    bm = re.search(r"\b([A-Z]+) SIGNAL\b", text)
    batch = bm.group(1) if bm else None
    out = []
    for n, blk in enumerate(re.split(r"SETUP #\d+", text)[1:], 1):
        core = F["core"].search(blk)
        if not (core and F["tp1"].search(blk) and F["tp2"].search(blk) and F["sl"].search(blk)):
            continue
        out.append(dict(
            ts_utc=ts_utc.isoformat(), batch=batch, setup_no=n,
            direction=core.group(1), symbol=core.group(2), entry=_num(core.group(3)),
            tp1=_num(_g("tp1", blk)), tp2=_num(_g("tp2", blk)), sl=_num(_g("sl", blk)),
            score=_g("score", blk, int), hit_rate=_g("hit", blk, float),
            analogues=_g("ana", blk, int), regime=_g("regime", blk),
            confirmation=_g("conf", blk, int), agreement=_g("agree", blk, int),
        ))
    return out


def parse_export(text, tz):
    """Pasted Telegram text with 'MercuryEdge, [Sep 30, 2026 at 16:05]' headers."""
    parts = HDR.split(text)  # [pre, date, time, body, date, time, body, ...]
    out = []
    for i in range(1, len(parts) - 2, 3):
        ts = pd.Timestamp(f"{parts[i]} {parts[i+1]}").tz_localize(tz).tz_convert("UTC")
        out += parse_message(parts[i + 2], ts)
    return out
