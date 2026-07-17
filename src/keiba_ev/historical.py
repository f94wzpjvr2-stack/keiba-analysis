from __future__ import annotations

import html as html_lib
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Callable, Iterable, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

JRA_BASE_URL = "https://www.jra.go.jp"
DEFAULT_JRA_RESULT_INDEX_URL = (
    "https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde0100"
)

HISTORICAL_SCHEMAS: dict[str, list[str]] = {
    "historical_races.csv": [
        "race_id",
        "date",
        "course",
        "meeting_no",
        "meeting_day",
        "race_no",
        "race_name",
        "surface",
        "distance",
        "direction",
        "going",
        "weather",
        "start_time",
        "source_url",
        "imported_at",
    ],
    "historical_runners.csv": [
        "race_id",
        "finish_position",
        "frame_no",
        "horse_no",
        "horse_name",
        "sex_age",
        "carried_weight",
        "jockey",
        "finish_time",
        "margin",
        "corner_positions",
        "final_3f",
        "body_weight",
        "body_weight_change",
        "trainer",
        "popularity",
        "source_url",
        "imported_at",
    ],
    "historical_payouts.csv": [
        "race_id",
        "bet_type",
        "selection",
        "payout_per_100",
        "popularity",
        "source_url",
        "imported_at",
    ],
    "historical_import_errors.csv": [
        "source_url",
        "error_type",
        "error_message",
        "occurred_at",
    ],
}

BET_TYPE_MAP = {
    "単勝": "win",
    "複勝": "place",
    "枠連": "bracket_quinella",
    "ワイド": "wide",
    "馬連": "quinella",
    "馬単": "exacta",
    "3連複": "trio",
    "三連複": "trio",
    "3連単": "trifecta",
    "三連単": "trifecta",
}

_RESULT_URL_RE = re.compile(
    r"(?:https?://www\.jra\.go\.jp)?/JRADB/accessS\.html\?CNAME=[^\"'<>\s]+",
    re.IGNORECASE,
)

_METADATA_RE = re.compile(
    r"(?P<year>\d{4})年\s*(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日"
    r".*?(?P<meeting_no>\d+)回\s*(?P<course>[^\d\s]+?)\s*(?P<meeting_day>\d+)日"
    r".*?(?P<race_no>\d+)レース",
    re.DOTALL,
)

_COURSE_RE = re.compile(
    r"コース：\s*([\d,]+)\s*メートル\s*（(芝|ダート|障害)・([^）]+)）"
)

_NAVIGATION_HEADINGS = {
    "検索ウィンドウ",
    "メニュー",
    "ナビゲーション",
    "レース結果",
    "払戻金",
    "勝馬の紹介",
    "競走中の出来事等",
    "開催選択へ戻る",
}


class HistoricalImportError(RuntimeError):
    """Raised when a JRA page cannot be parsed as a completed race result."""


@dataclass(frozen=True)
class ParsedHistoricalRace:
    race: pd.DataFrame
    runners: pd.DataFrame
    payouts: pd.DataFrame


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _flatten_columns(columns: Iterable[object]) -> list[str]:
    flattened: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            parts = [_clean_text(part) for part in column if _clean_text(part) != "nan"]
            flattened.append("".join(parts))
        else:
            flattened.append(_clean_text(column))
    return flattened


def _node_text(node) -> str:
    parts: list[str] = []
    text = _clean_text(node.get_text(" ", strip=True))
    if text:
        parts.append(text)
    for child in node.find_all(True):
        for attr in ("alt", "title", "aria-label"):
            value = _clean_text(child.get(attr))
            if value:
                parts.append(value)
        class_text = " ".join(child.get("class", []))
        src_text = _clean_text(child.get("src"))
        for value in (class_text, src_text):
            match = re.search(r"(?:枠|waku|frame)[_-]?([1-8])", value, re.IGNORECASE)
            if match:
                parts.append(match.group(1))
    return _clean_text(" ".join(parts))


