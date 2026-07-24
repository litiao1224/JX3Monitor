# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Report generation.

Produces text and JSON reports from settlement data.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.utils import copper_to_gold, ensure_dir, ts_label


def format_gold(copper: int) -> str:
    """Format copper amount as JX3 gold display (金/银/铜)."""
    g = copper // 10000
    s = (copper % 10000) // 100
    c = copper % 100
    parts = []
    if g:
        parts.append(f"{g}金")
    if s:
        parts.append(f"{s}银")
    if c:
        parts.append(f"{c}铜")
    return "".join(parts) if parts else "0金"


def build_text_report(
    settlement: Dict[str, Any],
    session_id: str = "",
    dungeon: str = "",
    my_role: str = "",
    generated_at: Optional[str] = None,
) -> str:
    """Build a human-readable text report."""
    lines = []
    lines.append("=" * 50)
    lines.append("         JX3 金团结算报告")
    lines.append("=" * 50)
    if session_id:
        lines.append(f"场次: {session_id}")
    if dungeon:
        lines.append(f"副本: {dungeon}")
    lines.append(f"生成时间: {generated_at or ts_label()}")
    if my_role:
        lines.append(f"我的角色: {my_role}")
    lines.append("")

    summary = settlement.get("summary", {})
    lines.append("--- 汇总 ---")
    lines.append(f"总金币: {format_gold(summary.get('total_gold_copper', 0))} "
                 f"({copper_to_gold(summary.get('total_gold_copper', 0)):.4f} 金)")
    lines.append(f"总物品: {summary.get('total_items', 0)}")
    lines.append(f"总事件: {summary.get('total_events', 0)}")

    members = summary.get("team_members", [])
    if members:
        lines.append(f"团队成员 ({len(members)}): {', '.join(members)}")

    type_counts = summary.get("event_type_counts", {})
    if type_counts:
        lines.append("事件类型:")
        for etype, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {etype}: {cnt}")
    lines.append("")

    roles = settlement.get("roles", [])
    if roles:
        lines.append("--- 角色明细 ---")
        for role in roles:
            marker = " ★" if role.get("is_me") else ""
            lines.append(f"\n[{role['name']}]{marker}")
            lines.append(f"  金币: {format_gold(role.get('total_gold_copper', 0))}")
            lines.append(f"  物品: {role.get('total_item_count', 0)}")
            if role.get("trade_confirm_count"):
                lines.append(f"  交易确认: {role['trade_confirm_count']}")
            items = role.get("items_received", [])
            if items:
                lines.append(f"  获得物品:")
                for item in items:
                    lines.append(f"    - {item}")
    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def build_json_report(
    settlement: Dict[str, Any],
    session_id: str = "",
    dungeon: str = "",
    my_role: str = "",
) -> Dict[str, Any]:
    """Build a JSON-serializable report dict."""
    return {
        "version": 1,
        "session_id": session_id,
        "dungeon": dungeon,
        "my_role": my_role,
        "generated_at": ts_label(),
        "settlement": settlement,
    }


def save_text_report(
    text: str,
    report_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    """Write text report to file."""
    ensure_dir(report_dir)
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path = report_dir / filename
    path.write_text(text, encoding="utf-8")
    return path


def save_json_report(
    data: Dict[str, Any],
    report_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    """Write JSON report to file."""
    import json
    ensure_dir(report_dir)
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = report_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def export_reports(
    settlement: Dict[str, Any],
    report_dir: Path,
    session_id: str = "",
    dungeon: str = "",
    my_role: str = "",
) -> List[Path]:
    """Generate and save both text and JSON reports."""
    paths = []
    text = build_text_report(settlement, session_id, dungeon, my_role)
    paths.append(save_text_report(text, report_dir))

    json_data = build_json_report(settlement, session_id, dungeon, my_role)
    paths.append(save_json_report(json_data, report_dir))
    return paths
