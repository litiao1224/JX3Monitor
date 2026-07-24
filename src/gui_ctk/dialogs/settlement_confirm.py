# -*- coding: utf-8 -*-
"""Settlement confirm dialog for JX3 Click Monitor.

Shows the settlement report with editable fields and purchase details.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import messagebox

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

import jx3_click_monitor as core
from src.config import INCOME_MEMORY_PATH

from src.gui_ctk.dialogs.shared import C, F, position_dialog
from src.gui_ctk.widgets import CTkTable

logger = logging.getLogger("jx3_monitor.dialogs.settlement")


def _format_gold(value: object) -> str:
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0
    if amount.is_integer():
        return f"{int(amount)}金"
    return f"{amount:.2f}金"


class SettlementConfirmDialog(ctk.CTkToplevel):
    """Settlement confirmation dialog with editable fields and purchase table."""

    def __init__(self, parent: ctk.CTk, app: App, session_dir: Path | None, report: dict | None) -> None:
        super().__init__(parent)
        self.app = app
        self.session_dir = session_dir
        self.report = dict(report or {})
        self.title("结算确认")
        self.configure(fg_color=C["background"])
        position_dialog(self, parent, 960, 660, 840, 560)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_and_reset)

        self.instance_var = ctk.StringVar(value=str(self.report.get("instance_name") or "未识别副本"))
        self.role_var = ctk.StringVar(value=str(self.report.get("role") or self.report.get("identity", {}).get("name") or self.report.get("identity_name") or ""))
        self.member_display_var = ctk.StringVar(value=str(self.report.get("member_count") or "-"))
        self.total_display_var = ctk.StringVar(value=_format_gold(self.report.get("total_auction_gold")))
        self.base_income_gold = self.default_income_gold()
        self.base_expense_gold = self.default_expense_gold()
        self.income_display_var = ctk.StringVar(value=_format_gold(self.base_income_gold))
        self.expense_display_var = ctk.StringVar(value=_format_gold(self.base_expense_gold))
        self.net_display_var = ctk.StringVar(value="")
        self.black_role_var = ctk.StringVar(value=str(self.report.get("black_role") or ""))
        self.add_income_amount_var = ctk.StringVar(value="")
        self.add_income_reason_var = ctk.StringVar(value="")
        self.add_expense_amount_var = ctk.StringVar(value="")
        self.add_expense_reason_var = ctk.StringVar(value="")
        self.added_income_items: list[dict[str, object]] = []
        self.added_expense_items: list[dict[str, object]] = []

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        ctk.CTkLabel(self, text="结算确认", font=F["title"], text_color=C["text_primary"]).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(self, text="确认或修改分析结果后再入账；取消不会丢失当前结算报告。", font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=18, pady=(0, 12))

        # Summary card
        summary = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        summary.pack(fill="x", padx=18, pady=(0, 12))
        top_metrics = ctk.CTkFrame(summary, fg_color=C["card"], corner_radius=0)
        top_metrics.pack(fill="x", padx=14, pady=(12, 8))
        for label, var in [("总额", self.total_display_var), ("分配人数", self.member_display_var), ("支出", self.expense_display_var), ("收入", self.income_display_var), ("净收入", self.net_display_var)]:
            metric = ctk.CTkFrame(top_metrics, fg_color=C["entry_bg"], corner_radius=8, border_width=1, border_color=C["border"])
            metric.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(metric, text=label, font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=10, pady=(7, 0))
            ctk.CTkLabel(metric, textvariable=var, font=F["card_title"], text_color=C["text_primary"]).pack(anchor="w", padx=10, pady=(0, 7))

        # Edit row — 2-Row spacious layout with proper entry widths and colored buttons
        edit_row_1 = ctk.CTkFrame(summary, fg_color=C["card"], corner_radius=0)
        edit_row_1.pack(fill="x", padx=14, pady=(4, 6))
        for label, var, width in [("副本名称", self.instance_var, 220), ("入账角色", self.role_var, 150), ("黑本角色", self.black_role_var, 120)]:
            group = ctk.CTkFrame(edit_row_1, fg_color=C["card"], corner_radius=0)
            group.pack(side="left", padx=(0, 16))
            ctk.CTkLabel(group, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            ctk.CTkEntry(group, textvariable=var, width=width, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack()

        edit_row_2 = ctk.CTkFrame(summary, fg_color=C["card"], corner_radius=0)
        edit_row_2.pack(fill="x", padx=14, pady=(0, 12))
        for label, amount_var, reason_var, command, button_text, btn_bg, btn_hover in [
            ("添加收入", self.add_income_amount_var, self.add_income_reason_var, self.add_income_item, "增加收入", C["primary"], C["primary_hover"]),
            ("添加支出", self.add_expense_amount_var, self.add_expense_reason_var, self.add_expense_item, "增加支出", "#c0392b", "#e74c3c")
        ]:
            group = ctk.CTkFrame(edit_row_2, fg_color=C["card"], corner_radius=0)
            group.pack(side="left", fill="x", expand=True, padx=(0, 12 if button_text == "增加收入" else 0))
            ctk.CTkLabel(group, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            inputs = ctk.CTkFrame(group, fg_color=C["card"], corner_radius=0)
            inputs.pack(fill="x")
            ctk.CTkEntry(inputs, textvariable=amount_var, width=85, placeholder_text="金额", fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(side="left", padx=(0, 4))
            ctk.CTkEntry(inputs, textvariable=reason_var, placeholder_text="原因", fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(inputs, text=button_text, command=command, font=F["button"], fg_color=btn_bg, text_color="#ffffff", hover_color=btn_hover, width=80).pack(side="left", padx=(4, 0))
        self.update_net_income()

        # Actions (Pack side="bottom" first to guarantee bottom visibility without manual resizing)
        actions = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        actions.pack(side="bottom", fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(actions, text="确认入账", command=self.confirm_income, font=F["button_large"], fg_color=C["primary"], text_color=C["text_on_primary"], hover_color=C["primary_hover"], width=130).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="仅保存报告", command=self.save_only, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=110).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="取消", command=self.close_and_reset, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=90).pack(side="right")

        # Detail card
        detail = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        detail.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        ctk.CTkLabel(detail, text="成交明细", font=F["card_title"], text_color=C["text_primary"]).pack(anchor="w", padx=14, pady=(12, 6))
        self.purchase_tree = CTkTable(detail, columns=[
            {"name": "item", "text": "物品", "width": 260, "anchor": "w"},
            {"name": "buyer", "text": "买家", "width": 180, "anchor": "w"},
            {"name": "amount", "text": "金额", "width": 110, "anchor": "e"},
            {"name": "source", "text": "来源", "width": 220, "anchor": "w"},
        ], row_height=28, select_mode="browse")
        self.purchase_tree.set_theme_colors(bg_header=C["table_header"], fg_header=C["table_header_text"], bg_row_even=C["card"], bg_row_odd=C["table_alt"], bg_selected=C["table_selected"], fg_selected=C["table_selected_text"], fg_normal=C["text_primary"])
        self.purchase_tree.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.load_purchase_rows()

    # ── Methods ──────────────────────────────────────────────────

    def load_purchase_rows(self) -> None:
        for idx, purchase in enumerate(self.report.get("purchases") or []):
            self.purchase_tree.insert(values=(
                purchase.get("item") or "",
                purchase.get("buyer") or purchase.get("target") or "",
                _format_gold(purchase.get("amount_gold")),
                purchase.get("reconciliation_source_label") or purchase.get("reconciliation_source") or purchase.get("label") or "",
            ), iid=str(idx))

    def _parse_gold_var(self, var: ctk.StringVar) -> float:
        try:
            return float((var.get() or "0").replace("金", "").strip() or 0)
        except Exception:
            return 0.0

    def _add_adjustment_item(self, amount_var: ctk.StringVar, reason_var: ctk.StringVar, bucket: list[dict[str, object]], label: str) -> None:
        amount = self._parse_gold_var(amount_var)
        if amount <= 0:
            messagebox.showinfo("提示", f"请填写{label}金额")
            return
        reason = reason_var.get().strip() or "未填写原因"
        bucket.append({"amount": amount, "reason": reason})
        amount_var.set("")
        reason_var.set("")
        self.update_net_income()

    def add_income_item(self) -> None:
        self._add_adjustment_item(self.add_income_amount_var, self.add_income_reason_var, self.added_income_items, "增加收入")

    def add_expense_item(self) -> None:
        self._add_adjustment_item(self.add_expense_amount_var, self.add_expense_reason_var, self.added_expense_items, "增加支出")

    def default_income_gold(self) -> float:
        value = self.report.get("self_actual_income_gold")
        if value is None:
            value = self.report.get("self_estimated_wage_gold")
        if value is None:
            value = self.report.get("average_wage_gold")
        try:
            return round(float(value or 0), 2)
        except Exception:
            return 0.0

    def default_expense_gold(self) -> float:
        total = 0.0
        identity = self.report.get("identity") or {}
        role_name = str(identity.get("role_name") or "").strip()
        server = str(identity.get("server") or "").strip()
        candidates = {role_name, f"{role_name}·{server}" if role_name and server else "", f"{role_name}@{server}" if role_name and server else ""}
        candidates.discard("")
        for purchase in self.report.get("purchases") or []:
            buyer = str(purchase.get("buyer") or "").strip()
            target = str(purchase.get("target") or "").strip()
            if candidates and (buyer in candidates or target in candidates):
                try:
                    total += float(purchase.get("amount_gold") or 0)
                except Exception:
                    pass
        return round(total, 2)

    def update_net_income(self) -> None:
        income = self.base_income_gold + sum(float(item.get("amount") or 0) for item in self.added_income_items)
        expense = self.base_expense_gold + sum(float(item.get("amount") or 0) for item in self.added_expense_items)
        self.income_display_var.set(_format_gold(income))
        self.expense_display_var.set(_format_gold(expense))
        net = round(income - expense, 2)
        if float(net).is_integer():
            self.net_display_var.set(_format_gold(int(net)))
        else:
            self.net_display_var.set(_format_gold(net))

    def edited_report(self) -> dict:
        report = dict(self.report)
        report["instance_name"] = self.instance_var.get().strip() or report.get("instance_name") or "未识别副本"
        role_name = self.role_var.get().strip()
        if role_name:
            report["role"] = role_name
            if isinstance(report.get("identity"), dict):
                report["identity"]["name"] = role_name
        pending_income = self._parse_gold_var(self.add_income_amount_var)
        pending_expense = self._parse_gold_var(self.add_expense_amount_var)
        income_items = list(self.added_income_items)
        expense_items = list(self.added_expense_items)
        if pending_income > 0:
            income_items.append({"amount": pending_income, "reason": self.add_income_reason_var.get().strip() or "未填写原因"})
        if pending_expense > 0:
            expense_items.append({"amount": pending_expense, "reason": self.add_expense_reason_var.get().strip() or "未填写原因"})
        add_income = sum(float(item.get("amount") or 0) for item in income_items)
        add_expense = sum(float(item.get("amount") or 0) for item in expense_items)
        report["added_income_gold"] = add_income
        report["added_income_items"] = income_items
        report["added_income_reason"] = "；".join(f"{_format_gold(item.get('amount'))}：{item.get('reason')}" for item in income_items)
        report["added_expense_gold"] = add_expense
        report["added_expense_items"] = expense_items
        report["added_expense_reason"] = "；".join(f"{_format_gold(item.get('amount'))}：{item.get('reason')}" for item in expense_items)
        report["manual_income_gold"] = round(self.base_income_gold + add_income, 2)
        report["manual_expense_gold"] = round(self.base_expense_gold + add_expense, 2)
        report["manual_net_gold"] = round(report["manual_income_gold"] - report["manual_expense_gold"], 2)
        report["black_role"] = self.black_role_var.get().strip()
        return report

    def _income_record(self, report: dict) -> dict:
        base = core.report_income_memory_record(report, self.session_dir or Path(""))
        role_name = self.role_var.get().strip() or report.get("role") or ""
        if role_name:
            base["role"] = role_name
        income = float(report.get("manual_income_gold") or 0)
        expense = float(report.get("manual_expense_gold") or 0)
        base["income_gold"] = income
        base["expense_gold"] = expense
        base["net_gold"] = round(income - expense, 2)
        base["black_role"] = report.get("black_role") or ""
        notes = []
        for item in report.get("added_income_items") or []:
            notes.append(f"添加收入 {_format_gold(item.get('amount'))}：{item.get('reason') or '未填写原因'}")
        added_expenses = report.get("added_expense_items") or []
        if added_expenses:
            current_expense_items = list(base.get("expense_items") or [])
            for item in added_expenses:
                current_expense_items.append({
                    "item": item.get("reason") or "手动增加支出",
                    "amount_gold": float(item.get("amount") or 0),
                    "buyer": base.get("role") or "",
                    "target": "added_expense",
                })
                notes.append(f"添加支出 {_format_gold(item.get('amount'))}：{item.get('reason') or '未填写原因'}")
            base["expense_items"] = current_expense_items
        else:
            for item in report.get("added_expense_items") or []:
                notes.append(f"添加支出 {_format_gold(item.get('amount'))}：{item.get('reason') or '未填写原因'}")
        base["note"] = "；".join(notes)
        return base

    def close_and_reset(self) -> None:
        self.app.new_report = None
        self.app.set_new_state("idle")
        self.app.stats_text.set("尚未开始")
        self.destroy()

    def save_only(self) -> None:
        self.report = self.edited_report()
        self.app.new_report = self.report
        self.app.stats_text.set(self.app.format_settlement_summary(self.report))
        self.app.status_var.set("结算报告已保留，尚未入账")
        self.close_and_reset()

    def confirm_income(self) -> None:
        if not self.session_dir:
            messagebox.showinfo("提示", "没有可入账的记录")
            return
        self.report = self.edited_report()
        try:
            core.upsert_income_memory_custom(INCOME_MEMORY_PATH, self._income_record(self.report))
            
            # Write back history confirmation metadata to the session directory
            meta_path = self.session_dir / "session_meta.json"
            if not meta_path.exists():
                meta_path = self.session_dir / "session.json"
            try:
                meta = core.read_json(meta_path, {})
                meta["history_confirmed"] = True
                meta["history_source"] = "新的记录" if meta.get("watch_mode") == "gui" else "手动"
                meta["history_confirmed_at"] = core.now_ts()
                meta["history_confirmed_label"] = core.ts_label()
                meta["history_confirmed_by"] = "income_confirm"
                if self.report.get("identity"):
                    meta["identity"] = self.report.get("identity")
                core.write_json(meta_path, meta)
            except Exception:
                pass

            self.app.new_report = None
            self.app.stats_text.set("尚未开始")
            self.app.status_var.set("✅ 结算数据已成功写入收支统计")
            # Force page refresh after a short delay to ensure file is written
            self.app.after(100, self._do_refresh_income)
            self.close_and_reset()
        except Exception as exc:
            messagebox.showerror("入账失败", f"无法写入收支统计：{exc}")

    def _do_refresh_income(self) -> None:
        """Refresh income and history pages on the main thread."""
        try:
            self.app.refresh_income_page()
            self.app.refresh_history_sessions()
        except Exception:
            pass
