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
        rows.append({col: k, "n": len(d),
                     "TP1_first%": round(100 * d.outcome.isin(TP1_FIRST).mean(), 1),
                     "TP2%": round(100 * (d.outcome == "TP2").mean(), 1),
                     "SL%": round(100 * (d.outcome == "SL").mean(), 1),
                     "avgR(exit@TP1)": round(d.r1.mean(), 2)})
    return pd.DataFrame(rows).to_string(index=False) if rows else "(no decided signals)"


def build():
    df = db.results_df()
    if df.empty:
        return "No settled signals yet."
    sl_d = (df.entry - df.sl).abs()
    df["tp1_r"] = (df.tp1 - df.entry).abs() / sl_d
    df["tp2_r"] = (df.tp2 - df.entry).abs() / sl_d
    df["r1"] = df.apply(lambda r: r.tp1_r if r.outcome in TP1_FIRST else (-1.0 if r.outcome == "SL" else None), axis=1)
    df["r2"] = df.apply(lambda r: r.tp2_r if r.outcome == "TP2" else (-1.0 if r.outcome in ("SL", "TP1_THEN_SL") else None), axis=1)
    df["score_band"] = pd.cut(df.score, [0, 64, 69, 74, 100], labels=["<65", "65-69", "70-74", "75+"])
    df["xmkt"] = df.agreement.fillna(0).apply(lambda a: "agreement 100%" if a == 100 else "agreement <100%")

    dec = df[df.outcome.isin(DECIDED)]
    lines = ["SIGNAL AUDIT", "", "Outcomes:", df.outcome.value_counts().to_string(), ""]
    if not dec.empty:
        lines += [
            f"Decided signals: {len(dec)}",
            f"TP1 before SL: {100 * dec.outcome.isin(TP1_FIRST).mean():.1f}%   "
            f"TP2 reached: {100 * (dec.outcome == 'TP2').mean():.1f}%   "
            f"SL first: {100 * (dec.outcome == 'SL').mean():.1f}%",
            f"Expectancy, close all at TP1: {dec.r1.mean():+.2f}R per trade",
            f"Expectancy, hold to TP2 (orig SL): {dec.r2.dropna().mean():+.2f}R per trade"
            if dec.r2.notna().any() else "",
            f"Provider's avg claimed 3D hit rate: {dec.hit_rate.mean():.1f}%", ""]
    lines += ["By score band:", _table(df, "score_band"), "",
              "By cross-market agreement:", _table(df, "xmkt"), "",
              "By symbol:", _table(df, "symbol"), "",
              "By direction:", _table(df, "direction")]
    return "\n".join(l for l in lines if l is not None)


if __name__ == "__main__":
    print(build())
