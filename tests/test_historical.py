from pathlib import Path

import pandas as pd

from keiba_ev.historical import (
    extract_jra_navigation_urls,
    import_recent_jra_races,
    parse_jra_result_html,
)

SAMPLE_URL = (
    "https://www.jra.go.jp/JRADB/accessS.html?"
    "CNAME=pw01sde0105202602090520260523%2F0C"
)

SAMPLE_HTML = """
<html>
<head><title>レース結果 2026年5月23日（土曜）2回東京9日 5レース</title></head>
<body>
<h1>レース結果 2026年5月23日（土曜）2回東京9日 5レース</h1>
<div>発走時刻：12時20分</div>
<div>天候 曇</div><div>芝 良</div>
<h2>3歳未勝利</h2>
<p>コース：2,000メートル（芝・左）</p>
<table>
<tr><th>着順</th><th>枠</th><th>馬番</th><th>馬名</th><th>性齢</th><th>負担重量</th><th>騎手名</th><th>タイム</th><th>着差</th><th>コーナー通過順位</th><th>推定上り</th><th>馬体重（増減）</th><th>調教師名</th><th>単勝人気</th></tr>
<tr><td>1</td><td>4</td><td>7</td><td>ボニープリンス</td><td>牡3</td><td>57.0</td><td>D.レーン</td><td>2:00.6</td><td></td><td>2-3-3</td><td>34.0</td><td>466(+6)</td><td>大竹 正博</td><td>1</td></tr>
<tr><td>2</td><td>8</td><td>15</td><td>ヤマメホープ</td><td>牡3</td><td>57.0</td><td>田辺 裕信</td><td>2:00.8</td><td>1</td><td>10-9-7</td><td>33.6</td><td>478(+4)</td><td>久保田 貴士</td><td>6</td></tr>
<tr><td>3</td><td>1</td><td>2</td><td>ヴァルカンテソーロ</td><td>牡3</td><td>57.0</td><td>柴田 大知</td><td>2:00.9</td><td>3/4</td><td>13-12-10</td><td>33.4</td><td>450(0)</td><td>嘉藤 貴行</td><td>5</td></tr>
</table>
<h2>払戻金</h2>
<div>単勝</div><div>7</div><div>310 円</div><div>1 番人気</div>
<div>複勝</div><div>7</div><div>140 円</div><div>1 番人気</div><div>15</div><div>210 円</div><div>6 番人気</div><div>2</div><div>160 円</div><div>3 番人気</div>
<div>ワイド</div><div>7-15</div><div>510 円</div><div>6 番人気</div><div>2-7</div><div>550 円</div><div>8 番人気</div><div>2-15</div><div>790 円</div><div>12 番人気</div>
<div>馬連</div><div>7-15</div><div>1,410 円</div><div>6 番人気</div>
<div>3連複</div><div>2-7-15</div><div>3,610 円</div><div>15 番人気</div>
<h3>勝馬の紹介</h3>
<a href="/JRADB/accessS.html?CNAME=pw01sde0105202602090620260523%2F0C">6レース</a>
</body>
</html>
"""


