from __future__ import annotations

from typing import Any

import pandas as pd

from .probability import combination_probabilities, probabilities_from_scores
from .scoring import score_horses


def analyze_race(horses: pd.DataFrame, config: dict[str, Any]) -> dict[str, pd.DataFrame]:
    scored = score_horses(horses, config["score_max"])
    probability_config = config.get("probability", {})
    probabilities = probabilities_from_scores(
        scored,
        temperature=float(probability_config.get("temperature", 8.0)),
    )
    combinations = combination_probabilities(probabilities)
    return {"horses": probabilities, **combinations}
