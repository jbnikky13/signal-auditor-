import pandas as pd
import db

TP1_FIRST = {"TP2", "TP1_THEN_SL", "TP1_ONLY"}
DECIDED = TP1_FIRST | {"SL"}


def _table(df, col):
    rows = []
    for k, g in df.groupby(col, observed=True):
        d = g[g.outcome.isin(DECIDED)]
        if d.empty:
            continue
        rows.append({
            col: k,
            "n": len(d),
            "TP1_first%": round(100 * d.outcome.isin(TP1_FIRST).mean(), 1),
            "TP2%": round(100 * (d.outcome == "TP2").mean(), 1),
            "SL%": round(100 * (d.outcome == "SL").mean(), 1),
            "avgR(exit@TP1)": round(d.r1.mean(), 2),
        })
    return pd.DataFrame(rows).to_string(index=False) if rows else "(no decided signals)"


def _pct(n, d):
    return "n/a" if not d else f"{100 * n / d:.1f}%"


def _fmt_r(value):
    return "n/a" if pd.isna(value) else f"{value:+.2f}R"


def build():
    df = db.results_df()
    if df.empty:
        return "📊 SIGNAL AUDITOR\n\nNo settled signals yet."

    for col in ["entry", "sl", "tp1", "tp2", "score", "agreement", "hit_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    sl_d = (df.entry - df.sl).abs()
    df["tp1_r"] = (df.tp1 - df.entry).abs() / sl_d
    df["tp2_r"] = (df.tp2 - df.entry).abs() / sl_d
    df["r1"] = df.apply(
        lambda r: r.tp1_r if r.outcome in TP1_FIRST else (-1.0 if r.outcome == "SL" else None),
        axis=1,
    )
    df["r2"] = df.apply(
        lambda r: r.tp2_r if r.outcome == "TP2" else (-1.0 if r.outcome in ("SL", "TP1_THEN_SL") else None),
        axis=1,
    )
    df["score_band"] = pd.cut(
        df.score,
        [-float("inf"), 64, 69, 74, float("inf")],
        labels=["<65", "65-69", "70-74", "75+"],
        include_lowest=True,
    )
    df.loc[df.score.isna(), "score_band"] = pd.NA
    df["xmkt"] = df.agreement.fillna(0).apply(
        lambda a: "100%" if a == 100 else "<100%"
    )

    outcomes = df.outcome.value_counts()
    decided = df[df.outcome.isin(DECIDED)]
    open_count = int((df.outcome == "OPEN").sum())
    no_data_count = int((df.outcome == "NO_DATA").sum())

    lines = [
        "📊 SIGNAL AUDITOR",
        "",
        "📌 SUMMARY",
        "────────────",
        f"Signals: {len(df)}   •   Decided: {len(decided)}",
        f"Open: {open_count}   •   No data: {no_data_count}",
        "",
        "OUTCOMES",
        "────────",
    ]

    for outcome in ["TP2", "TP1_THEN_SL", "TP1_ONLY", "SL", "OPEN", "NO_DATA"]:
        count = int(outcomes.get(outcome, 0))
        if count:
            label = {
                "TP2": "TP2 reached",
                "TP1_THEN_SL": "TP1 → SL",
                "TP1_ONLY": "TP1 only",
                "SL": "SL first",
                "OPEN": "Still open",
                "NO_DATA": "No market data",
            }[outcome]
            lines.append(f"{label}: {count}")

    if not decided.empty:
        tp1_first = int(decided.outcome.isin(TP1_FIRST).sum())
        tp2 = int((decided.outcome == "TP2").sum())
        sl_first = int((decided.outcome == "SL").sum())
        r1 = decided.r1.dropna()
        r2 = decided.r2.dropna()

        lines += [
            "",
            "📈 SETTLEMENT",
            "────────────",
            f"TP1 before SL: {_pct(tp1_first, len(decided))}",
            f"TP2 reached: {_pct(tp2, len(decided))}",
            f"SL first: {_pct(sl_first, len(decided))}",
            f"Expectancy @ TP1: {_fmt_r(r1.mean())} / trade",
            f"Expectancy @ TP2: {_fmt_r(r2.mean())} / trade",
            f"Total simulated R @ TP1: {_fmt_r(r1.sum())}",
            f"Total simulated R @ TP2: {_fmt_r(r2.sum())}",
        ]

    claimed = decided.hit_rate.dropna()
    lines += [
        "",
        "🧾 PROVIDER DATA",
        "────────────────",
        f"Claimed 3D hit rate: {len(claimed)}/{len(decided)} signals available",
        f"Provider average: {claimed.mean():.1f}%" if not claimed.empty else "Provider average: n/a",
        "",
        "🔎 DATA QUALITY",
        "──────────────",
        f"Missing score: {int(df.score.isna().sum())}/{len(df)}",
        f"Missing TP2: {int(df.tp2.isna().sum())}/{len(df)}",
        f"Missing claimed hit rate: {int(df.hit_rate.isna().sum())}/{len(df)}",
        "",
        "📊 BREAKDOWNS",
        "─────────────",
        "",
        "By score band",
        _table(df, "score_band"),
        "",
        "By cross-market agreement",
        _table(df, "xmkt"),
        "",
        "By batch",
        _table(df, "batch"),
        "",
        "By symbol",
        _table(df, "symbol"),
        "",
        "By direction",
        _table(df, "direction"),
        "",
        "📎 Detailed results: audit-results.csv",
    ]
    return "\n".join(str(x) for x in lines if x is not None)


if __name__ == "__main__":
    print(build())
