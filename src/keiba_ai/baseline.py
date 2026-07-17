import numpy as np
from .features import build_features

def baseline_probabilities(df, temperature=8.0):
    out = build_features(df)
    result = []
    for _, g in out.groupby("race_id", sort=False):
        z = (g["total_score"].to_numpy(float) - g["total_score"].max()) / temperature
        p = np.exp(z)
        result.extend((p / p.sum()).tolist())
    out["win_prob_model"] = result
    return out
