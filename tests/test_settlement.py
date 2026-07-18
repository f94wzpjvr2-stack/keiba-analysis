from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from keiba_ev.result_collector import fetch_official_result
from keiba_ev.settlement import (
    normalize_bets,
    normalize_selection,
    settle_race_bets,
    settle_unsettled_races,
)

RACE_ID = "20260523_東京_R05"
RESULT_URL = "https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde0105202602090520260523%2F0C"

RESULT_HTML = """
<html>
<head><title>レース結果 2026年5月23日（土曜）2回東京9日 5レース</title></head>
<body>
<h1>レース結果 2026年5月23日（土曜）2回東京9日 5レース</h1>
<h2>3歳未勝利</h2>
<div>天候 曇</div><div>芝 良</div>
<p>コース：2,000メートル（芝・左）</p>
<table>
<tr><th>着順</th><th>枠</th><th>馬番</th><th>馬名</th><th>性齢</th><th>負担重量</th><th>騎手名</th><th>タイム</th><th>着差</th><th>コーナー通過順位</th><th>推定上り</th><th>馬体重（増減）</th><th>調教師名</th><th>単勝人気</th></tr>
<tr><td>1</td><td>3</td><td>6</td><td>サンプルA</td><td>牡3</td><td>57.0</td><td>騎手A</td><td>2:00.6</td><td></td><td>1-1</td><td>34.0</td><td>466(+6)</td><td>厩舎A</td><td>1</td></tr>
<tr><td>2</td><td>1</td><td>2</td><td>サンプルB</td><td>牡3</td><td>57.0</td><td>騎手B</td><td>2:00.8</td><td>1</td><td>2-2</td><td>33.6</td><td>478(+4)</td><td>厩舎B</td><td>2</td></tr>
<tr><td>3</td><td>5</td><td>10</td><td>サンプルC</td><td>牡3</td><td>57.0</td><td>騎手C</td><td>2:00.9</td><td>3/4</td><td>3-3</td><td>33.4</td><td>450(0)</td><td>厩舎C</td><td>3</td></tr>
</table>
<h2>払戻金</h2>
<div>単勝</div><div>6</div><div>300円 1番人気</div>
<div>複勝</div><div>6</div><div>120円 1番人気</div><div>2</div><div>180円 2番人気</div><div>10</div><div>250円 3番人気</div>
<div>ワイド</div><div>2-6</div><div>500円 1番人気</div><div>6-10</div><div>700円 2番人気</div><div>2-10</div><div>900円 3番人気</div>
<div>馬連</div><div>2-6</div><div>1,000円 4番人気</div>
<div>馬単</div><div>6-2</div><div>2,000円 5番人気</div>
<div>3連複</div><div>2-6-10</div><div>3,000円 6番人気</div>
<div>3連単</div><div>6-2-10</div><div>6,000円 7番人気</div>
<h3>勝馬の紹介</h3>
</body>
</html>
"""


def result():
    return fetch_official_result(RESULT_URL, fetch_html=lambda _: RESULT_HTML)


def bets(rows):
    return pd.DataFrame(
        [
            {
                "race_id": RACE_ID,
                "bet_type": bet_type,
                "selection": selection,
                "stake": stake,
                "odds_at_prediction": 1.0,
                "estimated_probability": 0.1,
                "expected_value": 1.1,
                "predicted_at": "2026-05-23T12:00:00+09:00",
                "algorithm_version": "test",
            }
            for bet_type, selection, stake in rows
        ]
    )


@pytest.mark.parametrize(
    ("bet_type", "selection", "payout"),
    [
        ("単勝", "6", 300),
        ("複勝", "6", 120),
        ("ワイド", "6－2", 500),
        ("馬連", "6-2", 1000),
        ("馬単", "6 - 2", 2000),
        ("三連複", "10-2-6", 3000),
        ("三連単", "6-2-10", 6000),
    ],
)
def test_each_winning_bet_type_settles(bet_type, selection, payout):
    settled = settle_race_bets(bets([(bet_type, selection, 100)]), result())
    assert bool(settled.iloc[0]["hit"]) is True
    assert settled.iloc[0]["payout_per_100"] == payout
    assert settled.iloc[0]["payout_amount"] == payout


def test_losing_bet_settles_as_zero_payout():
    settled = settle_race_bets(bets([("単勝", "1", 100)]), result())
    row = settled.iloc[0]
    assert bool(row["hit"]) is False
    assert row["payout_per_100"] == 0
    assert row["payout_amount"] == 0
    assert row["profit"] == -100


