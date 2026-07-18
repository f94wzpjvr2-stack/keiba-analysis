from __future__ import annotations

import pandas as pd


def settlement_summary(results: pd.DataFrame) -> dict[str, float]:
    if results.empty:
        return {
            "races": 0,
            "stake": 0.0,
            "payout": 0.0,
            "profit": 0.0,
            "return_rate": 0.0,
        }
    race_totals = results.drop_duplicates("race_id")
    stake = float(race_totals["race_total_stake"].sum())
    payout = float(race_totals["race_total_payout"].sum())
    return {
        "races": float(race_totals["race_id"].nunique()),
        "stake": stake,
        "payout": payout,
        "profit": payout - stake,
        "return_rate": payout / stake * 100 if stake else 0.0,
    }


def grouped_return_rate(results: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if results.empty or group_column not in results.columns:
        return pd.DataFrame(columns=[group_column, "stake", "payout", "profit", "return_rate"])
    grouped = (
        results.groupby(group_column, dropna=False)
        .agg(stake=("stake", "sum"), payout=("payout_amount", "sum"))
        .reset_index()
    )
    grouped["profit"] = grouped["payout"] - grouped["stake"]
    grouped["return_rate"] = grouped["payout"] / grouped["stake"].where(grouped["stake"] != 0) * 100
    return grouped.sort_values("return_rate", ascending=False)


def build_performance_report(results: pd.DataFrame, current_results: pd.DataFrame | None = None) -> dict:
    current = current_results if current_results is not None else results.iloc[0:0]
    return {
        "current": settlement_summary(current),
        "cumulative": settlement_summary(results),
        "by_bet_type": grouped_return_rate(results, "bet_type"),
        "by_algorithm_version": grouped_return_rate(results, "algorithm_version"),
    }
