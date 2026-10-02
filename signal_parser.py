"""Parse MercuryEdge-style Telegram trading signals into normalized audit records."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

PRICE_RE = r"([0-9]+(?:\.[0-9]+)?)"

def _num(pattern, text):
    m = re.search(pattern, text, re.I | re.M)
    return float(m.group(1)) if m else None

def _int(pattern, text):
    m = re.search(pattern, text, re.I | re.M)
    return int(m.group(1)) if m else None

def _timestamp(text, default_tz):
    m = re.search(r"(20\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)", text)
    if m:
        dt = datetime.fromisoformat(m.group(1))
        return (dt.replace(tzinfo=ZoneInfo(default_tz)) if dt.tzinfo is None else dt).astimezone(ZoneInfo("UTC")).isoformat()
    return None

def _clean(text):
    # Telegram messages can contain emoji, markdown, bullets and non-breaking spaces.
    text = text.replace("\r", "").replace("\u00a0", " ")
    text = text.replace("—", "-").replace("–", "-")
    return "\n".join(line.strip(" \t•·") for line in text.splitlines())

def _find_starts(lines):
    # Support both the normal "BUY EURUSD @ 1.2345" form and common
    # variants such as "BUY EURUSD ENTRY 1.2345".
    starts = []
    for i, line in enumerate(lines):
        if re.search(r"\b(?:BUY|SELL)\s+([A-Z0-9][A-Z0-9._-]{1,15})\s+(?:@|AT|ENTRY\s*(?:PRICE)?\s*[:=]?)\s*" + PRICE_RE, line, re.I):
            starts.append(i)
    return starts

def _headline(text):
    m = re.search(
        r"\b(BUY|SELL)\s+([A-Z0-9][A-Z0-9._-]{1,15})\s+"
        r"(?:@|AT|ENTRY\s*(?:PRICE)?\s*[:=]?)\s*" + PRICE_RE,
        text,
        re.I,
    )
    return (m.group(1).upper(), m.group(2).upper(), float(m.group(3))) if m else None

def _target(patterns, block):
    for p in patterns:
        value = _num(p + r"\s*[:=@-]?\s*" + PRICE_RE, block)
        if value is not None:
            return value
    return None

def parse_export(text, tz="Africa/Lagos"):
    """Parse one or more MercuryEdge setup blocks.

    Accepted examples include:
      BUY EURUSD @ 1.2345
      SELL EURUSD ENTRY 1.2345
      TP1: 1.2355 / TP 1 1.2355 / TAKE PROFIT 1: 1.2355
      TP2: 1.2370 / TAKE PROFIT 2: 1.2370
      SL: 1.2320 / STOP LOSS: 1.2320
    """
    text = _clean(text)
    lines = text.splitlines()
    starts = _find_starts(lines)
    if not starts:
        return []

    records = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        block = "\n".join(lines[max(0, start - 12):end])
        parsed = _headline(lines[start])
        if not parsed:
            continue
        direction, symbol, entry = parsed

        tp1 = _target([r"\bTP\s*1\b", r"\bTAKE\s*PROFIT\s*1\b"], block)
        tp2 = _target([r"\bTP\s*2\b", r"\bTAKE\s*PROFIT\s*2\b"], block)
        sl = _target([r"\bSL\b", r"\bSTOP\s*LOSS\b"], block)

        # Some messages only publish one TP. Treat it as TP1 rather than
        # silently discarding the signal; settlement can still evaluate TP1/SL.
        if tp1 is None and tp2 is not None:
            tp1, tp2 = tp2, None
        if tp1 is None or sl is None:
            continue

        hit_rate = _num(r"\b(?:HIT\s*RATE|WIN\s*RATE)\s*[:=]?\s*" + PRICE_RE, block)
        score = _int(r"\bSCORE\s*[:=]?\s*(\d{1,3})", block)
        analogues = _int(r"\b(?:ANALOGUES|ANALOGS)\s*[:=]?\s*(\d+)", block)
        agreement = _num(r"\b(?:AGREEMENT|CROSS[- ]?MARKET)\s*[:=]?\s*" + PRICE_RE + r"\s*%?", block)
        confirmation = _int(r"\bCONFIRMATION\s*[:=]?\s*(\d+)", block)

        ts = _timestamp(block, tz) or datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat()
        batch_m = re.search(r"\b(?:MORNING|AFTERNOON|EVENING)\b", block, re.I)
        setup_m = re.search(r"SETUP\s*#\s*(\d+)", block, re.I)

        records.append({
            "ts_utc": ts,
            "batch": batch_m.group(0).upper() if batch_m else None,
            "setup_no": int(setup_m.group(1)) if setup_m else None,
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl,
            "score": score,
            "hit_rate": hit_rate,
            "analogues": analogues,
            "regime": None,
            "confirmation": confirmation,
            "agreement": agreement,
        })
    return records