def _table_to_dataframe(table) -> pd.DataFrame:
    grid: list[list[str]] = []
    rowspans: dict[tuple[int, int], str] = {}
    for row_index, row in enumerate(table.find_all("tr")):
        values: list[str] = []
        column_index = 0
        while (row_index, column_index) in rowspans:
            values.append(rowspans.pop((row_index, column_index)))
            column_index += 1
        for cell in row.find_all(["th", "td"]):
            while (row_index, column_index) in rowspans:
                values.append(rowspans.pop((row_index, column_index)))
                column_index += 1
            value = _node_text(cell)
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            for offset in range(colspan):
                values.append(value)
                if rowspan > 1:
                    for extra_row in range(1, rowspan):
                        rowspans[(row_index + extra_row, column_index + offset)] = value
            column_index += colspan
        while (row_index, column_index) in rowspans:
            values.append(rowspans.pop((row_index, column_index)))
            column_index += 1
        if values:
            grid.append(values)

    if not grid:
        return pd.DataFrame()
    width = max(len(row) for row in grid)
    normalized = [row + [""] * (width - len(row)) for row in grid]
    header_index = 0
    for index, row in enumerate(normalized):
        compact = {re.sub(r"\s+", "", value) for value in row}
        if "着順" in compact and "馬番" in compact and "馬名" in compact:
            header_index = index
            break
    headers = _flatten_columns(normalized[header_index])
    data = normalized[header_index + 1 :]
    return pd.DataFrame(data, columns=headers)


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(html_lib.unescape(url))
    if not parsed.netloc:
        parsed = urlparse(urljoin(JRA_BASE_URL, url))
    if parsed.netloc.lower() != "www.jra.go.jp":
        return ""
    query = parse_qs(parsed.query, keep_blank_values=True)
    cname = query.get("CNAME", [""])[0]
    if not cname.lower().startswith("pw01sde"):
        return ""
    normalized_query = urlencode({"CNAME": cname})
    return urlunparse(("https", "www.jra.go.jp", parsed.path, "", normalized_query, ""))


def extract_jra_navigation_urls(page_html: str, current_url: str) -> list[str]:
    """Extract JRA race-result and result-navigation URLs from one page."""
    soup = BeautifulSoup(page_html, "html.parser")
    candidates: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        candidate = _canonicalize_url(urljoin(current_url, anchor["href"]))
        if candidate:
            candidates.add(candidate)

    for match in _RESULT_URL_RE.findall(page_html):
        candidate = _canonicalize_url(urljoin(current_url, match))
        if candidate:
            candidates.add(candidate)

    return sorted(candidates)


def _find_result_table(page_html: str) -> pd.DataFrame:
    soup = BeautifulSoup(page_html, "html.parser")
    for table_node in soup.find_all("table"):
        table = _table_to_dataframe(table_node)
        if table.empty:
            continue
        normalized = {re.sub(r"\s+", "", c): c for c in table.columns}
        if "着順" in normalized and "馬番" in normalized and "馬名" in normalized:
            return table

    try:
        tables = pd.read_html(StringIO(page_html))
    except ValueError as exc:
        raise HistoricalImportError("着順表を検出できませんでした") from exc

    for table in tables:
        table = table.copy()
        table.columns = _flatten_columns(table.columns)
        normalized = {re.sub(r"\s+", "", c): c for c in table.columns}
        if "着順" in normalized and "馬番" in normalized and "馬名" in normalized:
            return table
    raise HistoricalImportError("着順・馬番・馬名を含む結果表がありません")


def _column(table: pd.DataFrame, *aliases: str) -> pd.Series:
    normalized = {re.sub(r"\s+", "", c): c for c in table.columns}
    for alias in aliases:
        key = re.sub(r"\s+", "", alias)
        if key in normalized:
            return table[normalized[key]]
    return pd.Series([pd.NA] * len(table), index=table.index, dtype="object")


def _parse_body_weight(value: object) -> tuple[object, object]:
    text = _clean_text(value)
    match = re.search(r"(?P<weight>\d+)\s*\((?P<change>[^)]*)\)", text)
    if not match:
        return pd.NA, pd.NA
    weight = int(match.group("weight"))
    change_text = match.group("change").replace("＋", "+").replace("−", "-")
    change_match = re.search(r"[+-]?\d+", change_text)
    change = int(change_match.group(0)) if change_match else pd.NA
    return weight, change


