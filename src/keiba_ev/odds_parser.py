from __future__ import annotations

import re

import pandas as pd

PAIR_RE = re.compile(r"(?P<a>\d{1,2})\s*[-－]\s*(?P<b>\d{1,2})\s+[\t ]*(?P<odds>\d+(?:\.\d+)?)")
WIDE_RE = re.compile(
    r"(?P<a>\d{1,2})\s*[-－]\s*(?P<b>\d{1,2})\s+[\t ]*(?P<low>\d+(?:\.\d+)?)\s*[-－]\s*(?P<high>\d+(?:\.\d+)?)"
)
TRIO_RE = re.compile(
    r"(?:^|\s)(?P<a>\d{1,2})\s*[-－]\s*(?P<b>\d{1,2})\s*[-－]\s*(?P<c>\d{1,2})\s+[\t ]*(?P<odds>\d+(?:\.\d+)?)"
)


def _canonical_pair(a: int, b: int) -> str:
    first, second = sorted((a, b))
    return f"{first}-{second}"


def _canonical_trio(a: int, b: int, c: int) -> str:
    return "-".join(map(str, sorted((a, b, c))))


def parse_wide_text(text: str, basis: str = "low") -> pd.DataFrame:
    """Parse wide odds text with ranges such as `1-2 18.6-20.0`."""
    rows = []
    for match in WIDE_RE.finditer(text):
        low = float(match.group("low"))
        high = float(match.group("high"))
        if basis == "low":
            odds = low
        elif basis == "mid":
            odds = (low + high) / 2
        elif basis == "high":
            odds = high
        else:
            raise ValueError("basis must be low, mid or high")
        rows.append(
            {
                "selection": _canonical_pair(int(match.group("a")), int(match.group("b"))),
                "odds": odds,
                "odds_low": low,
                "odds_high": high,
            }
        )
    return pd.DataFrame(rows).drop_duplicates("selection", keep="last")


def parse_quinella_text(text: str) -> pd.DataFrame:
    """Parse quinella odds text such as `1-2 68.1`."""
    rows = []
    for line in text.splitlines():
        if re.search(r"\d+\s*[-－]\s*\d+\s+\d+(?:\.\d+)?\s*[-－]\s*\d", line):
            continue
        match = PAIR_RE.search(line)
        if match:
            rows.append(
                {
                    "selection": _canonical_pair(int(match.group("a")), int(match.group("b"))),
                    "odds": float(match.group("odds")),
                }
            )
    return pd.DataFrame(rows).drop_duplicates("selection", keep="last")


def parse_trio_text(text: str) -> pd.DataFrame:
    """Parse trio odds lines. Popularity columns before the selection are allowed."""
    rows = []
    for line in text.splitlines():
        match = TRIO_RE.search(line)
        if match:
            rows.append(
                {
                    "selection": _canonical_trio(
                        int(match.group("a")), int(match.group("b")), int(match.group("c"))
                    ),
                    "odds": float(match.group("odds")),
                }
            )
    return pd.DataFrame(rows).drop_duplicates("selection", keep="last")