def complex_jra_html() -> str:
    runner_rows = []
    for horse_no in range(1, 17):
        frame_no = (horse_no + 1) // 2
        frame_cell = (
            f'<td rowspan="2"><img class="waku_{frame_no}" '
            f'src="/JRADB/img/waku{frame_no}.png" alt="枠{frame_no}"></td>'
            if horse_no % 2 == 1
            else ""
        )
        runner_rows.append(
            "<tr>"
            f"<td>{horse_no}</td>"
            f"{frame_cell}"
            f"<td>{horse_no}</td>"
            f"<td>サンプル{horse_no:02d}</td>"
            "<td>牡3</td><td>57.0</td><td>騎手</td>"
            f"<td>1:{34 + horse_no:02d}.0</td><td></td><td>1-1</td>"
            "<td>35.0</td><td>480(+0)</td><td>厩舎</td>"
            f"<td>{horse_no}</td>"
            "</tr>"
        )
    return f"""
<html>
<head><title>JRA レース結果 検索ウィンドウ</title></head>
<body>
<nav><a>払戻金</a><a>検索ウィンドウ</a></nav>
<h1>レース結果 2026年5月23日（土曜）2回東京9日 11レース</h1>
<h2>検索ウィンドウ</h2>
<h3>欅ステークス</h3>
<div>発走時刻：15時45分</div>
<div>天候 晴</div><div>ダート 良</div>
<p>コース：1,400メートル（ダート・左）</p>
<table>
<tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th><th>性齢</th><th>負担重量</th><th>騎手名</th><th>タイム</th><th>着差</th><th>コーナー通過順位</th><th>推定上り</th><th>馬体重（増減）</th><th>調教師名</th><th>単勝人気</th></tr>
{''.join(runner_rows)}
</table>
<h2>払戻金</h2>
<div>単勝</div><div>5</div><div>1,570円 7番人気</div>
<div>複勝</div><div>5</div><div>360</div><div>円</div><div>7</div><div>番人気</div>
<div>8</div><div>170円</div><div>2番人気</div>
<div>12</div><div>240 円</div><div>4 番人気</div>
<div>枠連</div><div>3-4</div><div>1,880円 8番人気</div>
<div>ワイド</div><div>5-8</div><div>740</div><div>円</div><div>8</div><div>番人気</div>
<div>5-12</div><div>1,320円 18番人気</div>
<div>8-12</div><div>620 円</div><div>5 番人気</div>
<div>馬連</div><div>5-8</div><div>3,120円 13番人気</div>
<div>馬単</div><div>5-8</div><div>7,800</div><div>円</div><div>31</div><div>番人気</div>
<div>3連複</div><div>5-8-12</div><div>5,640円 20番人気</div>
<div>3連単</div><div>5-8-12</div><div>42,900</div><div>円</div><div>151</div><div>番人気</div>
<h3>勝馬の紹介</h3>
</body>
</html>
"""


def test_parse_jra_result_html():
    parsed = parse_jra_result_html(SAMPLE_HTML, SAMPLE_URL)
    race = parsed.race.iloc[0]
    assert race["race_id"] == "20260523_東京_R05"
    assert race["distance"] == 2000
    assert race["surface"] == "芝"
    assert race["going"] == "良"
    assert len(parsed.runners) == 3
    assert parsed.runners.iloc[0]["body_weight"] == 466
    assert parsed.runners.iloc[0]["body_weight_change"] == 6
    assert set(parsed.payouts["bet_type"]) >= {"win", "place", "wide", "quinella", "trio"}
    trio = parsed.payouts[parsed.payouts["bet_type"] == "trio"].iloc[0]
    assert trio["selection"] == "2-7-15"
    assert trio["payout_per_100"] == 3610


def test_extract_navigation_urls_is_same_domain_and_deduplicated():
    urls = extract_jra_navigation_urls(SAMPLE_HTML, SAMPLE_URL)
    assert len(urls) == 1
    assert urls[0].startswith("https://www.jra.go.jp/JRADB/accessS.html?CNAME=")


def test_import_is_idempotent(tmp_path: Path):
    index_url = "https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde0100"
    pages = {
        index_url: SAMPLE_HTML,
        SAMPLE_URL: SAMPLE_HTML,
    }

    def fetch(url: str) -> str:
        return pages.get(url, SAMPLE_HTML)

    first = import_recent_jra_races(
        race_count=1,
        output_dir=tmp_path,
        seed_urls=[index_url],
        fetch_html=fetch,
        request_interval=0,
        max_pages=5,
    )
    second = import_recent_jra_races(
        race_count=1,
        output_dir=tmp_path,
        seed_urls=[index_url],
        fetch_html=fetch,
        request_interval=0,
        max_pages=5,
    )
    assert first.iloc[0]["new_races"] == 1
    assert second.iloc[0]["new_races"] == 0
    races = pd.read_csv(tmp_path / "historical_races.csv")
    assert len(races) == 1