def _parse_metadata(soup: BeautifulSoup, source_url: str) -> dict[str, object]:
    page_text = _clean_text(soup.get_text(" ", strip=True))
    title_text = _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    heading_text = " ".join(
        _clean_text(node.get_text(" ", strip=True))
        for node in soup.find_all(["h1", "h2"])
    )
    metadata_match = _METADATA_RE.search(" ".join([title_text, heading_text, page_text]))
    if not metadata_match:
        raise HistoricalImportError("開催日・競馬場・レース番号を解析できませんでした")

    year = int(metadata_match.group("year"))
    month = int(metadata_match.group("month"))
    day = int(metadata_match.group("day"))
    course = metadata_match.group("course")
    race_no = int(metadata_match.group("race_no"))
    race_date = f"{year:04d}-{month:02d}-{day:02d}"
    race_id = f"{year:04d}{month:02d}{day:02d}_{course}_R{race_no:02d}"

    race_name = ""
    for node in soup.find_all(["h2", "h3"]):
        candidate = _clean_text(node.get_text(" ", strip=True))
        if not candidate:
            continue
        if candidate in _NAVIGATION_HEADINGS:
            continue
        if "検索ウィンドウ" in candidate or "レース結果" in candidate:
            continue
        if any(bet_type in candidate for bet_type in BET_TYPE_MAP):
            continue
        race_name = candidate
        break

    course_match = _COURSE_RE.search(page_text)
    distance: object = pd.NA
    surface = ""
    direction = ""
    if course_match:
        distance = int(course_match.group(1).replace(",", ""))
        surface = course_match.group(2)
        direction = course_match.group(3)

    weather_match = re.search(r"天候\s*([一-龥ぁ-んァ-ン]+)", page_text)
    going_match = re.search(r"(?:芝|ダート|障害)\s*(良|稍重|重|不良)", page_text)
    start_match = re.search(r"発走時刻[:：]\s*(\d{1,2})時\s*(\d{2})分", page_text)

    return {
        "race_id": race_id,
        "date": race_date,
        "course": course,
        "meeting_no": int(metadata_match.group("meeting_no")),
        "meeting_day": int(metadata_match.group("meeting_day")),
        "race_no": race_no,
        "race_name": race_name,
        "surface": surface,
        "distance": distance,
        "direction": direction,
        "going": going_match.group(1) if going_match else "",
        "weather": weather_match.group(1) if weather_match else "",
        "start_time": (
            f"{int(start_match.group(1)):02d}:{int(start_match.group(2)):02d}"
            if start_match
            else ""
        ),
        "source_url": source_url,
    }


def _parse_runners(
    table: pd.DataFrame,
    race_id: str,
    source_url: str,
    imported_at: str,
) -> pd.DataFrame:
    finish = _column(table, "着順")
    horse_no = _column(table, "馬番")
    horse_name = _column(table, "馬名")
    frame_no = _column(table, "枠", "枠番")
    sex_age = _column(table, "性齢")
    carried_weight = _column(table, "負担重量")
    jockey = _column(table, "騎手名", "騎手")
    finish_time = _column(table, "タイム")
    margin = _column(table, "着差")
    corner_positions = _column(table, "コーナー通過順位")
    final_3f = _column(table, "推定上り", "上り")
    body_weight_raw = _column(table, "馬体重（増減）", "馬体重(増減)", "馬体重")
    trainer = _column(table, "調教師名", "調教師")
    popularity = _column(table, "単勝人気", "人気")

    rows: list[dict[str, object]] = []
    for index in table.index:
        horse_no_text = _clean_text(horse_no.loc[index])
        horse_name_text = _clean_text(horse_name.loc[index])
        if not horse_no_text or not horse_name_text or horse_no_text == "nan":
            continue
        number_match = re.search(r"\d+", horse_no_text)
        if not number_match:
            continue
        body_weight, body_weight_change = _parse_body_weight(body_weight_raw.loc[index])
        popularity_match = re.search(r"\d+", _clean_text(popularity.loc[index]))
        frame_match = re.search(r"\d+", _clean_text(frame_no.loc[index]))
        rows.append(
            {
                "race_id": race_id,
                "finish_position": _clean_text(finish.loc[index]),
                "frame_no": int(frame_match.group(0)) if frame_match else pd.NA,
                "horse_no": int(number_match.group(0)),
                "horse_name": horse_name_text,
                "sex_age": _clean_text(sex_age.loc[index]),
                "carried_weight": _clean_text(carried_weight.loc[index]),
                "jockey": _clean_text(jockey.loc[index]),
                "finish_time": _clean_text(finish_time.loc[index]),
                "margin": _clean_text(margin.loc[index]),
                "corner_positions": _clean_text(corner_positions.loc[index]),
                "final_3f": _clean_text(final_3f.loc[index]),
                "body_weight": body_weight,
                "body_weight_change": body_weight_change,
                "trainer": _clean_text(trainer.loc[index]),
                "popularity": int(popularity_match.group(0)) if popularity_match else pd.NA,
                "source_url": source_url,
                "imported_at": imported_at,
            }
        )

    if len(rows) < 2:
        raise HistoricalImportError("出走馬を2頭以上解析できませんでした")
    return pd.DataFrame(rows, columns=HISTORICAL_SCHEMAS["historical_runners.csv"])


