from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from .historical import JRAHistoricalClient, is_completed_jra_result_page, parse_jra_result_html


class ResultNotPublishedError(RuntimeError):
    """Raised when an official result page is reachable but not published yet."""


@dataclass(frozen=True)
class RaceResult:
    race_id: str
    race: pd.Series
    runners: pd.DataFrame
    payouts: pd.DataFrame
    result_source_url: str
    result_retrieved_at: str

    @property
    def top3(self) -> tuple[int | None, int | None, int | None]:
        finish = self.runners.copy()
        finish["finish_numeric"] = pd.to_numeric(
            finish["finish_position"].astype(str).str.extract(r"(\d+)")[0],
            errors="coerce",
        )
        ordered = finish.dropna(subset=["finish_numeric"]).sort_values(
            ["finish_numeric", "horse_no"]
        )
        top = ordered["horse_no"].astype(int).head(3).tolist()
        return tuple((top + [None, None, None])[:3])


def fetch_official_result(
    source_url: str,
    *,
    fetch_html: Callable[[str], str] | None = None,
    request_interval: float = 2.0,
    timeout: float = 20.0,
) -> RaceResult:
    """Fetch and parse one official JRA result page.

    The function does not infer results from non-result pages. If the page is not
    published yet, callers can keep the race unsettled.
    """
    if not source_url:
        raise ValueError("result source URL is required")
    if fetch_html is None:
        fetch_html = JRAHistoricalClient(
            request_interval=request_interval,
            timeout=timeout,
        ).fetch_html
    html = fetch_html(source_url)
    if not is_completed_jra_result_page(html):
        raise ResultNotPublishedError("result page is not published yet")
    parsed = parse_jra_result_html(html, source_url)
    race = parsed.race.iloc[0]
    return RaceResult(
        race_id=str(race["race_id"]),
        race=race,
        runners=parsed.runners.copy(),
        payouts=parsed.payouts.copy(),
        result_source_url=source_url,
        result_retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
