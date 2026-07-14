from __future__ import annotations

import math

import pandas as pd


def fractional_kelly(probability: float, odds: float, fraction: float = 0.25) -> float:
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")
    if odds <= 1:
        return 0.0
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    full_kelly = (probability * odds - 1.0) / (odds - 1.0)
    return max(0.0, full_kelly) * fraction


def allocate_budget(
    candidates: pd.DataFrame,
    budget: int,
    *,
    unit: int = 100,
    ev_threshold: float = 1.03,
    kelly_fraction: float = 0.25,
    max_tickets: int = 8,
    max_ticket_share: float = 0.35,
) -> pd.DataFrame:
    """Allocate a budget ceiling conservatively across positive-EV candidates.

    The function may spend less than the budget. It never forces negative-EV bets.
    """
    if budget < 0 or budget % unit != 0:
        raise ValueError("budget must be a non-negative multiple of unit")
    if not 0 < max_ticket_share <= 1:
        raise ValueError("max_ticket_share must be in (0, 1]")

    required = {"selection", "model_prob", "odds", "ev"}
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError(f"Missing staking columns: {missing}")

    selected = candidates[candidates["ev"] >= ev_threshold].copy().reset_index(drop=True)
    if selected.empty or budget == 0:
        return pd.DataFrame(
            columns=["selection", "model_prob", "odds", "ev", "kelly", "stake"]
        )

    selected["kelly"] = [
        fractional_kelly(prob, odds, kelly_fraction)
        for prob, odds in zip(selected["model_prob"], selected["odds"])
    ]
    selected = (
        selected[selected["kelly"] > 0]
        .nlargest(max_tickets, ["ev", "kelly"])
        .copy()
        .reset_index(drop=True)
    )
    if selected.empty:
        return pd.DataFrame(
            columns=["selection", "model_prob", "odds", "ev", "kelly", "stake"]
        )

    selected["weight"] = selected["kelly"] * (selected["ev"] - 1.0).clip(lower=0.0).pow(0.5)
    weight_sum = float(selected["weight"].sum())
    if weight_sum <= 0:
        return pd.DataFrame(
            columns=["selection", "model_prob", "odds", "ev", "kelly", "stake"]
        )

    max_stake = max(unit, math.floor((budget * max_ticket_share) / unit) * unit)
    selected["stake"] = (
        (selected["weight"] / weight_sum * budget // unit) * unit
    ).astype(int).clip(upper=max_stake)

    # Give one unit to the strongest candidates when rounding made every stake zero.
    if selected["stake"].sum() == 0:
        count = min(len(selected), budget // unit)
        selected.loc[selected.index[:count], "stake"] = unit

    # Add remaining units only to positive-EV tickets and respect the ticket cap.
    remaining = budget - int(selected["stake"].sum())
    ordered = selected.sort_values(["ev", "kelly"], ascending=False).index.tolist()
    cursor = 0
    while remaining >= unit and ordered:
        index = ordered[cursor % len(ordered)]
        if selected.at[index, "stake"] + unit <= max_stake:
            selected.at[index, "stake"] += unit
            remaining -= unit
        cursor += 1
        if cursor > len(ordered) * (budget // unit + 1):
            break

    selected = selected[selected["stake"] > 0]
    columns = ["selection", "model_prob", "odds", "ev", "kelly", "stake"]
    if "bet_type" in selected.columns:
        columns = ["bet_type", *columns]
    return selected[columns].sort_values(["stake", "ev"], ascending=False).reset_index(drop=True)