def _looks_like_selection(text: str, bet_type: str) -> bool:
    if bet_type in {"win", "place"}:
        return bool(re.fullmatch(r"\d+", text))
    if bet_type in {"wide", "quinella", "bracket_quinella", "exacta"}:
        return bool(re.fullmatch(r"\d+[-－ー]\d+", text))
    if bet_type in {"trio", "trifecta"}:
        return bool(re.fullmatch(r"\d+[-－ー]\d+[-－ー]\d+", text))
    return False


def _normalize_token(text: str) -> str:
    return (
        _clean_text(text)
        .replace("３", "3")
        .replace("－", "-")
        .replace("ー", "-")
        .replace("–", "-")
    )


def _payout_section_tokens(soup: BeautifulSoup) -> list[str]:
    tokens = [_normalize_token(line) for line in soup.get_text("\n", strip=True).splitlines()]
    tokens = [token for token in tokens if token]
    payout_indexes = [index for index, token in enumerate(tokens) if token == "払戻金"]
    if not payout_indexes:
        return tokens

    best_section: list[str] = []
    best_score = -1
    for start_index in payout_indexes:
        end_index = len(tokens)
        for marker in ("勝馬の紹介", "競走中の出来事等", "開催選択へ戻る"):
            try:
                marker_index = tokens.index(marker, start_index + 1)
                end_index = min(end_index, marker_index)
            except ValueError:
                pass
        section = tokens[start_index + 1 : end_index]
        bet_type_count = sum(1 for token in section if token in BET_TYPE_MAP)
        payout_count = sum(1 for token in section if re.search(r"[\d,]+\s*円", token))
        score = bet_type_count * 10 + payout_count
        if score > best_score:
            best_score = score
            best_section = section
    return best_section


def _parse_payout_and_popularity(
    tokens: Sequence[str],
    start_index: int,
) -> tuple[int | None, int | None, int]:
    payout: int | None = None
    popularity: int | None = None
    pending_payout_number: str | None = None
    pending_popularity_number: int | None = None
    next_index = start_index

    for index, token in enumerate(tokens[start_index : min(start_index + 10, len(tokens))], start_index):
        next_index = index + 1
        normalized = token.replace(" ", "")
        if normalized in BET_TYPE_MAP:
            next_index = index
            break
        payout_match = re.search(r"([\d,]+)円", normalized)
        if payout_match and payout is None:
            payout = int(payout_match.group(1).replace(",", ""))
        elif payout is None and re.fullmatch(r"[\d,]+", normalized):
            pending_payout_number = normalized
        elif payout is None and normalized == "円" and pending_payout_number is not None:
            payout = int(pending_payout_number.replace(",", ""))

        popularity_match = re.search(r"(\d+)番人気", normalized)
        if popularity_match:
            popularity = int(popularity_match.group(1))
            break
        if re.fullmatch(r"\d+", normalized):
            pending_popularity_number = int(normalized)
        elif normalized == "番人気" and pending_popularity_number is not None:
            popularity = pending_popularity_number
            break

    return payout, popularity, next_index


