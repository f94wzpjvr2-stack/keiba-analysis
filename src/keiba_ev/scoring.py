from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

SCORE_COLUMNS = ("ability", "suitability", "pace", "training", "paddock")


def score_horses(horses: pd.DataFrame, score_max: Mapping[str, float]) -> pd.DataFrame:
    """Validate score columns and calculate the 100-point total score."""
    required = {"horse_no", "horse_name", *SCORE_COLUMNS}
    missing = sorted(required - set(horses.columns))
    if missing:
        raise ValueError(f"Missing horse columns: {missing}")

    out = horses.copy()
    if out["horse_no"].duplicated().any():
        duplicates = out.loc[out["horse_no"].duplicated(), "horse_no"].tolist()
        raise ValueError(f"Duplicate horse numbers: {duplicates}")

    for column in SCORE_COLUMNS:
        max_value = float(score_max[column])
        values = pd.to_numeric(out[column], errors="raise")
        invalid = (values < 0) | (values > max_value)
        if invalid.any():
            bad = out.loc[invalid, ["horse_no", column]].to_dict("records")
            raise ValueError(f"{column} must be between 0 and {max_value}: {bad}")
        out[column] = values.astype(float)

    out["total_score"] = out[list(SCORE_COLUMNS)].sum(axis=1)
    out["ability_rank"] = out["total_score"].rank(method="min", ascending=False).astype(int)
    return out
