from __future__ import annotations

from pathlib import Path

import pandas as pd

TEMPLATES: dict[str, list[str]] = {
    "races.csv": [
        "race_id",
        "date",
        "course",
        "race_no",
        "surface",
        "distance",
        "going",
        "weather",
        "class_name",
        "budget_ceiling",
        "algorithm_version",
    ],
    "horses.csv": [
        "race_id",
        "horse_no",
        "horse_name",
        "ability",
        "suitability",
        "pace",
        "training",
        "paddock",
        "win_prob_input",
        "win_odds",
    ],
    "bets.csv": [
        "race_id",
        "bet_type",
        "selection",
        "stake",
        "odds_at_purchase",
        "model_prob",
        "ev_at_purchase",
        "payout",
        "algorithm_version",
        "odds_at_prediction",
        "estimated_probability",
        "expected_value",
        "predicted_at",
    ],
    "results.csv": [
        "race_id",
        "first",
        "second",
        "third",
        "notes",
        "bet_type",
        "selection",
        "stake",
        "hit",
        "payout_per_100",
        "payout_amount",
        "profit",
        "race_total_stake",
        "race_total_payout",
        "race_profit",
        "race_return_rate",
        "settled_at",
        "result_source_url",
        "algorithm_version",
    ],
}


def initialize_data_store(root: str | Path) -> Path:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    for filename, columns in TEMPLATES.items():
        target = root_path / filename
        if not target.exists():
            pd.DataFrame(columns=columns).to_csv(target, index=False, encoding="utf-8-sig")
    return root_path


def append_rows(path: str | Path, rows: pd.DataFrame) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_header = not target.exists() or target.stat().st_size == 0
    rows.to_csv(target, mode="a", header=write_header, index=False, encoding="utf-8-sig")