@pytest.mark.parametrize(("stake", "expected"), [(100, 300), (200, 600), (500, 1500)])
def test_payout_amount_scales_by_stake(stake, expected):
    settled = settle_race_bets(bets([("単勝", "6", stake)]), result())
    assert settled.iloc[0]["payout_amount"] == expected


def test_rejects_non_100_yen_stake():
    with pytest.raises(ValueError, match="100-yen"):
        normalize_bets(bets([("単勝", "6", 150)]))


def test_selection_normalization_by_bet_type():
    assert normalize_selection("６", "単勝") == "6"
    assert normalize_selection("6 － 2", "ワイド") == "2-6"
    assert normalize_selection("6-2", "馬単") == "6-2"
    assert normalize_selection("10－2－6", "三連複") == "2-6-10"
    assert normalize_selection("6 2 10", "三連単") == "6-2-10"


def write_store(root: Path, bet_rows: pd.DataFrame, races: pd.DataFrame) -> None:
    root.mkdir(parents=True, exist_ok=True)
    bet_rows.to_csv(root / "bets.csv", index=False)
    races.to_csv(root / "races.csv", index=False)
    pd.DataFrame(columns=["race_id"]).to_csv(root / "results.csv", index=False)


def test_double_settlement_is_prevented(tmp_path: Path):
    write_store(
        tmp_path,
        bets([("単勝", "6", 100)]),
        pd.DataFrame([{"race_id": RACE_ID, "result_source_url": RESULT_URL}]),
    )
    first = settle_unsettled_races(tmp_path, fetch_html=lambda _: RESULT_HTML, request_interval=2.0)
    second = settle_unsettled_races(tmp_path, fetch_html=lambda _: RESULT_HTML, request_interval=2.0)
    saved = pd.read_csv(tmp_path / "results.csv")
    assert first["summary"]["settled_races"] == 1
    assert second["summary"]["settled_races"] == 0
    assert len(saved) == 1


def test_unpublished_result_is_skipped(tmp_path: Path):
    write_store(
        tmp_path,
        bets([("単勝", "6", 100)]),
        pd.DataFrame([{"race_id": RACE_ID, "result_source_url": RESULT_URL}]),
    )
    out = settle_unsettled_races(tmp_path, fetch_html=lambda _: "<html>未確定</html>")
    assert out["summary"]["skipped_races"] == 1
    assert pd.read_csv(tmp_path / "results.csv").empty


def test_one_fetch_failure_does_not_stop_other_races(tmp_path: Path):
    other_race = "20260523_東京_R06"
    root = tmp_path
    both_bets = pd.concat(
        [
            bets([("単勝", "6", 100)]),
            bets([("単勝", "6", 100)]).assign(race_id=other_race),
        ],
        ignore_index=True,
    )
    both_bets.to_csv(root / "bets.csv", index=False)
    pd.DataFrame(
        [
            {"race_id": RACE_ID, "result_source_url": RESULT_URL},
            {"race_id": other_race, "result_source_url": "https://example.invalid/result"},
        ]
    ).to_csv(root / "races.csv", index=False)
    pd.DataFrame(columns=["race_id"]).to_csv(root / "results.csv", index=False)

    def fetch(url):
        if "example.invalid" in url:
            raise RuntimeError("network failed")
        return RESULT_HTML

    out = settle_unsettled_races(root, fetch_html=fetch)
    assert out["summary"]["settled_races"] == 1
    assert out["summary"]["errors"] == 1
    assert (root / "automation" / "result_import_errors.csv").exists()


def test_pre_race_bet_information_is_not_overwritten(tmp_path: Path):
    original = bets([("単勝", "6", 100)])
    write_store(
        tmp_path,
        original,
        pd.DataFrame([{"race_id": RACE_ID, "result_source_url": RESULT_URL}]),
    )
    settle_unsettled_races(tmp_path, fetch_html=lambda _: RESULT_HTML)
    after = pd.read_csv(tmp_path / "bets.csv")
    after["selection"] = after["selection"].astype(str)
    pd.testing.assert_frame_equal(original, after, check_dtype=False)


def test_result_columns_do_not_include_prediction_features():
    settled = settle_race_bets(bets([("単勝", "6", 100)]), result())
    forbidden = {"estimated_probability", "expected_value", "odds_at_prediction", "predicted_at"}
    assert forbidden.isdisjoint(settled.columns)
