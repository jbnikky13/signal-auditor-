import pandas as pd

import config
import settle


def _signal():
    return {
        "id": "test-signal",
        "symbol": "EURUSD",
        "direction": "BUY",
        "ts_utc": "2026-01-01T00:00:00+00:00",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
        "tp2": 110.0,
    }


def _candles(rows):
    index = pd.to_datetime([row[0] for row in rows], utc=True)
    return pd.DataFrame(
        [{"Open": 100.0, "High": high, "Low": low, "Close": 100.0}
         for _, high, low in rows],
        index=index,
    )


def test_default_horizon_is_24_hours():
    assert config.MAX_HOURS == 24


def test_tp1_before_expiry_and_sl_after_expiry_is_tp1_only():
    sig = _signal()
    candles = _candles([
        ("2026-01-01T00:01:00Z", 106.0, 99.0),
        ("2026-01-02T00:01:00Z", 101.0, 94.0),
    ])

    result = settle.settle(
        sig, candles, now=pd.Timestamp("2026-01-03T00:00:00Z")
    )

    assert result["outcome"] == "TP1_ONLY"
    assert result["final"] is True
    assert result["tp1_t"] == pd.Timestamp("2026-01-01T00:01:00Z")


def test_price_touch_after_expiry_does_not_settle_trade_as_sl():
    sig = _signal()
    candles = _candles([
        ("2026-01-01T00:01:00Z", 101.0, 99.0),
        ("2026-01-02T00:01:00Z", 101.0, 94.0),
    ])

    result = settle.settle(
        sig, candles, now=pd.Timestamp("2026-01-03T00:00:00Z")
    )

    assert result["outcome"] == "NO_RESOLUTION"
    assert result["final"] is True
    assert result["t_hit"] is None
