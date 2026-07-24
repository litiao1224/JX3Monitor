from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "jx3_click_monitor_gui_ctk.py"


class SettlementSummaryHarness:
    from jx3_click_monitor_gui_ctk import App

    format_settlement_summary = App.format_settlement_summary


def test_format_settlement_summary_uses_real_report_fields() -> None:
    report = {
        "purchase_count": 8,
        "total_auction_gold": 456350,
        "member_count": 23,
        "average_wage_gold": 17863,
        "instance_name": "25人英雄·阆风悬城",
    }

    text = SettlementSummaryHarness().format_settlement_summary(report)

    assert "8 件成交" in text
    assert "456350金" in text
    assert "23 人工资" in text
    assert "17863金" in text
    assert "25人英雄·阆风悬城" in text


def test_confirm_dialog_uses_income_upsert_api() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("class SettlementConfirmDialog")
    end = source.index("class App", start)
    block = source[start:end]

    assert "core.upsert_income_memory_custom" in block
    assert "core.save_income_memory(INCOME_MEMORY_PATH, report" not in block