def test_parse_handles_cancelled_dnf_dead_heat_and_multiple_payouts():
    html = SAMPLE_HTML.replace(
        "<tr><td>2</td><td>8</td><td>15</td>",
        "<tr><td>1</td><td>8</td><td>15</td>",
    ).replace(
        "<tr><td>3</td><td>1</td><td>2</td>",
        "<tr><td>中止</td><td>1</td><td>2</td>",
    )
    parsed = parse_jra_result_html(html, SAMPLE_URL)
    assert parsed.runners["finish_position"].tolist() == ["1", "1", "中止"]
    place = parsed.payouts[parsed.payouts["bet_type"] == "place"]
    wide = parsed.payouts[parsed.payouts["bet_type"] == "wide"]
    assert len(place) == 3
    assert len(wide) == 3


def test_import_logs_bad_pages_without_stopping(tmp_path: Path):
    index_url = "https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde0100"
    bad_url = (
        "https://www.jra.go.jp/JRADB/accessS.html?"
        "CNAME=pw01sde0105202602090120260523%2F0C"
    )
    index_html = (
        SAMPLE_HTML
        + f'<a href="{bad_url}">bad</a>'
        + f'<a href="{SAMPLE_URL}">good</a>'
    )
    pages = {
        index_url: index_html,
        bad_url: "<html><body>レース結果 着順 払戻金</body></html>",
        SAMPLE_URL: SAMPLE_HTML,
    }

    def fetch(url: str) -> str:
        return pages[url]

    summary = import_recent_jra_races(
        race_count=2,
        output_dir=tmp_path,
        seed_urls=[index_url],
        fetch_html=fetch,
        request_interval=0,
        max_pages=5,
    )
    assert summary.iloc[0]["new_races"] == 1
    assert summary.iloc[0]["errors"] >= 1
    errors = pd.read_csv(tmp_path / "historical_import_errors.csv")
    assert not errors.empty


def test_parse_realistic_jra_result_with_16_runners_and_12_payouts():
    parsed = parse_jra_result_html(complex_jra_html(), SAMPLE_URL)
    race = parsed.race.iloc[0]
    assert race["race_name"] == "欅ステークス"
    assert race["race_name"] != "検索ウィンドウ"
    assert len(parsed.runners) == 16
    assert not parsed.runners["frame_no"].isna().any()
    assert parsed.runners["frame_no"].tolist() == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8]
    assert len(parsed.payouts) == 12
    counts = parsed.payouts["bet_type"].value_counts().to_dict()
    assert counts == {
        "place": 3,
        "wide": 3,
        "win": 1,
        "bracket_quinella": 1,
        "quinella": 1,
        "exacta": 1,
        "trio": 1,
        "trifecta": 1,
    }
    win = parsed.payouts[parsed.payouts["bet_type"] == "win"].iloc[0]
    exacta = parsed.payouts[parsed.payouts["bet_type"] == "exacta"].iloc[0]
    assert win["payout_per_100"] == 1570
    assert win["popularity"] == 7
    assert exacta["payout_per_100"] == 7800
    assert exacta["popularity"] == 31


def test_realistic_jra_import_is_idempotent(tmp_path: Path):
    index_url = "https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde0100"
    pages = {
        index_url: complex_jra_html(),
        SAMPLE_URL: complex_jra_html(),
    }

    def fetch(url: str) -> str:
        return pages.get(url, complex_jra_html())

    first = import_recent_jra_races(
        race_count=1,
        output_dir=tmp_path,
        seed_urls=[index_url],
        fetch_html=fetch,
        request_interval=0,
        max_pages=5,
    )
    second = import_recent_jra_races(
        race_count=1,
        output_dir=tmp_path,
        seed_urls=[index_url],
        fetch_html=fetch,
        request_interval=0,
        max_pages=5,
    )
    assert first.iloc[0]["new_races"] == 1
    assert first.iloc[0]["new_runner_rows"] == 16
    assert first.iloc[0]["new_payout_rows"] == 12
    assert second.iloc[0]["new_races"] == 0
    assert second.iloc[0]["new_runner_rows"] == 0
    assert second.iloc[0]["new_payout_rows"] == 0
