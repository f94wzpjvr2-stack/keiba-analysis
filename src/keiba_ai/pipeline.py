from pathlib import Path
import pandas as pd
from .baseline import baseline_probabilities
from .model import load_model, predict_win_prob
from .odds_parser import parse_pair_odds, parse_trio_odds
from .ev import single_win_ev, pair_probabilities, trio_probabilities, combine_ev
from .betting import allocate_budget

def run_analysis(race, horses, wide_text="", quinella_text="", trio_text="", model_path=None):
    h=horses.copy()
    h["race_id"]=race["race_id"]
    if model_path and Path(model_path).exists():
        scored=predict_win_prob(load_model(model_path),h)
        source="machine_learning"
    else:
        scored=baseline_probabilities(h)
        source="baseline"
    tables=[single_win_ev(scored)]
    w=parse_pair_odds(wide_text,"wide")
    q=parse_pair_odds(quinella_text,"quinella")
    t=parse_trio_odds(trio_text)
    if not w.empty: tables.append(combine_ev(pair_probabilities(scored,"wide"),w,"wide"))
    if not q.empty: tables.append(combine_ev(pair_probabilities(scored,"quinella"),q,"quinella"))
    if not t.empty: tables.append(combine_ev(trio_probabilities(scored),t,"trio"))
    ev_table=pd.concat(tables,ignore_index=True)
    bets=allocate_budget(ev_table,race["budget_ceiling"])
    return {"source":source,"horses":scored,"ev_table":ev_table,"bets":bets}
