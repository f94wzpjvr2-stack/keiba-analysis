import pandas as pd

def allocate_budget(ev_table, budget_ceiling, unit=100, ev_threshold=1.03):
    c=ev_table[ev_table["ev"]>=ev_threshold].copy().sort_values("ev",ascending=False)
    if c.empty:
        return pd.DataFrame(columns=list(ev_table.columns)+["stake"])
    c=c.head(max(1,budget_ceiling//unit))
    w=(c["ev"]-1).clip(lower=.01)
    c["stake"]=((w/w.sum()*budget_ceiling)//unit*unit).astype(int)
    c.loc[c["stake"]==0,"stake"]=unit
    while c["stake"].sum()>budget_ceiling:
        idx=c.sort_values(["ev","stake"]).index[0]
        c.loc[idx,"stake"]-=unit
        if c.loc[idx,"stake"]<=0:
            c=c.drop(idx)
    return c[c["stake"]>0]