def _parse_payouts(
    soup: BeautifulSoup,
    race_id: str,
    source_url: str,
    imported_at: str,
) -> pd.DataFrame:
    section = _payout_section_tokens(soup)

    rows: list[dict[str, object]] = []
    current_bet_type = ""
    index = 0
    while index < len(section):
        line = _normalize_token(section[index])
        if line in BET_TYPE_MAP:
            current_bet_type = BET_TYPE_MAP[line]
            index += 1
            continue
        normalized_selection = _normalize_token(line)
        if current_bet_type and _looks_like_selection(normalized_selection, current_bet_type):
            payout, popularity, next_index = _parse_payout_and_popularity(section, index + 1)
            if payout is not None:
                rows.append(
                    {
                        "race_id": race_id,
                        "bet_type": current_bet_type,
                        "selection": normalized_selection,
                        "payout_per_100": payout,
                        "popularity": popularity if popularity is not None else pd.NA,
                        "source_url": source_url,
                        "imported_at": imported_at,
                    }
                )
                index = max(index + 1, next_index)
                continue
        index += 1

    if not rows:
        raise HistoricalImportError("払戻組合せを解析できませんでした")
    return pd.DataFrame(rows, columns=HISTORICAL_SCHEMAS["historical_payouts.csv"])


def is_completed_jra_result_page(page_html: str) -> bool:
    text = _clean_text(BeautifulSoup(page_html, "html.parser").get_text(" ", strip=True))
    return "レース結果" in text and "着順" in text and "払戻金" in text


def parse_jra_result_html(page_html: str, source_url: str) -> ParsedHistoricalRace:
    """Parse one completed JRA race result page into normalized DataFrames."""
    soup = BeautifulSoup(page_html, "html.parser")
    metadata = _parse_metadata(soup, source_url)
    imported_at = datetime.now(timezone.utc).isoformat()
    metadata["imported_at"] = imported_at
    race = pd.DataFrame([metadata], columns=HISTORICAL_SCHEMAS["historical_races.csv"])
    runners = _parse_runners(
        _find_result_table(page_html),
        str(metadata["race_id"]),
        source_url,
        imported_at,
    )
    payouts = _parse_payouts(
        soup,
        str(metadata["race_id"]),
        source_url,
        imported_at,
    )
    return ParsedHistoricalRace(race=race, runners=runners, payouts=payouts)


