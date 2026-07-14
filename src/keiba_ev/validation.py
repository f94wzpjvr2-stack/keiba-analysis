from __future__ import annotations

import pandas as pd


def validate_ticket_plan(plan: pd.DataFrame, budget_ceiling: int, unit: int = 100) -> dict[str, object]:
    errors: list[str] = []
    if budget_ceiling < 0 or budget_ceiling % unit != 0:
        errors.append("予算上限は100円単位で指定してください")
    if plan.empty:
        return {"ok": not errors, "errors": errors, "spent": 0, "unspent": budget_ceiling}
    if (plan["stake"] <= 0).any():
        errors.append("購入額0円以下の買い目があります")
    if (plan["stake"] % unit != 0).any():
        errors.append("100円単位でない買い目があります")
    duplicate_columns = ["selection"]
    if "bet_type" in plan.columns:
        duplicate_columns = ["bet_type", "selection"]
    if plan.duplicated(subset=duplicate_columns).any():
        errors.append("重複買い目があります")
    spent = int(plan["stake"].sum())
    if spent > budget_ceiling:
        errors.append(f"予算超過です: {spent} > {budget_ceiling}")
    return {
        "ok": not errors,
        "errors": errors,
        "spent": spent,
        "unspent": budget_ceiling - spent,
    }
