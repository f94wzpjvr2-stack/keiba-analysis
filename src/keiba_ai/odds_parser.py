import re
import pandas as pd

PAIR_RE = re.compile(r"(\d+)\s*[-－ー]\s*(\d+)\s+([0-9]+(?:\.[0-9]+)?)(?:\s*[-－ー]\s*([0-9]+(?:\.[0-9]+)?))?")
TRIO_RE = re.compile(r"(\d+)\s*[-－ー]\s*(\d+)\s*[-－ー]\s*(\d+)\s+([0-9]+(?:\.[0-9]+)?)")

def parse_pair_odds(text, bet_type):
    rows = []
    for m in PAIR_RE.finditer(text or ""):
        a,b = sorted((int(m.group(1)), int(m.group(2))))
        low = float(m.group(3))
        high = float(m.group(4)) if m.group(4) else low
        rows.append({"bet_type":bet_type,"selection":f"{a}-{b}","odds_low":low,"odds_high":high})
    return pd.DataFrame(rows).drop_duplicates(["bet_type","selection"]) if rows else pd.DataFrame(columns=["bet_type","selection","odds_low","odds_high"])

def parse_trio_odds(text):
    rows = []
    for m in TRIO_RE.finditer(text or ""):
        nums = sorted((int(m.group(1)),int(m.group(2)),int(m.group(3))))
        rows.append({"bet_type":"trio","selection":"-".join(map(str,nums)),"odds_low":float(m.group(4)),"odds_high":float(m.group(4))})
    return pd.DataFrame(rows).drop_duplicates(["bet_type","selection"]) if rows else pd.DataFrame(columns=["bet_type","selection","odds_low","odds_high"])
