from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "gui_ctk" / "dialogs" / "settlement_confirm.py"


def source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_settlement_confirm_dialog_exists_with_actions() -> None:
    source = source_text()

    assert "class SettlementConfirmDialog" in source
    assert "确认入账" in source
    assert "仅保存报告" in source
    assert "取消" in source
    assert "成交明细" in source


def test_settlement_confirm_dialog_uses_adjustment_fields() -> None:
    source = source_text()
    start = source.index("class SettlementConfirmDialog")
    end = len(source)
    block = source[start:end]

    assert "添加收入" in block
    assert "添加支出" in block
    assert "增加收入" in block
    assert "增加支出" in block
    assert "self.added_income_items" in block
    assert "self.added_expense_items" in block
    assert "def add_income_item" in block
    assert "def add_expense_item" in block
    assert "净收入" in block
    assert "黑本角色" in block
    assert "self.add_income_amount_var" in block
    assert "self.add_income_reason_var" in block
    assert "self.add_expense_amount_var" in block
    assert "self.add_expense_reason_var" in block
    assert "self.net_display_var" in block
    assert "self.black_role_var" in block
    assert "core.upsert_income_memory_custom" in block
    assert "core.upsert_income_memory(INCOME_MEMORY_PATH" not in block


def test_settlement_dialog_closes_back_to_idle() -> None:
    source = source_text()
    start = source.index("class SettlementConfirmDialog")
    end = len(source)
    block = source[start:end]

    assert "def close_and_reset" in block
    assert "self.app.new_report = None" in block
    assert "self.app.set_new_state(\"idle\")" in block
    assert "command=self.close_and_reset" in block


def test_ready_button_is_view_bill() -> None:
    source = (ROOT / "src/gui_ctk/pages/__init__.py").read_text("utf-8")

    assert "查看副本账单" in source
    assert "生成结算（确认后入账）" not in source


def test_settlement_totals_are_read_only_labels() -> None:
    source = source_text()
    start = source.index("class SettlementConfirmDialog")
    end = len(source)
    block = source[start:end]

    assert "self.member_display_var" in block
    assert "self.total_display_var" in block
    assert "self.income_display_var" in block
    assert "self.expense_display_var" in block
    assert "self.net_display_var" in block
    assert "self.member_var" not in block
    assert "self.total_var" not in block
    assert "self.wage_var" not in block
    assert "工资/人" not in block


def test_settlement_ready_opens_dialog() -> None:
    source = (ROOT / "jx3_click_monitor_gui_ctk.py").read_text("utf-8")

    assert "def open_settlement_confirm_dialog" in source
    assert "self.open_settlement_confirm_dialog()" in source
    assert "SettlementConfirmDialog(self, self, self.session_dir, self.new_report)" in source


def test_make_report_reopens_dialog_instead_of_direct_upsert() -> None:
    source = (ROOT / "jx3_click_monitor_gui_ctk.py").read_text("utf-8")
    start = source.index("    def make_report")
    end = source.index("    def refresh_history_sessions", start)
    block = source[start:end]

    assert "self.open_settlement_confirm_dialog()" in block
    assert "core.upsert_income_memory" not in block
