from __future__ import annotations

import pandas as pd


def attach_odds_and_ev(probabilities: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    """Join model probabilities to odds and calculate EV and break-even probability."""
    required_prob = {"selection", "model_prob"}
    required_odds = {"selection", "odds"}
    if not required_prob.issubset(probabilities.columns):
        raise ValueError(f"Probability table requires {sorted(required_prob)}")
    if not required_odds.issubset(odds.columns):
        raise ValueError(f"Odds table requires {sorted(required_odds)}")

    merged = probabilities.merge(odds, on="selection", how="inner", validate="one_to_one")
    merged["market_break_even_prob"] = 1.0 / merged["odds"]
    merged["edge"] = merged["model_prob"] - merged["market_break_even_prob"]
    merged["ev"] = merged["model_prob"] * merged["odds"]
    merged["ev_rank"] = merged["ev"].rank(method="min", ascending=False).astype(int)
    return merged.sort_values(["ev", "model_prob"], ascending=False).reset_index(drop=True)
