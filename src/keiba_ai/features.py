import numpy as np

FEATURES = [
    "ability",
    "suitability",
    "pace",
    "training",
    "paddock",
    "total_score",
    "field_size",
    "log_win_odds",
    "market_prob",
]

def build_features(df):
    out = df.copy()
    out["total_score"] = out[["ability","suitability","pace","training","paddock"]].sum(axis=1)
    out["field_size"] = out.groupby("race_id")["horse_no"].transform("count")
    out["log_win_odds"] = np.log(out["win_odds"].clip(lower=1.01))
    raw = 1 / out["win_odds"]
    out["market_prob"] = raw / raw.groupby(out["race_id"]).transform("sum")
    return out
