import pandas as pd
from keiba_ai.baseline import baseline_probabilities
from keiba_ai.odds_parser import parse_pair_odds, parse_trio_odds
from keiba_ai.betting import allocate_budget
from keiba_ai.features import FEATURES
from keiba_ai.model import LEAKAGE_COLUMNS, time_split, validate_no_leakage_features

def test_probs():
    df=pd.DataFrame([
        {"race_id":"r","horse_no":1,"horse_name":"A","ability":30,"suitability":15,"pace":15,"training":7,"paddock":5,"win_odds":3.0},
        {"race_id":"r","horse_no":2,"horse_name":"B","ability":25,"suitability":14,"pace":14,"training":6,"paddock":5,"win_odds":6.0},
    ])
    out=baseline_probabilities(df)
    assert abs(out["win_prob_model"].sum()-1)<1e-9

def test_parsers():
    assert parse_pair_odds("1-8 2.7-2.9","wide").iloc[0]["odds_high"]==2.9
    assert parse_trio_odds("1-8-15 16.3").iloc[0]["selection"]=="1-8-15"

def test_budget():
    ev=pd.DataFrame([{"bet_type":"win","selection":"1","ev":1.4},{"bet_type":"wide","selection":"1-2","ev":1.2}])
    bets=allocate_budget(ev,1500)
    assert bets["stake"].sum()<=1500


def test_time_split_keeps_recent_rows_in_validation():
    df = pd.DataFrame(
        [
            {"race_id": "old", "date": "2026-01-01"},
            {"race_id": "recent", "date": "2026-02-15"},
        ]
    )
    train, valid = time_split(df, holdout_days=30)
    assert train["race_id"].tolist() == ["old"]
    assert valid["race_id"].tolist() == ["recent"]


def test_model_features_do_not_include_post_race_columns():
    assert set(FEATURES).isdisjoint(LEAKAGE_COLUMNS)
    validate_no_leakage_features()
