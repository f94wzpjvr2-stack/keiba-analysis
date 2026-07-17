import itertools

import pandas as pd

def single_win_ev(h):
    out = h.copy()
    out["bet_type"]="win"
    out["selection"]=out["horse_no"].astype(int).astype(str)
    out["odds"]=out["win_odds"]
    out["hit_prob"]=out["win_prob_model"]
    out["ev"]=out["odds"]*out["hit_prob"]
    return out[["bet_type","selection","hit_prob","odds","ev"]]

def pair_probabilities(h, mode):
    p=dict(zip(h["horse_no"].astype(int),h["win_prob_model"].astype(float)))
    result={}
    for a,b in itertools.combinations(sorted(p),2):
        result[f"{a}-{b}"] = min(1.0,(4.2 if mode=="wide" else 2.0)*p[a]*p[b])
    return result

def trio_probabilities(h):
    p=dict(zip(h["horse_no"].astype(int),h["win_prob_model"].astype(float)))
    return {f"{a}-{b}-{c}":min(1.0,10.5*p[a]*p[b]*p[c]) for a,b,c in itertools.combinations(sorted(p),3)}

def combine_ev(prob_map, odds_df, bet_type):
    if odds_df.empty:
        return pd.DataFrame(columns=["bet_type","selection","hit_prob","odds","ev"])
    out=odds_df.copy()
    out["hit_prob"]=out["selection"].map(prob_map)
    out["odds"]=out["odds_low"]
    out["ev"]=out["hit_prob"]*out["odds"]
    out["bet_type"]=bet_type
    return out[["bet_type","selection","hit_prob","odds","ev"]].dropna()
