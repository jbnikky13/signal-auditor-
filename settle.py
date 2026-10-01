"""First-touch settlement engine. Never guesses when one candle touches both TP and SL."""
import pandas as pd
import config

TERMINAL = {"TP2", "SL", "TP1_THEN_SL", "AMBIGUOUS_SL_TP1_SAME_CANDLE",
            "TP1_THEN_AMBIGUOUS", "DATA_MISMATCH"}


def pip_size(sym):
    if sym in config.PIP:
        return config.PIP[sym]
    return 0.01 if sym.endswith("JPY") else 0.0001


def _res(outcome, final, **kw):
    return dict(outcome=outcome, final=final, t_hit=None, mins=None, tp1_t=None,
                mae_pips=None, mfe_pips=None, back_to_entry=None, note="", **kw)


def settle(sig, candles, spread_pips=1.0, max_hours=72, now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    ts = pd.Timestamp(sig["ts_utc"])
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    over = now >= ts + pd.Timedelta(hours=max_hours)
    if candles is None or candles.empty:
        return _res("NO_DATA", over, note="no candles")

    pip = pip_size(sig["symbol"])
    sp = spread_pips * pip
    buy = sig["direction"] == "BUY"
    start = ts.floor("min") + pd.Timedelta(minutes=1)  # skip the candle the signal landed in
    c = candles.loc[(candles.index >= start) & (candles.index <= ts + pd.Timedelta(hours=max_hours))]
    if c.empty:
        return _res("NO_DATA", over, note="no candles after signal")
    gap = c.index[0] - start
    if gap > pd.Timedelta(minutes=config.MAX_DATA_GAP_MIN):
        return _res("DATA_GAP", over, note=f"first candle {gap} after signal")

    # sanity: is this price feed even on the same scale as the signal (e.g. spot vs futures)?
    before = candles.loc[candles.index < start]
    if not before.empty and (start - before.index[-1]) <= pd.Timedelta(minutes=15):
        ref = float(before["Close"].iloc[-1])
        if abs(ref - sig["entry"]) > config.MISMATCH_SL_MULT * abs(sig["entry"] - sig["sl"]):
            return _res("DATA_MISMATCH", True, note=f"feed {ref} vs signal entry {sig['entry']}")

    stage, be_hit, mae, mfe = 0, False, 0.0, 0.0
    out, t_hit, tp1_t = "OPEN", None, None
    e, sl, tp1, tp2 = sig["entry"], sig["sl"], sig["tp1"], sig["tp2"]
    for t, hi, lo in zip(c.index, c["High"].to_numpy(), c["Low"].to_numpy()):
        if buy:   # long closes on the bid (feed price)
            sl_hit, tp1_hit, tp2_hit = lo <= sl, hi >= tp1, hi >= tp2
            adverse, favour, be_touch = e - lo, hi - e, lo <= e
        else:     # short closes on the ask (feed price + spread)
            sl_hit, tp1_hit, tp2_hit = hi + sp >= sl, lo + sp <= tp1, lo + sp <= tp2
            adverse, favour, be_touch = hi + sp - e, e - lo, hi + sp >= e
        mae, mfe = max(mae, adverse), max(mfe, favour)
        if stage == 0:
            if sl_hit and tp1_hit:
                out, t_hit = "AMBIGUOUS_SL_TP1_SAME_CANDLE", t
                break
            if sl_hit:
                out, t_hit = "SL", t
                break
            if tp1_hit:
                stage, tp1_t = 1, t
                if tp2_hit:
                    out, t_hit = "TP2", t
                    break
        else:
            if sl_hit and tp2_hit:
                out, t_hit = "TP1_THEN_AMBIGUOUS", t
                break
            be_hit = be_hit or be_touch
            if tp2_hit:
                out, t_hit = "TP2", t
                break
            if sl_hit:
                out, t_hit = "TP1_THEN_SL", t
                break

    final = out in TERMINAL
    if out == "OPEN":
        out = "TP1_ONLY" if stage == 1 else "OPEN"
        final = over
        if over and out == "OPEN":
            out = "NO_RESOLUTION"
    r = _res(out, final)
    r.update(t_hit=t_hit, tp1_t=tp1_t,
             mins=(t_hit - ts).total_seconds() / 60 if t_hit is not None else None,
             mae_pips=round(mae / pip, 1), mfe_pips=round(mfe / pip, 1),
             back_to_entry=be_hit if stage else None)
    return r
