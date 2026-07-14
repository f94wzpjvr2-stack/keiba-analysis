import pandas as pd
import pytest

from keiba_ev.probability import combination_probabilities, probabilities_from_scores
from keiba_ev.scoring import score_horses


SCORE_MAX = {"ability": 40, "suitability": 20, "pace": 20, "training": 10, "paddock": 10}


def sample_horses():
    return pd.DataFrame(
        [
            {"horse_no": 1, "horse_name": "A", "ability": 35, "suitability": 17, "pace": 15, "training": 8, "paddock": 8},
            {"horse_no": 2, "horse_name": "B", "ability": 32, "suitability": 16, "pace": 16, "training": 7, "paddock": 7},
            {"horse_no": 3, "horse_name": "C", "ability": 28, "suitability": 15, "pace": 14, "training": 7, "paddock": 7},
            {"horse_no": 4, "horse_name": "D", "ability": 26, "suitability": 14, "pace": 13, "training": 6, "paddock": 6},
        ]
    )


def test_probability_tables_sum_correctly():
    scored = score_horses(sample_horses(), SCORE_MAX)
    probs = probabilities_from_scores(scored)
    tables = combination_probabilities(probs)
    assert probs["win_prob"].sum() == pytest.approx(1.0)
    assert tables["quinella"]["model_prob"].sum() == pytest.approx(1.0)
    assert tables["trio"]["model_prob"].sum() == pytest.approx(1.0)
    assert tables["wide"]["model_prob"].sum() == pytest.approx(3.0)


def test_user_probability_input_is_normalized():
    horses = sample_horses()
    horses["win_prob_input"] = [40, 30, 20, 10]
    scored = score_horses(horses, SCORE_MAX)
    probs = probabilities_from_scores(scored)
    assert probs.loc[probs["horse_no"] == 1, "win_prob"].item() == pytest.approx(0.4)
