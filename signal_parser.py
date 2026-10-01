"""Parse MercuryEdge-style signal exports into normalized audit records."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

PRICE_RE = r"([0-9]+(?:\.[0-9]+)?)"

def _num(pattern, text):
    m = re.search(pattern, text, re.I)
    return float(m.group(1)) if m else None

def _int(pattern, text):
    m = re.search(pattern, text, re.I)
    return int(m.group(1)) if m else None

def _timestamp(text, default_tz):
    # Accept explicit ISO timestamps when present.
    m = re.search(r"(20\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)", text)
    if m:
        dt = datetime.fromisoformat(m.group(1))
        return (dt.replace(tzinfo=ZoneInfo(default_tz)) if dt.tzinfo is None else dt).astimezone(ZoneInfo("UTC")).isoformat()
    return None

def parse_export(text, tz="Africa/Lagos"):
    """Parse one or more MercuryEdge setup blocks.

    A block normally contains:
      BUY/SELL SYMBOL @ entry
      TP1 ...
      TP2 ...
      SL ...
    Optional metadata such as score/hit rate/agreement is retained.
    """
    lines = [x.strip() for x in text.replace("\r", "").splitlines()]
    starts = [i for i, line in enumerate(lines)
              if re.search(r"\b(?:BUY|SELL)\s+[A-Z0-9._-]+\s*@\s*" + PRICE_RE, line, re.I)]
    if not starts:
        return []

    records = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        block = "\n".join(lines[max(0, start - 12):end])
        headline = lines[start]

        m = re.search(r"\b(BUY|SELL)\s+([A-Z0-9._-]+)\s*@\s*" + PRICE_RE, headline, re.I)
        if not m:
            continue
        direction, symbol, entry = m.group(1).upper(), m.group(2).upper(), float(m.group(3))

        tp1 = _num(r"\bTP1\s*[:=@]?\s*" + PRICE_RE, block)
        tp2 = _num(r"\bTP2\s*[:=@]?\s*" + PRICE_RE, block)
        sl = _num(r"\bSL\s*[:=@]?\s*" + PRICE_RE, block)
        if tp1 is None or tp2 is None or sl is None:
            continue

        hit_rate = _num(r"(?:HIT\s*RATE|WIN\s*RATE)\s*[:=]?\s*" + PRICE_RE, block)
        score = _int(r"\bSCORE\s*[:=]?\s*(\d{1,3})", block)
        analogues = _int(r"\b(?:ANALOGUES|ANALOGS)\s*[:=]?\s*(\d+)", block)
        agreement = _num(r"\b(?:AGREEMENT|CROSS[- ]?MARKET)\s*[:=]?\s*" + PRICE_RE + r"\s*%?", block)
        confirmation = _int(r"\bCONFIRMATION\s*[:=]?\s*(\d+)", block)

        ts = _timestamp(block, tz)
        if ts is None:
            # Telegram listener supplies an explicit timestamp. For pasted text,
            # use the current time only as a last-resort ingestion timestamp.
            ts = datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat()

        batch_m = re.search(r"\b(?:MORNING|AFTERNOON|EVENING)\b", block, re.I)
        batch = batch_m.group(0).upper() if batch_m else None
        setup_m = re.search(r"SETUP\s*#\s*(\d+)", block, re.I)
        setup_no = int(setup_m.group(1)) if setup_m else None

        records.append({
            "ts_utc": ts,
            "batch": batch,
            "setup_no": setup_no,
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
