# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Settlement snapshot parsing and reconciliation.

Parses settlement summary messages, deduplicates repeated snapshots,
and provides helpers for purchase-gap analysis.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.core.patterns import PURCHASE_GAP_STATUS_LABELS, RECONCILIATION_SOURCE_LABELS
from src.core.utils import normalize_text


def settlement_snapshot_from_match(m) -> Optional[Dict[str, Any]]:
    """Parse a regex match of the settlement summary pattern into a snapshot dict."""
    snap = {
        "total_income_gold": int(m.group("total")),
        "subsidy_gold": int(m.group("subsidy")),
        "distributable_gold": int(m.group("distributable")),
        "member_count": int(m.group("members")),
        "base_wage_gold": int(m.group("wage")),
    }
    issues = []
    if snap["member_count"] <= 0:
        issues.append("member_count<=0")
    expected_distributable = snap["total_income_gold"] - snap["subsidy_gold"]
    if expected_distributable != snap["distributable_gold"]:
        issues.append(f"distributable_mismatch:{expected_distributable}")
    if snap["member_count"] > 0:
        expected_wage_floor = snap["distributable_gold"] // snap["member_count"]
        if abs(expected_wage_floor - snap["base_wage_gold"]) > 1:
            issues.append(f"base_wage_mismatch:{expected_wage_floor}")
    snap["valid"] = not issues
    snap["issues"] = issues
    return snap if snap["valid"] else None


def settlement_snapshot_signature(snap: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        snap.get("total_income_gold"),
        snap.get("subsidy_gold"),
        snap.get("distributable_gold"),
        snap.get("member_count"),
        snap.get("base_wage_gold"),
    )


def dedupe_settlement_snapshots(
    snapshots: List[Dict[str, Any]], window_seconds: float = 3600.0
) -> List[Dict[str, Any]]:
    """Within a 1h window, repeated identical settlement summaries keep only the last one."""
    ordered = sorted(snapshots, key=lambda x: (x.get("time") or 0, x.get("label") or ""))
    kept: List[Dict[str, Any]] = []
    for snap in ordered:
        sig = settlement_snapshot_signature(snap)
        t = float(snap.get("time") or 0)
        replaced = False
        for i in range(len(kept) - 1, -1, -1):
            prev = kept[i]
            if settlement_snapshot_signature(prev) != sig:
                continue
            pt = float(prev.get("time") or 0)
            if abs(t - pt) <= window_seconds:
                kept[i] = snap
                replaced = True
            break
        if not replaced:
            kept.append(snap)
    return kept


# ── Reconciliation helpers ─────────────────────────────────────


def reconciliation_source_label(value: str | None) -> str:
    return RECONCILIATION_SOURCE_LABELS.get(str(value or ""), str(value or ""))


def purchase_gap_status(diff: Any) -> str:
    try:
        value = float(diff or 0)
    except (TypeError, ValueError):
        return "unknown"
    if abs(value) <= 1:
        return "match"
    return "settlement_gt_sales" if value > 0 else "sales_gt_settlement"


def purchase_gap_status_label(status: str | None) -> str:
    return PURCHASE_GAP_STATUS_LABELS.get(str(status or ""), str(status or ""))


def purchase_gap_note(diff: Any) -> str:
    status = purchase_gap_status(diff)
    if status == "match":
        return "明确成交合计与工资条总收入基本一致。"
    if status == "settlement_gt_sales":
        return "工资条总收入高于明确成交合计；可能存在手动补录、未刷成交行的收入或插件统计来源差异。"
    if status == "sales_gt_settlement":
        return "明确成交合计高于工资条总收入；可能存在重记、改价、跨场记录或工资条不是本场最终版本。"
    return "未能判断成交合计与工资条差额。"
