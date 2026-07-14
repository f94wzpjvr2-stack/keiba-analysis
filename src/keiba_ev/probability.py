from __future__ import annotations

from itertools import permutations

import numpy as np
import pandas as pd


def _normalize(values: np.ndarray) -> np.ndarray:
    if np.any(~np.isfinite(values)):
        raise ValueError("Probability strengths contain non-finite values")
    if np.any(values < 0):
        raise ValueError("Probability strengths must be non-negative")
    total = float(values.sum())
    if total <= 0:
        raise ValueError("Probability strengths must sum to a positive value")
    return values / total


def probabilities_from_scores(
    scored: pd.DataFrame,
    temperature: float = 8.0,
    provided_column: str = "win_prob_input",
) -> pd.DataFrame:
    """Create win probabilities.

    If `win_prob_input` exists and every value is present, it is normalized and used.
    Otherwise a provisional softmax conversion from total_score is used.
    """
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    out = scored.copy()

    if provided_column in out.columns and out[provided_column].notna().all():
        strengths = pd.to_numeric(out[provided_column], errors="raise").to_numpy(float)
        source = "user_input_normalized"
    else:
        if "total_score" not in out.columns:
            raise ValueError("total_score is required")
        scores = out["total_score"].to_numpy(float)
        shifted = (scores - scores.max()) / temperature
        strengths = np.exp(shifted)
        source = f"score_softmax_t{temperature:g}"

    out["win_prob"] = _normalize(strengths)
    out["probability_source"] = source
    out["win_rank"] = out["win_prob"].rank(method="min", ascending=False).astype(int)
    return out


def ordered_finish_probability(weights: dict[int, float], order: tuple[int, ...]) -> float:
    """Plackett-Luce probability for an ordered finish sequence."""
    remaining = dict(weights)
    probability = 1.0
    for horse_no in order:
        if horse_no not in remaining:
            return 0.0
        denominator = sum(remaining.values())
        if denominator <= 0:
            return 0.0
        probability *= remaining[horse_no] / denominator
        remaining.pop(horse_no)
    return probability


def combination_probabilities(probabilities: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Calculate win, quinella, wide and trio probabilities.

    Pair/triple probabilities use a Plackett-Luce approximation from win strengths.
    """
    required = {"horse_no", "horse_name", "win_prob"}
    missing = sorted(required - set(probabilities.columns))
    if missing:
        raise ValueError(f"Missing probability columns: {missing}")

    horse_names = dict(zip(probabilities["horse_no"].astype(int), probabilities["horse_name"]))
    weights = dict(zip(probabilities["horse_no"].astype(int), probabilities["win_prob"].astype(float)))
    horse_numbers = sorted(weights)

    win_rows = [
        {
            "selection": str(no),
            "horse_no": no,
            "horse_name": horse_names[no],
            "model_prob": weights[no],
        }
        for no in horse_numbers
    ]

    top2_ordered: dict[tuple[int, int], float] = {}
    top3_ordered: dict[tuple[int, int, int], float] = {}
    for order in permutations(horse_numbers, 2):
        top2_ordered[order] = ordered_finish_probability(weights, order)
    for order in permutations(horse_numbers, 3):
        top3_ordered[order] = ordered_finish_probability(weights, order)

    quinella_rows = []
    wide_rows = []
    for i, first in enumerate(horse_numbers):
        for second in horse_numbers[i + 1 :]:
            quinella_prob = top2_ordered[(first, second)] + top2_ordered[(second, first)]
            wide_prob = sum(
                probability
                for order, probability in top3_ordered.items()
                if first in order and second in order
            )
            selection = f"{first}-{second}"
            quinella_rows.append({"selection": selection, "model_prob": quinella_prob})
            wide_rows.append({"selection": selection, "model_prob": wide_prob})

    trio_rows = []
    for i, first in enumerate(horse_numbers):
        for j, second in enumerate(horse_numbers[i + 1 :], i + 1):
            for third in horse_numbers[j + 1 :]:
                members = {first, second, third}
                trio_prob = sum(
                    probability
                    for order, probability in top3_ordered.items()
                    if set(order) == members
                )
                trio_rows.append(
                    {"selection": f"{first}-{second}-{third}", "model_prob": trio_prob}
                )

    return {
        "win": pd.DataFrame(win_rows),
        "quinella": pd.DataFrame(quinella_rows),
        "wide": pd.DataFrame(wide_rows),
        "trio": pd.DataFrame(trio_rows),
    }
