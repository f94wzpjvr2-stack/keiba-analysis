from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from .result_collector import RaceResult, ResultNotPublishedError, fetch_official_result

BET_TYPE_ALIASES = {
    "win": "win",
    "単勝": "win",
    "place": "place",
    "複勝": "place",
    "wide": "wide",
    "ワイド": "wide",
    "quinella": "quinella",
    "馬連": "quinella",
    "exacta": "exacta",
    "馬単": "exacta",
    "trio": "trio",
    "三連複": "trio",
    "3連複": "trio",
    "trifecta": "trifecta",
    "三連単": "trifecta",
    "3連単": "trifecta",
    "bracket_quinella": "bracket_quinella",
    "枠連": "bracket_quinella",
}

SETTLEMENT_COLUMNS = [
    "race_id",
    "bet_type",
    "selection",
    "stake",
    "hit",
    "payout_per_100",
    "payout_amount",
    "profit",
    "race_total_stake",
    "race_total_payout",
    "race_profit",
    "race_return_rate",
    "settled_at",
    "result_source_url",
    "algorithm_version",
]

ERROR_COLUMNS = ["race_id", "stage", "source_url", "error_type", "error_message", "occurred_at"]
RUN_COLUMNS = [
    "run_started_at",
    "run_finished_at",
    "unsettled_races",
    "settled_races",
    "skipped_races",
    "errors",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bet_type(bet_type: object) -> str:
    text = str(bet_type).strip()
    if text not in BET_TYPE_ALIASES:
        raise ValueError(f"unsupported bet_type: {bet_type}")
    return BET_TYPE_ALIASES[text]


def normalize_selection(selection: object, bet_type: object) -> str:
    normalized_type = canonical_bet_type(bet_type)
    text = (
        str(selection)
        .strip()
        .replace("　", " ")
        .replace("－", "-")
        .replace("ー", "-")
        .replace("–", "-")
    )
    numbers = [int(value) for value in re.findall(r"\d+", text)]
    expected = {
        "win": 1,
        "place": 1,
        "wide": 2,
        "quinella": 2,
        "exacta": 2,
        "bracket_quinella": 2,
        "trio": 3,
        "trifecta": 3,
    }[normalized_type]
    if len(numbers) != expected:
        raise ValueError(f"selection {selection!r} does not match {normalized_type}")
    if normalized_type in {"wide", "quinella", "bracket_quinella", "trio"}:
        numbers = sorted(numbers)
    return "-".join(str(value) for value in numbers)


def normalize_bets(bets: pd.DataFrame) -> pd.DataFrame:
    required = {"race_id", "bet_type", "selection", "stake", "algorithm_version"}
    missing = sorted(required - set(bets.columns))
    if missing:
        raise ValueError(f"Missing bet columns: {missing}")
    out = bets.copy()
    if "odds_at_prediction" not in out.columns and "odds_at_purchase" in out.columns:
        out["odds_at_prediction"] = out["odds_at_purchase"]
    if "estimated_probability" not in out.columns and "model_prob" in out.columns:
        out["estimated_probability"] = out["model_prob"]
    if "expected_value" not in out.columns and "ev_at_purchase" in out.columns:
        out["expected_value"] = out["ev_at_purchase"]
    if "predicted_at" not in out.columns:
        out["predicted_at"] = ""
    out["stake"] = pd.to_numeric(out["stake"], errors="raise").astype(int)
    invalid = (out["stake"] <= 0) | (out["stake"] % 100 != 0)
    if invalid.any():
        bad = out.loc[invalid, ["race_id", "bet_type", "selection", "stake"]].to_dict("records")
        raise ValueError(f"stake must be a positive 100-yen unit: {bad}")
    out["bet_type"] = out["bet_type"].map(canonical_bet_type)
    out["selection"] = [
        normalize_selection(selection, bet_type)
        for selection, bet_type in zip(out["selection"], out["bet_type"])
    ]
    out = out.drop_duplicates(["race_id", "bet_type", "selection"], keep="last")
    return out


def _payout_lookup(result: RaceResult) -> dict[tuple[str, str], int]:
    lookup: dict[tuple[str, str], int] = {}
    for row in result.payouts.to_dict("records"):
        bet_type = canonical_bet_type(row["bet_type"])
        selection = normalize_selection(row["selection"], bet_type)
        lookup[(bet_type, selection)] = int(row["payout_per_100"])
    return lookup


def settle_race_bets(bets: pd.DataFrame, result: RaceResult) -> pd.DataFrame:
    normalized = normalize_bets(bets)
    race_bets = normalized[normalized["race_id"].astype(str) == result.race_id].copy()
    if race_bets.empty:
        return pd.DataFrame(columns=SETTLEMENT_COLUMNS)
    lookup = _payout_lookup(result)
    rows: list[dict[str, object]] = []
    settled_at = now_utc()
    for bet in race_bets.to_dict("records"):
        key = (bet["bet_type"], bet["selection"])
        payout_per_100 = lookup.get(key, 0)
        payout_amount = int(bet["stake"] / 100 * payout_per_100)
        profit = payout_amount - int(bet["stake"])
        rows.append(
            {
                "race_id": result.race_id,
                "bet_type": bet["bet_type"],
                "selection": bet["selection"],
                "stake": int(bet["stake"]),
                "hit": payout_per_100 > 0,
                "payout_per_100": payout_per_100,
                "payout_amount": payout_amount,
                "profit": profit,
                "settled_at": settled_at,
                "result_source_url": result.result_source_url,
                "algorithm_version": bet["algorithm_version"],
            }
        )
    out = pd.DataFrame(rows)
    total_stake = int(out["stake"].sum())
    total_payout = int(out["payout_amount"].sum())
    out["race_total_stake"] = total_stake
    out["race_total_payout"] = total_payout
    out["race_profit"] = total_payout - total_stake
    out["race_return_rate"] = total_payout / total_stake * 100 if total_stake else 0.0
    return out[SETTLEMENT_COLUMNS]


def read_csv_or_empty(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns or [])
    return pd.read_csv(path)


def write_csv(path: Path, rows: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False, encoding="utf-8-sig")


def append_csv(path: Path, rows: pd.DataFrame) -> None:
    if rows.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(
        path,
        mode="a",
        header=not path.exists() or path.stat().st_size == 0,
        index=False,
        encoding="utf-8-sig",
    )


def log_error(root: Path, race_id: str, stage: str, source_url: str, exc: Exception) -> None:
    append_csv(
        root / "automation" / f"{stage}_errors.csv",
        pd.DataFrame(
            [
                {
                    "race_id": race_id,
                    "stage": stage,
                    "source_url": source_url,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "occurred_at": now_utc(),
                }
            ],
            columns=ERROR_COLUMNS,
        ),
    )


def unsettled_race_ids(bets: pd.DataFrame, results: pd.DataFrame) -> list[str]:
    if bets.empty:
        return []
    settled = set()
    if not results.empty and "race_id" in results.columns:
        settled = set(results["race_id"].dropna().astype(str))
    race_ids = list(dict.fromkeys(bets["race_id"].dropna().astype(str)))
    return [race_id for race_id in race_ids if race_id not in settled]


def _race_source_url(races: pd.DataFrame, race_id: str) -> str:
    if races.empty:
        return ""
    row = races[races["race_id"].astype(str) == race_id]
    if row.empty:
        return ""
    for column in ("result_source_url", "source_url", "result_url", "jra_result_url"):
        if column in row.columns:
            value = row.iloc[0].get(column, "")
            if pd.notna(value) and str(value).strip():
                return str(value).strip()
    return ""


def _merge_results(existing: pd.DataFrame, additions: pd.DataFrame, root: Path) -> pd.DataFrame:
    if additions.empty:
        return existing
    if existing.empty:
        return additions.copy()
    if not set(SETTLEMENT_COLUMNS).issubset(existing.columns):
        settled_ids = set(existing.get("race_id", pd.Series(dtype="object")).dropna().astype(str))
        additions = additions[~additions["race_id"].astype(str).isin(settled_ids)]
        if additions.empty:
            return existing
        return pd.concat([existing, additions], ignore_index=True, sort=False)
    merged = existing.copy()
    for race_id in additions["race_id"].dropna().astype(str).unique():
        old = merged[merged["race_id"].astype(str) == race_id]
        new = additions[additions["race_id"].astype(str) == race_id]
        if old.empty:
            continue
        comparable = ["race_id", "bet_type", "selection", "stake", "hit", "payout_amount"]
        old_cmp = old[comparable].sort_values(comparable).reset_index(drop=True)
        new_cmp = new[comparable].sort_values(comparable).reset_index(drop=True)
        if old_cmp.equals(new_cmp):
            additions = additions[additions["race_id"].astype(str) != race_id]
        else:
            log_error(
                root,
                race_id,
                "settlement",
                str(new["result_source_url"].iloc[0]),
                ValueError("existing settlement differs from official result"),
            )
            additions = additions[additions["race_id"].astype(str) != race_id]
    if additions.empty:
        return merged
    return pd.concat([merged, additions], ignore_index=True)


def settle_unsettled_races(
    data_dir: str | Path,
    *,
    fetch_html: Callable[[str], str] | None = None,
    request_interval: float = 2.0,
) -> dict[str, object]:
    root = Path(data_dir)
    run_started_at = now_utc()
    bets = normalize_bets(read_csv_or_empty(root / "bets.csv"))
    races = read_csv_or_empty(root / "races.csv")
    results = read_csv_or_empty(root / "results.csv", SETTLEMENT_COLUMNS)
    unsettled = unsettled_race_ids(bets, results)
    additions: list[pd.DataFrame] = []
    skipped = 0
    errors = 0
    cache: dict[str, RaceResult] = {}
    for race_id in unsettled:
        source_url = _race_source_url(races, race_id)
        if not source_url:
            errors += 1
            log_error(root, race_id, "result_import", "", ValueError("result source URL is missing"))
            continue
        try:
            if source_url not in cache:
                cache[source_url] = fetch_official_result(
                    source_url,
                    fetch_html=fetch_html,
                    request_interval=request_interval,
                )
            result = cache[source_url]
            additions.append(settle_race_bets(bets, result))
        except ResultNotPublishedError:
            skipped += 1
        except Exception as exc:
            errors += 1
            log_error(root, race_id, "result_import", source_url, exc)
    settled_rows = pd.concat(additions, ignore_index=True) if additions else pd.DataFrame(
        columns=SETTLEMENT_COLUMNS
    )
    merged = _merge_results(results, settled_rows, root)
    write_csv(root / "results.csv", merged)
    run = {
        "run_started_at": run_started_at,
        "run_finished_at": now_utc(),
        "unsettled_races": len(unsettled),
        "settled_races": settled_rows["race_id"].nunique() if not settled_rows.empty else 0,
        "skipped_races": skipped,
        "errors": errors,
    }
    append_csv(root / "automation" / "automation_runs.csv", pd.DataFrame([run], columns=RUN_COLUMNS))
    return {"summary": run, "settled": settled_rows, "results": merged}
