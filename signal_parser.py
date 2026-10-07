"""Parse MercuryEdge-style Telegram trading signals into normalized audit records."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

# Accepts plain (1.2345, 7050.5) and thousands-separated (7,050.25) prices.
# The old pattern stopped at the comma, so "7,050" was read as 7.
PRICE_RE = r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"

# MercuryEdge writes some labels with a colon ("CONFIRMATION: +0") and others
# with a period ("SCORE. 68/100", "TP1. 7,858.42"), so accept either.
SEP = r"\s*[\.:=@-]?\s*"
SEP_NUM = r"\s*[\.:=]?\s*"   # no "-" here, so it can't swallow a minus sign

SETUP_MARK = re.compile(r"^\s*SETUP\s*#\s*(\d+)", re.I)
BATCH_RE = re.compile(r"\b(MORNING|AFTERNOON|EVENING)\b", re.I)


def _f(s):
    return float(s.replace(",", ""))


def levels_ok(direction, entry, tp1, tp2, sl):
    """True only if SL < entry < TP1 < TP2 (BUY) or the reverse (SELL)."""
    if entry is None or tp1 is None or sl is None:
        return False
    chain = [sl, entry, tp1] + ([tp2] if tp2 is not None else [])
    pairs = list(zip(chain, chain[1:]))
    if str(direction).upper() == "BUY":
        return all(a < b for a, b in pairs)
    return all(a > b for a, b in pairs)


def _num(pattern, text):
    m = re.search(pattern, text, re.I | re.M)
    return _f(m.group(1)) if m else None

def _int(pattern, text):
    m = re.search(pattern, text, re.I | re.M)
    return int(m.group(1)) if m else None

def _text(pattern, text):
    m = re.search(pattern, text, re.I | re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip().upper() if m else None

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
    return (m.group(1).upper(), m.group(2).upper(), _f(m.group(3))) if m else None

def _target(patterns, block):
    for p in patterns:
        value = _num(p + SEP + PRICE_RE, block)
        if value is not None:
            return value
    return None

def _setup_begin(lines, start):
    """Index where this setup's block begins: its own 'SETUP #n' line if it is
    within a few lines above the BUY/SELL headline, else 3 lines above it.
    (The old code looked 12 lines back, which pulled the previous setup's
    CONFIRMATION/AGREEMENT lines into the next setup's block.)"""
    for j in range(start, max(-1, start - 5), -1):
        if SETUP_MARK.match(lines[j]):
            return j
    return max(0, start - 3)

def _batch_before(lines, idx):
    """Most recent MORNING/AFTERNOON/EVENING label at or above idx."""
    for j in range(idx, -1, -1):
        m = BATCH_RE.search(lines[j])
        if m:
            return m.group(1).upper()
    return None

def parse_export(text, tz="Africa/Lagos"):
    """Parse one or more MercuryEdge setup blocks.

    Accepted examples include:
      BUY EURUSD @ 1.2345
      SELL EURUSD ENTRY 1.2345
      TP1: 1.2355 / TP1. 1.2355 / TP 1 1.2355 / TAKE PROFIT 1: 1.2355
      TP2: 1.2370 / TAKE PROFIT 2: 1.2370
      SL: 1.2320 / SL. 1.2320 / STOP LOSS: 1.2320
      SCORE. 68/100, Analogues. 183, Regime. BULLISH / NORMAL
      CONFIRMATION: +0, AGREEMENT: 0%
    """
    text = _clean(text)
    lines = text.splitlines()
    starts = _find_starts(lines)
    if not starts:
        return []
    begins = [_setup_begin(lines, s) for s in starts]

    records = []
    for pos, start in enumerate(starts):
        lo = begins[pos]
        hi = begins[pos + 1] if pos + 1 < len(starts) else len(lines)
        block = "\n".join(lines[lo:hi])
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
        if not levels_ok(direction, entry, tp1, tp2, sl):
            print(f"[warn] skipped invalid levels: {direction} {symbol} "
                  f"entry={entry} tp1={tp1} tp2={tp2} sl={sl}")
            continue

        hit_rate = _num(r"\b(?:HIT\s*RATE|WIN\s*RATE)" + SEP + PRICE_RE, block)
        score = _int(r"\bSCORE" + SEP_NUM + r"(\d{1,3})", block)
        analogues = _int(r"\b(?:ANALOGUES|ANALOGS)" + SEP_NUM + r"(\d+)", block)
        regime = _text(r"^\s*REGIME" + SEP_NUM + r"(.+?)\s*$", block)
        agreement = _num(r"\bAGREEMENT" + SEP_NUM + PRICE_RE + r"\s*%?", block)
        confirmation = _int(r"\bCONFIRMATION" + SEP_NUM + r"([+-]?\d+)", block)

        ts = _timestamp(block, tz) or datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat()
        setup_m = SETUP_MARK.match(lines[lo]) if SETUP_MARK.match(lines[lo]) else re.search(r"SETUP\s*#\s*(\d+)", block, re.I)

        records.append({
            "ts_utc": ts,
            "batch": _batch_before(lines, lo),
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
            "regime": regime,
            "confirmation": confirmation,
            "agreement": agreement,
        })
    return records
