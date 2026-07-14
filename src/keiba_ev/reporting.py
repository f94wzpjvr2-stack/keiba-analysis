from __future__ import annotations

import pandas as pd


def roi_summary(bets: pd.DataFrame) -> dict[str, float]:
    required = {"stake", "payout"}
    missing = sorted(required - set(bets.columns))
    if missing:
        raise ValueError(f"Missing ROI columns: {missing}")
    stake = float(pd.to_numeric(bets["stake"], errors="raise").sum())
    payout = float(pd.to_numeric(bets["payout"], errors="raise").fillna(0).sum())
    return {
        "stake": stake,
        "payout": payout,
        "profit": payout - stake,
        "roi": payout / stake if stake else 0.0,
    }


def grouped_roi(bets: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    required = {"stake", "payout", *group_columns}
    missing = sorted(required - set(bets.columns))
    if missing:
        raise ValueError(f"Missing grouped ROI columns: {missing}")
    out = bets.copy()
    out["stake"] = pd.to_numeric(out["stake"], errors="raise")
    out["payout"] = pd.to_numeric(out["payout"], errors="raise").fillna(0)
    grouped = (
        out.groupby(group_columns, dropna=False)
        .agg(stake=("stake", "sum"), payout=("payout", "sum"), tickets=("stake", "size"))
        .reset_index()
    )
    grouped["profit"] = grouped["payout"] - grouped["stake"]
    grouped["roi"] = grouped["payout"] / grouped["stake"].where(grouped["stake"] != 0)
    return grouped.sort_values("roi", ascending=False)