class JRAHistoricalClient:
    """Small polite HTTP client for JRA result pages."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        request_interval: float = 2.0,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.request_interval = max(0.0, request_interval)
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "keiba-analysis/0.1 historical-import (personal research; contact via repository)",
        )
        self._last_request_at = 0.0

    def fetch_html(self, url: str) -> str:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        response = self.session.get(url, timeout=self.timeout)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return response.text


def discover_jra_result_urls(
    seed_urls: Sequence[str],
    *,
    race_count: int,
    fetch_html: Callable[[str], str],
    max_pages: int | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Crawl JRA result/navigation links and return completed result pages.

    The crawler is bounded and same-domain only. It records fetch/parse failures instead
    of terminating the entire import.
    """
    if race_count <= 0:
        raise ValueError("race_count must be positive")
    page_limit = max_pages or max(300, race_count * 8)
    queue: deque[str] = deque()
    for seed in seed_urls:
        candidate = _canonicalize_url(seed)
        if candidate:
            queue.append(candidate)
    if not queue:
        raise ValueError("JRAの有効なseed URLがありません")

    seen: set[str] = set()
    result_urls: list[str] = []
    errors: list[dict[str, str]] = []

    while queue and len(seen) < page_limit and len(result_urls) < race_count:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            page_html = fetch_html(url)
        except Exception as exc:  # network errors must be logged and skipped
            errors.append(
                {
                    "source_url": url,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
            continue

        if is_completed_jra_result_page(page_html):
            result_urls.append(url)

        for candidate in extract_jra_navigation_urls(page_html, url):
            if candidate not in seen:
                queue.append(candidate)

    return result_urls[:race_count], errors


def _read_or_empty(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path, dtype={"race_id": "string", "selection": "string"})


def _upsert_csv(path: Path, new_rows: pd.DataFrame, key_columns: list[str]) -> int:
    columns = HISTORICAL_SCHEMAS[path.name]
    existing = _read_or_empty(path, columns)
    if new_rows.empty:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")
        return 0
    combined = pd.concat([existing, new_rows[columns]], ignore_index=True)
    before = len(existing)
    combined = combined.drop_duplicates(subset=key_columns, keep="last")
    combined = combined[columns]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    combined.to_csv(temp, index=False, encoding="utf-8-sig")
    temp.replace(path)
    return max(0, len(combined) - before)


def initialize_historical_store(output_dir: str | Path) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    for filename, columns in HISTORICAL_SCHEMAS.items():
        path = root / filename
        if not path.exists():
            pd.DataFrame(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")
    return root


def import_recent_jra_races(
    *,
    race_count: int = 100,
    output_dir: str | Path,
    seed_urls: Sequence[str] | None = None,
    resume: bool = True,
    request_interval: float = 2.0,
    timeout: float = 20.0,
    max_pages: int | None = None,
    fetch_html: Callable[[str], str] | None = None,
) -> pd.DataFrame:
    """Import recent completed JRA results into dedicated historical CSV files.

    This stores post-race facts only. It does not fabricate pre-race scores, purchase-time
    odds, model probabilities, or bets. Existing race IDs are skipped when ``resume`` is true.
    """
    root = initialize_historical_store(output_dir)
    seeds = list(seed_urls or [DEFAULT_JRA_RESULT_INDEX_URL])
    client = None
    if fetch_html is None:
        client = JRAHistoricalClient(timeout=timeout, request_interval=request_interval)
        fetch_html = client.fetch_html

    existing_races = _read_or_empty(
        root / "historical_races.csv",
        HISTORICAL_SCHEMAS["historical_races.csv"],
    )
    existing_ids = set(existing_races["race_id"].dropna().astype(str)) if resume else set()

    urls, discovery_errors = discover_jra_result_urls(
        seeds,
        race_count=race_count + len(existing_ids),
        fetch_html=fetch_html,
        max_pages=max_pages,
    )

    race_frames: list[pd.DataFrame] = []
    runner_frames: list[pd.DataFrame] = []
    payout_frames: list[pd.DataFrame] = []
    errors = discovery_errors.copy()
    skipped_existing = 0

    for url in urls:
        if len(race_frames) >= race_count:
            break
        try:
            parsed = parse_jra_result_html(fetch_html(url), url)
            race_id = str(parsed.race.iloc[0]["race_id"])
            if resume and race_id in existing_ids:
                skipped_existing += 1
                continue
            race_frames.append(parsed.race)
            runner_frames.append(parsed.runners)
            payout_frames.append(parsed.payouts)
            existing_ids.add(race_id)
        except Exception as exc:
            errors.append(
                {
                    "source_url": url,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )

    races = pd.concat(race_frames, ignore_index=True) if race_frames else pd.DataFrame(
        columns=HISTORICAL_SCHEMAS["historical_races.csv"]
    )
    runners = pd.concat(runner_frames, ignore_index=True) if runner_frames else pd.DataFrame(
        columns=HISTORICAL_SCHEMAS["historical_runners.csv"]
    )
    payouts = pd.concat(payout_frames, ignore_index=True) if payout_frames else pd.DataFrame(
        columns=HISTORICAL_SCHEMAS["historical_payouts.csv"]
    )

    added_races = _upsert_csv(root / "historical_races.csv", races, ["race_id"])
    added_runners = _upsert_csv(
        root / "historical_runners.csv", runners, ["race_id", "horse_no"]
    )
    added_payouts = _upsert_csv(
        root / "historical_payouts.csv", payouts, ["race_id", "bet_type", "selection"]
    )

    if errors:
        occurred_at = datetime.now(timezone.utc).isoformat()
        error_rows = pd.DataFrame(
            [
                {
                    **error,
                    "occurred_at": occurred_at,
                }
                for error in errors
            ],
            columns=HISTORICAL_SCHEMAS["historical_import_errors.csv"],
        )
        _upsert_csv(
            root / "historical_import_errors.csv",
            error_rows,
            ["source_url", "error_type", "error_message"],
        )

    summary = {
        "requested_races": race_count,
        "discovered_result_urls": len(urls),
        "new_races": added_races,
        "new_runner_rows": added_runners,
        "new_payout_rows": added_payouts,
        "skipped_existing": skipped_existing,
        "errors": len(errors),
        "output_dir": str(root),
    }
    return pd.DataFrame([summary])
