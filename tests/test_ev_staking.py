import pandas as pd

from keiba_ev.ev import attach_odds_and_ev
from keiba_ev.staking import allocate_budget
from keiba_ev.validation import validate_ticket_plan


def test_ev_and_budget_allocation():
    probabilities = pd.DataFrame(
        [
            {"selection": "1-2", "model_prob": 0.20},
            {"selection": "1-3", "model_prob": 0.08},
            {"selection": "2-3", "model_prob": 0.10},
        ]
    )
    odds = pd.DataFrame(
        [
            {"selection": "1-2", "odds": 6.0},
            {"selection": "1-3", "odds": 15.0},
            {"selection": "2-3", "odds": 7.0},
        ]
    )
    ev = attach_odds_and_ev(probabilities, odds)
    plan = allocate_budget(ev, 1000, ev_threshold=1.03)
    validation = validate_ticket_plan(plan, 1000)
    assert validation["ok"]
    assert validation["spent"] <= 1000
    assert (plan["ev"] >= 1.03).all()


def test_no_positive_ev_means_no_bet():
    candidates = pd.DataFrame(
        [{"selection": "1", "model_prob": 0.2, "odds": 3.0, "ev": 0.6}]
    )
    plan = allocate_budget(candidates, 1000)
    assert plan.empty


def test_allocation_handles_duplicate_dataframe_indices_across_bet_types():
    first = pd.DataFrame(
        [
            {"bet_type": "単勝", "selection": "1", "model_prob": 0.3, "odds": 4.0, "ev": 1.2},
            {"bet_type": "単勝", "selection": "2", "model_prob": 0.2, "odds": 6.0, "ev": 1.2},
        ]
    )
    second = pd.DataFrame(
        [
            {"bet_type": "ワイド", "selection": "1-2", "model_prob": 0.25, "odds": 5.0, "ev": 1.25},
        ]
    )
    candidates = pd.concat([first, second])
    plan = allocate_budget(candidates, 1000)
    assert not plan.empty
    assert plan["stake"].sum() <= 1000
