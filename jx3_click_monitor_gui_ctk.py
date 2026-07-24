#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clean modern CustomTkinter UI entrypoint."""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
from datetime import datetime
from pathlib import Path
from tkinter import Menu, filedialog, messagebox

import customtkinter as ctk

import jx3_click_monitor as core
# ── 核心模块与应用层服务 ──────────────────────────────────────────
from src.config import (
    APP_NAME, CONFIG_PATH, DEFAULT_JX3_PATH, DEFAULT_OUT_DIR, INCOME_MEMORY_PATH,
)
from src.monitor.worker import MonitorWorker
from src.core.instance_detect import dungeon_display_name
from src.core.money import fmt_money
from src.gui_ctk.widgets import CTkTable, CTkContextMenu
from src.gui_ctk.themes import COLORS as C, FONTS as F
from src.gui_ctk.themes import (
    CORNER_RADIUS, CORNER_RADIUS_SM, CORNER_RADIUS_LG,
    SIDEBAR_WIDTH, BUTTON_HEIGHT, BUTTON_HEIGHT_LG, INPUT_HEIGHT,
)
from src.gui_ctk.animations import animate_page_transition, hover_glow
from src.gui_ctk.error_handler import handle_ui_error
from src.gui_ctk.state import AppState, StateMachine
from src.gui_ctk.icon_cache import get_icon_cache
from src.config import AppConfig
from src.gui_ctk.pages import (
    build_new_page,
    build_history_page,
    build_income_page,
    build_growth_page,
    build_settings_page,
)

DEFAULT_GROWTH_DUNGEON_COUNT = 3

# drain_queue poll intervals
_POLL_FAST_MS = 50
_POLL_IDLE_MS = 300
_MAX_PER_DRAIN = 30

logger = logging.getLogger("jx3_monitor.app")



def repair_display_text(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    known = {        "娴嬭瘯鏈?": "测试服",
        "灏忛功楣夋祴璇曞彿": "小鹦鹉测试号",
        "娴嬭瘯璇﹀彿": "测试账号",
        "娴嬭瘯鍓湰路灏忛功楣瘯璇?": "测试副本·小鹦鹉试账",
    }
    if text in known:
        return known[text]
    mojibake_markers = set("娴嬭瘯灏忛功楣璇曞彿路鍓湰鑐佬澘")
    if not any(char in mojibake_markers for char in text):
        return text
    best = text
    attempts = []
    for enc, dec in (("gbk", "utf-8"), ("cp936", "utf-8"), ("utf-8", "gbk"), ("utf-8", "cp936")):
        try:
            attempts.append(text.encode(enc, errors="strict").decode(dec, errors="strict"))
        except Exception:
            pass
    for candidate in attempts:
        if _display_text_score(candidate) > _display_text_score(best):
            best = candidate
    if best != "?":
        best = best.replace("?", "")
    return best or text

def _display_text_score(text: str) -> int:
    score = 0
    for char in text:
        if "一" <= char <= "鿿":
            score += 3
        elif char in "路·、：，。！？（）【】《》":
            score += 1
        elif char in "?�€鑐灏娴嬭瘯鍓璇楣曞彿":
            score -= 1
    return score


def format_gold_text(value: object) -> str:
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0
    if amount.is_integer():
        return f"{int(amount)}金"
    return f"{amount:.2f}金"


class SettlementConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, app: "App", session_dir: Path | None, report: dict | None) -> None:
        super().__init__(parent)
        self.app = app
        self.session_dir = session_dir
        self.report = dict(report or {})
        self.title("结算确认")
        self.geometry("900x620")
        self.minsize(780, 520)
        self.configure(fg_color=C["background"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_and_reset)

        self.instance_var = ctk.StringVar(value=str(self.report.get("instance_name") or "未识别剧本"))
        self.member_display_var = ctk.StringVar(value=str(self.report.get("member_count") or "-"))
        self.total_display_var = ctk.StringVar(value=format_gold_text(self.report.get("total_auction_gold")))
        self.base_income_gold = self.default_income_gold()
        self.base_expense_gold = self.default_expense_gold()
        self.income_display_var = ctk.StringVar(value=format_gold_text(self.base_income_gold))
        self.expense_display_var = ctk.StringVar(value=format_gold_text(self.base_expense_gold))
        self.net_display_var = ctk.StringVar(value="")
        self.black_role_var = ctk.StringVar(value=str(self.report.get("black_role") or ""))
        self.add_income_amount_var = ctk.StringVar(value="")
        self.add_income_reason_var = ctk.StringVar(value="")
        self.add_expense_amount_var = ctk.StringVar(value="")
        self.add_expense_reason_var = ctk.StringVar(value="")
        self.added_income_items: list[dict[str, object]] = []
        self.added_expense_items: list[dict[str, object]] = []

        ctk.CTkLabel(self, text="结算确认", font=F["title"], text_color=C["text_primary"]).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(self, text="确认或修改分析结果后入账；取消不会丢失当前结算报告。", font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=18, pady=(0, 12))

        summary = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        summary.pack(fill="x", padx=18, pady=(0, 12))
        top_metrics = ctk.CTkFrame(summary, fg_color=C["card"], corner_radius=0)
        top_metrics.pack(fill="x", padx=14, pady=(12, 8))
        for label, var in [("总额", self.total_display_var), ("分配人数", self.member_display_var), ("支出", self.expense_display_var), ("收入", self.income_display_var), ("净收入", self.net_display_var)]:
            metric = ctk.CTkFrame(top_metrics, fg_color=C["entry_bg"], corner_radius=8, border_width=1, border_color=C["border"])
            metric.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(metric, text=label, font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=10, pady=(7, 0))
            ctk.CTkLabel(metric, textvariable=var, font=F["card_title"], text_color=C["text_primary"]).pack(anchor="w", padx=10, pady=(0, 7))

        edit_row = ctk.CTkFrame(summary, fg_color=C["card"], corner_radius=0)
        edit_row.pack(fill="x", padx=14, pady=(4, 12))
        for label, var, width in [("剧本名称", self.instance_var, 180), ("黑本角色", self.black_role_var, 72)]:
            group = ctk.CTkFrame(edit_row, fg_color=C["card"], corner_radius=0)
            group.pack(side="left", fill="x", expand=(label == "剧本名称"), padx=(0, 8))
            ctk.CTkLabel(group, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            ctk.CTkEntry(group, textvariable=var, width=width, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(fill="x" if label == "剧本名称" else None)
        for label, amount_var, reason_var, command, button_text in [("添加收入", self.add_income_amount_var, self.add_income_reason_var, self.add_income_item, "增加收入"), ("添加支出", self.add_expense_amount_var, self.add_expense_reason_var, self.add_expense_item, "增加支出")]:
            group = ctk.CTkFrame(edit_row, fg_color=C["card"], corner_radius=0)
            group.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(group, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            inputs = ctk.CTkFrame(group, fg_color=C["card"], corner_radius=0)
            inputs.pack(fill="x")
            ctk.CTkEntry(inputs, textvariable=amount_var, width=76, placeholder_text="金额", fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(side="left", padx=(0, 4))
            ctk.CTkEntry(inputs, textvariable=reason_var, placeholder_text="原因", fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(inputs, text=button_text, command=command, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=74).pack(side="left", padx=(4, 0))
        self.update_net_income()

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

        actions = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        actions.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(actions, text="确认入账", command=self.confirm_income, font=F["button_large"], fg_color=C["primary"], text_color=C["text_on_primary"], hover_color=C["primary_hover"], width=130).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="仅保存报告", command=self.save_only, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=110).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="取消", command=self.close_and_reset, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=90).pack(side="right")

    def load_purchase_rows(self) -> None:
        for idx, purchase in enumerate(self.report.get("purchases") or []):
            self.purchase_tree.insert(values=(
                purchase.get("item") or "",
                purchase.get("buyer") or purchase.get("target") or "",
                format_gold_text(purchase.get("amount_gold")),
                purchase.get("reconciliation_source_label") or purchase.get("reconciliation_source") or purchase.get("label") or "",
            ), iid=str(idx))

    def parse_gold_var(self, var: ctk.StringVar) -> float:
        try:
            return float((var.get() or "0").replace("金", "").strip() or 0)
        except Exception:
            return 0.0

    def add_adjustment_item(self, amount_var: ctk.StringVar, reason_var: ctk.StringVar, bucket: list[dict[str, object]], label: str) -> None:
        amount = self.parse_gold_var(amount_var)
        if amount <= 0:
            messagebox.showinfo("提示", f"请填写{label}金额")
            return
        reason = reason_var.get().strip() or "未填写原因"
        bucket.append({"amount": amount, "reason": reason})
        amount_var.set("")
        reason_var.set("")
        self.update_net_income()

    def add_income_item(self) -> None:
        self.add_adjustment_item(self.add_income_amount_var, self.add_income_reason_var, self.added_income_items, "增加收入")

    def add_expense_item(self) -> None:
        self.add_adjustment_item(self.add_expense_amount_var, self.add_expense_reason_var, self.added_expense_items, "增加支出")

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
        self.income_display_var.set(format_gold_text(income))
        self.expense_display_var.set(format_gold_text(expense))
        net = round(income - expense, 2)
        if float(net).is_integer():
            self.net_display_var.set(format_gold_text(int(net)))
        else:
            self.net_display_var.set(format_gold_text(net))

    def edited_report(self) -> dict:
        report = dict(self.report)
        report["instance_name"] = self.instance_var.get().strip() or report.get("instance_name") or "未识别剧本"
        pending_income = self.parse_gold_var(self.add_income_amount_var)
        pending_expense = self.parse_gold_var(self.add_expense_amount_var)
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
        report["added_income_reason"] = "；".join(f"{format_gold_text(item.get('amount'))}：{item.get('reason')}" for item in income_items)
        report["added_expense_gold"] = add_expense
        report["added_expense_items"] = expense_items
        report["added_expense_reason"] = "；".join(f"{format_gold_text(item.get('amount'))}：{item.get('reason')}" for item in expense_items)
        report["manual_income_gold"] = round(self.base_income_gold + add_income, 2)
        report["manual_expense_gold"] = round(self.base_expense_gold + add_expense, 2)
        report["manual_net_gold"] = round(report["manual_income_gold"] - report["manual_expense_gold"], 2)
        report["black_role"] = self.black_role_var.get().strip()
        return report

    def income_record(self, report: dict) -> dict:
        base = core.report_income_memory_record(report, self.session_dir or Path(""))
        income = float(report.get("manual_income_gold") or 0)
        expense = float(report.get("manual_expense_gold") or 0)
        base["income_gold"] = income
        base["expense_gold"] = expense
        base["net_gold"] = round(income - expense, 2)
        base["black_role"] = report.get("black_role") or ""
        notes = []
        for item in report.get("added_income_items") or []:
            notes.append(f"添加收入 {format_gold_text(item.get('amount'))}：{item.get('reason') or '未填写原因'}")

        # Merge manual added expense items into base['expense_items'] so they appear in analysis
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
                notes.append(f"添加支出 {format_gold_text(item.get('amount'))}：{item.get('reason') or '未填写原因'}")
            base["expense_items"] = current_expense_items
        else:
            for item in report.get("added_expense_items") or []:
                notes.append(f"添加支出 {format_gold_text(item.get('amount'))}：{item.get('reason') or '未填写原因'}")

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
            core.upsert_income_memory_custom(INCOME_MEMORY_PATH, self.income_record(self.report))
            self.app.new_report = None
            self.app.stats_text.set("尚未开始")
            self.app.status_var.set(f"已入账 · v{core.APP_VERSION}")
            self.app.refresh_income_page()
            messagebox.showinfo("入账成功", "结算数据已写入收支统计")
            self.close_and_reset()
        except Exception as exc:
            messagebox.showerror("入账失败", f"无法写入收支统计：{exc}")


class IncomeEditDialog(ctk.CTkToplevel):
    """Edit a single income record. Styled like SettlementConfirmDialog."""

    def __init__(self, parent: ctk.CTk, app: "App", record: dict, record_idx: int) -> None:
        super().__init__(parent)
        self.app = app
        self.record = dict(record)
        self.record_idx = record_idx

        self.title("编辑收支记录")
        self.geometry("740x550")
        self.minsize(660, 500)
        self.configure(fg_color=C["background"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close)

        income_gold = float(record.get("income_gold") or record.get("income") or 0)
        expense_gold = float(record.get("expense_gold") or record.get("expense") or 0)
        net_gold = float(record.get("net_gold") or record.get("net") or 0)
        if net_gold == 0 and (income_gold or expense_gold):
            net_gold = income_gold - expense_gold

        self.instance_var = ctk.StringVar(value=str(record.get("instance") or record.get("instance_name") or ""))
        self.role_var = ctk.StringVar(value=str(record.get("role") or ""))
        self.server_var = ctk.StringVar(value=str(record.get("server") or ""))
        self.recorded_at_var = ctk.StringVar(value=str(record.get("recorded_at") or ""))
        self.base_income_gold = income_gold
        self.base_expense_gold = expense_gold
        self.added_income_items: list[dict[str, object]] = []
        self.added_expense_items: list[dict[str, object]] = []
        self.income_var = ctk.StringVar(value=format_gold_text(income_gold))
        self.expense_var = ctk.StringVar(value=format_gold_text(expense_gold))
        self.net_var = ctk.StringVar(value=format_gold_text(net_gold))
        self.note_var = ctk.StringVar(value=str(record.get("note") or ""))
        self.black_role_var = ctk.StringVar(value=str(record.get("black_role") or ""))
        self.add_income_amount_var = ctk.StringVar(value="")
        self.add_income_reason_var = ctk.StringVar(value="")
        self.add_expense_amount_var = ctk.StringVar(value="")
        self.add_expense_reason_var = ctk.StringVar(value="")

        # ── Title ──
        ctk.CTkLabel(self, text="编辑收支记录", font=F["title"], text_color=C["text_primary"]).pack(anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(self, text="修改后点击保存，取消则不保留更改。", font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=18, pady=(0, 12))

        # ── Metrics row ──
        metrics = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        metrics.pack(fill="x", padx=18, pady=(0, 12))
        top_row = ctk.CTkFrame(metrics, fg_color=C["card"], corner_radius=0)
        top_row.pack(fill="x", padx=14, pady=(12, 8))
        for label, var in [("收入", self.income_var), ("支出", self.expense_var), ("净收入", self.net_var)]:
            box = ctk.CTkFrame(top_row, fg_color=C["entry_bg"], corner_radius=8, border_width=1, border_color=C["border"])
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(box, text=label, font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=10, pady=(7, 0))
            ctk.CTkLabel(box, textvariable=var, font=F["card_title"], text_color=C["text_primary"]).pack(anchor="w", padx=10, pady=(0, 7))

        # ── Fields card ──
        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        card.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        # Row: 时间 · 区服 · 剧本名称 · 角色 · 黑本角色（一行）
        fields = ctk.CTkFrame(card, fg_color=C["card"], corner_radius=0)
        fields.pack(fill="x", padx=14, pady=(12, 6))
        for label, var, width in [
            ("时间", self.recorded_at_var, 130),
            ("区服", self.server_var, 80),
            ("剧本名称", self.instance_var, 130),
            ("角色", self.role_var, 90),
            ("黑本角色", self.black_role_var, 80),
        ]:
            col = ctk.CTkFrame(fields, fg_color=C["card"], corner_radius=0)
            col.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(col, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            ctk.CTkEntry(col, textvariable=var, width=width, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(anchor="w")

        # Row: 添加收入 · 添加支出
        row3 = ctk.CTkFrame(card, fg_color=C["card"], corner_radius=0)
        row3.pack(fill="x", padx=14, pady=(0, 6))
        for label, amount_var, reason_var, cmd, btn_text in [
            ("添加收入", self.add_income_amount_var, self.add_income_reason_var, self.add_income_item, "确认"),
            ("添加支出", self.add_expense_amount_var, self.add_expense_reason_var, self.add_expense_item, "确认"),
        ]:
            group = ctk.CTkFrame(row3, fg_color=C["card"], corner_radius=0)
            group.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(group, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            inputs = ctk.CTkFrame(group, fg_color=C["card"], corner_radius=0)
            inputs.pack(fill="x")
            ctk.CTkLabel(inputs, text="金额", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(0, 2))
            ctk.CTkEntry(inputs, textvariable=amount_var, width=80, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(inputs, text="原因", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(0, 2))
            ctk.CTkEntry(inputs, textvariable=reason_var, placeholder_text="", fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(inputs, text=btn_text, command=cmd, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=74).pack(side="left", padx=(4, 0))

        # Row: 备注
        row4 = ctk.CTkFrame(card, fg_color=C["card"], corner_radius=0)
        row4.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(row4, text="备注", font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
        ctk.CTkEntry(row4, textvariable=self.note_var, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(fill="x")

        # ── Actions ──
        actions = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        actions.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(actions, text="保存", command=self.save, font=F["button_large"], fg_color=C["primary"], text_color=C["text_on_primary"], hover_color=C["primary_hover"], width=130).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="取消", command=self.close, font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"], hover_color=C["toolbar_hover"], width=90).pack(side="right")

    def _parse_gold(self, var: ctk.StringVar) -> float:
        try:
            return float((var.get() or "0").replace("金", "").strip() or 0)
        except Exception:
            return 0.0

    def _update_display(self) -> None:
        total_income = self.base_income_gold + sum(float(item.get("amount") or 0) for item in self.added_income_items)
        total_expense = self.base_expense_gold + sum(float(item.get("amount") or 0) for item in self.added_expense_items)
        self.income_var.set(format_gold_text(total_income))
        self.expense_var.set(format_gold_text(total_expense))
        net = round(total_income - total_expense, 2)
        self.net_var.set(format_gold_text(net))

    def _add_item(self, amount_var: ctk.StringVar, reason_var: ctk.StringVar, bucket: list[dict[str, object]], label: str) -> None:
        amount = self._parse_gold(amount_var)
        if amount <= 0:
            messagebox.showinfo("提示", f"请填写{label}金额")
            return
        reason = reason_var.get().strip() or "未填写原因"
        bucket.append({"amount": amount, "reason": reason})
        amount_var.set("")
        reason_var.set("")
        self._update_display()

    def add_income_item(self) -> None:
        self._add_item(self.add_income_amount_var, self.add_income_reason_var, self.added_income_items, "增加收入")

    def add_expense_item(self) -> None:
        self._add_item(self.add_expense_amount_var, self.add_expense_reason_var, self.added_expense_items, "增加支出")

    def save(self) -> None:
        try:
            total_income = self.base_income_gold + sum(float(item.get("amount") or 0) for item in self.added_income_items)
            total_expense = self.base_expense_gold + sum(float(item.get("amount") or 0) for item in self.added_expense_items)
            net_gold = round(total_income - total_expense, 2)
            notes = []
            if self.added_income_items:
                notes.append("添加收入：" + "；".join(f"{format_gold_text(item.get('amount'))}：{item.get('reason')}" for item in self.added_income_items))
            if self.added_expense_items:
                notes.append("添加支出：" + "；".join(f"{format_gold_text(item.get('amount'))}：{item.get('reason')}" for item in self.added_expense_items))
            note_text = self.note_var.get().strip()
            if notes:
                note_text = ("；" + "；".join(notes)) if note_text else "；".join(notes)
            # Append manual added expense items to expense_items in the saved patch
            new_expense_items = list(self.record.get("expense_items") or [])
            if self.added_expense_items:
                for item in self.added_expense_items:
                    new_expense_items.append({
                        "item": item.get("reason") or "手动增加支出",
                        "amount_gold": float(item.get("amount") or 0),
                        "buyer": self.role_var.get().strip() or self.record.get("role") or "",
                        "target": "added_expense",
                    })
            patch = {
                "recorded_at": self.recorded_at_var.get().strip(),
                "server": self.server_var.get().strip(),
                "role": self.role_var.get().strip(),
                "instance": self.instance_var.get().strip(),
                "income_gold": total_income,
                "expense_gold": total_expense,
                "net_gold": net_gold,
                "note": note_text,
                "black_role": self.black_role_var.get().strip(),
                "expense_items": new_expense_items,
            }
            # Perform IO operation in a background thread to prevent UI lag
            def _async_save():
                try:
                    seq = self.record.get("seq")
                    if seq is not None:
                        core.update_income_memory_record(INCOME_MEMORY_PATH, int(seq), patch)
                    else:
                        if 0 <= self.record_idx < len(self.app.income_records):
                            self.app.income_records[self.record_idx].update(patch)
                            from src.core.income_memory import save_income_memory
                            save_income_memory(INCOME_MEMORY_PATH, {"records": self.app.income_records})
                    self.app.queue.put(("refresh_income", None))
                except Exception as e:
                    self.app.queue.put(("error", {"title": "保存失败", "message": str(e)}))

            threading.Thread(target=_async_save, daemon=True).start()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))


from src.gui_ctk.dialogs import SettlementConfirmDialog, IncomeEditDialog


class App(ctk.CTk):
    def __init__(self, *args, **kwargs) -> None:
        self._iconbitmap_method_called = True  # Prevent CustomTkinter from setting its default blue "C" icon
        super().__init__(*args, **kwargs)
        # Explicitly set AppUserModelID to ensure Windows taskbar groups and shows the custom icon correctly
        try:
            import ctypes
            myappid = 'litia.jx3monitor.app.v14' # unique string to bust Windows taskbar icon cache
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # Set our custom icon immediately before the window is mapped/realized
        try:
            import sys
            import os
            from pathlib import Path
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_path = Path(base_dir) / "src" / "gui" / "icon.ico"
            if not icon_path.exists():
                icon_path = Path(base_dir) / "icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception as e:
            print("Error setting icon early:", repr(e))

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("")
        self.geometry("1180x800")
        self.minsize(980, 640)
        self.configure(fg_color=C["sidebar"])
        self.config_data = self.load_config()
        self.jx3_var = ctk.StringVar(value=str(self.config_data.get("jx3_path") or DEFAULT_JX3_PATH))
        self.out_var = ctk.StringVar(value=str(self.config_data.get("out_dir") or DEFAULT_OUT_DIR))
        self.status_var = ctk.StringVar(value=f"就绪 · v{core.APP_VERSION}")
        self.page_title_var = ctk.StringVar(value="新的记录")
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: MonitorWorker | None = None
        self.session_dir: Path | None = None
        self.new_report: dict | None = None
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.menu_buttons: dict[str, ctk.CTkButton] = {}
        self.growth_records: list[dict] = []
        self.growth_dungeon_map: dict[str, str] = {}
        self.selected_growth_dungeons: set[str] = set(self.config_data.get("selected_growth_dungeons", []) or [])
        self.hidden_growth_ownerkeys: set[str] = set(self.config_data.get("hidden_growth_ownerkeys", []) or [])
        self.selected_growth_ownerkeys: set[str] = set(self.config_data.get("selected_growth_ownerkeys", []) or [])
        self.growth_role_selection_initialized = "selected_growth_ownerkeys" in self.config_data
        self.growth_source_var = ctk.StringVar(value="从茗伊角色统计数据库只读加载")
        self.member_var = ctk.StringVar(value=str(self.config_data.get("member_count", "") or ""))
        self.personal_subsidy_var = ctk.StringVar(value=str(self.config_data.get("personal_subsidy", "") or ""))
        self.startup_mode_var = ctk.StringVar(value=self.config_data.get("startup_mode", "manual") or "manual")
        self.season_start_var = ctk.StringVar(value=self.config_data.get("season_start", ""))
        self.season_end_var = ctk.StringVar(value=self.config_data.get("season_end", ""))
        self.offline_start_time_var = ctk.StringVar(value=str(self.config_data.get("offline_start_time", "") or ""))
        self.offline_end_time_var = ctk.StringVar(value=str(self.config_data.get("offline_end_time", "") or ""))
        
        # Cloud Sync variables
        self.cloud_sync_enabled_var = ctk.BooleanVar(value=bool(self.config_data.get("cloud_sync_enabled", False)))
        self.cloud_provider_var = ctk.StringVar(value=str(self.config_data.get("cloud_provider", "cos")))
        self.cloud_endpoint_var = ctk.StringVar(value=str(self.config_data.get("cloud_endpoint", "")))
        self.cloud_region_var = ctk.StringVar(value=str(self.config_data.get("cloud_region", "")))
        self.cloud_secret_id_var = ctk.StringVar(value=str(self.config_data.get("cloud_secret_id", "")))
        self.cloud_secret_key_var = ctk.StringVar(value=str(self.config_data.get("cloud_secret_key", "")))
        self.cloud_bucket_var = ctk.StringVar(value=str(self.config_data.get("cloud_bucket", "")))
        self.cloud_url_path_var = ctk.StringVar(value=str(self.config_data.get("cloud_url_path", "")))

        self.income_filter: dict[str, str] = {"date_from": "", "date_to": "", "role": "", "server": "", "note": ""}
        self.income_columns_all = ("recorded_at", "server", "role", "black_role", "instance", "income", "expense", "net", "note", "session_time")
        self.income_headings = {"recorded_at": "时间", "server": "区服", "role": "角色", "black_role": "黑本角色", "instance": "剧本名称", "income": "收入", "expense": "支出", "net": "净收入", "note": "备注", "session_time": "会话"}
        saved_visible = set(self.config_data.get("income_visible_columns", []) or ["recorded_at", "server", "role", "instance", "income", "expense", "net", "black_role", "note"])
        self.income_column_vars = {key: ctk.BooleanVar(value=key in saved_visible) for key in self.income_columns_all}
        self.income_records: list[dict] = []

        # Pagination variables
        self.income_page_index = 0
        self.income_page_size = 50
        self.history_page_index = 0
        self.history_page_size = 30
        self.history_sessions_all: list[Path] = []

        # Threading queue wakeup event
        self.queue_event = threading.Event()

        self.build_layout()
        self.show_page("new")
        self.bind("<Map>", self.hide_titlebar_icon_event)
        self.set_native_title_bar_color(C["sidebar"])
        self.after(150, self.drain_queue)

    def hide_titlebar_icon_event(self, event) -> None:
        if event.widget == self:
            self.hide_titlebar_icon()

    def hide_titlebar_icon(self) -> None:
        try:
            import ctypes
            tk_hwnd = self.winfo_id()
            GA_ROOT = 2
            hwnd = ctypes.windll.user32.GetAncestor(tk_hwnd, GA_ROOT)
            if hwnd == 0:
                hwnd = tk_hwnd

            # 1. Create a 16x16 transparent icon handle dynamically to block fallback to the class icon
            and_mask = b"\xff" * 32  # All bits 1 means transparent
            xor_mask = b"\x00" * 32  # All bits 0
            hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
            hicon_trans = ctypes.windll.user32.CreateIcon(
                hinst,
                16, 16,  # 16x16
                1, 1,    # 1 plane, 1 bpp
                and_mask,
                xor_mask
            )

            # 2. Method A: Set dialog frame style (removes titlebar icon space) - 64-bit safe
            GWL_EXSTYLE = -20
            WS_EX_DLGMODALFRAME = 0x00000001
            try:
                SetWindowLongPtrW = ctypes.windll.user32.SetWindowLongPtrW
                SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
                SetWindowLongPtrW.restype = ctypes.c_ssize_t
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if not (ex_style & WS_EX_DLGMODALFRAME):
                    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_DLGMODALFRAME)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 2 | 1 | 4 | 0x0020)
            except AttributeError:
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if not (ex_style & WS_EX_DLGMODALFRAME):
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_DLGMODALFRAME)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 2 | 1 | 4 | 0x0020)

            # 3. Method B: Bind the transparent small icon to the titlebar (ICON_SMALL)
            if hicon_trans:
                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_trans)
        except Exception as e:
            logger.error("Error in hide_titlebar_icon: %s", repr(e))

    def set_native_title_bar_color(self, hex_color: str) -> None:
        """Use DWM API to set Windows title bar background color to match sidebar, and remove window icon."""
        try:
            import ctypes

            def apply_window_styles_delayed():
                try:
                    # Get parent window handle and parent DWM top-level wrapper handle dynamically
                    tk_hwnd = self.winfo_id()
                    GA_ROOT = 2
                    hwnd = ctypes.windll.user32.GetAncestor(tk_hwnd, GA_ROOT)
                    if hwnd == 0:
                        hwnd = tk_hwnd

                    # ── 1. Color title bar and text using DWM ──
                    if hex_color.startswith("#") and len(hex_color) == 7:
                        r = int(hex_color[1:3], 16)
                        g = int(hex_color[3:5], 16)
                        b = int(hex_color[5:7], 16)
                        color_ref = (b << 16) | (g << 8) | r

                        # Attribute DWMWA_CAPTION_COLOR = 35
                        ctypes.windll.dwmapi.DwmSetWindowAttribute(
                            hwnd, 35, ctypes.byref(ctypes.c_int(color_ref)), ctypes.sizeof(ctypes.c_int)
                        )
                        # Attribute DWMWA_TEXT_COLOR = 36 to make title text look cleaner
                        ctypes.windll.dwmapi.DwmSetWindowAttribute(
                            hwnd, 36, ctypes.byref(ctypes.c_int(0x00CCCCCC)), ctypes.sizeof(ctypes.c_int)
                        )

                    # ── 2. Strip title bar icon space and clear icon ──
                    self.hide_titlebar_icon()

                except Exception as e:
                    logger.error("Error in apply_window_styles_delayed: %s", repr(e))

            self.after(200, apply_window_styles_delayed)
        except Exception as e:
            logger.error("Error in set_native_title_bar_color: %s", repr(e))

    def load_config(self) -> dict:
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
        return {}

    def save_config(self) -> None:
        self.config_data.update({"jx3_path": self.jx3_var.get(), "out_dir": self.out_var.get(),
            "member_count": self.member_var.get(), "personal_subsidy": self.personal_subsidy_var.get(),
            "startup_mode": self.startup_mode_var.get(), "season_start": self.season_start_var.get(),
            "season_end": self.season_end_var.get(), "offline_start_time": self.offline_start_time_var.get(),
            "offline_end_time": self.offline_end_time_var.get(),
            "selected_growth_dungeons": sorted(self.selected_growth_dungeons),
            "hidden_growth_ownerkeys": sorted(self.hidden_growth_ownerkeys),
            "selected_growth_ownerkeys": sorted(self.selected_growth_ownerkeys),
            "cloud_sync_enabled": self.cloud_sync_enabled_var.get(),
            "cloud_provider": self.cloud_provider_var.get(),
            "cloud_endpoint": self.cloud_endpoint_var.get(),
            "cloud_region": self.cloud_region_var.get(),
            "cloud_secret_id": self.cloud_secret_id_var.get(),
            "cloud_secret_key": self.cloud_secret_key_var.get(),
            "cloud_bucket": self.cloud_bucket_var.get(),
            "cloud_url_path": self.cloud_url_path_var.get(),
            "income_visible_columns": [key for key, var in self.income_column_vars.items() if var.get()]})

        def _async_save_cfg():
            try:
                CONFIG_PATH.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        threading.Thread(target=_async_save_cfg, daemon=True).start()

    def trigger_background_cloud_sync(self, upload_html: bool = False, manual: bool = False) -> None:
        """Export data and upload to cloud in a background thread."""
        if not self.cloud_sync_enabled_var.get():
            if manual:
                messagebox.showinfo("提示", "未开启云同步功能，请先在设置中启用并配置参数。")
            return

        # Show visual loading status in status bar if not manual
        if not manual:
            self.status_var.set("正在同步数据到云端...")

        def _run_sync():
            try:
                import src.core.cloud_exporter as cloud_exporter
                url = cloud_exporter.export_and_upload(self, upload_html=upload_html)
                if manual:
                    self.queue.put(("message_info", ("同步成功", f"云端数据及网页已成功同步！\n\n你可以通过以下网址访问云端看板：\n{url}")))
                else:
                    self.queue.put(("log", "云端数据同步成功"))
            except Exception as e:
                logger.error("Cloud sync failed: %s", repr(e))
                if manual:
                    self.queue.put(("message_error", ("同步失败", f"同步数据发生错误：\n{e}")))
                else:
                    self.queue.put(("log", "云端同步失败，请检查设置"))

        threading.Thread(target=_run_sync, daemon=True).start()

    def build_layout(self) -> None:
        """Build premium dark layout: sidebar + content + status bar."""
        root = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0)
        root.pack(fill="both", expand=True)

        # ── Sidebar ──
        sidebar = ctk.CTkFrame(root, fg_color=C["sidebar"], width=SIDEBAR_WIDTH, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)



        # ── Menu items (compact, no group headers) ──
        menu_items = [
            ("new", "🎯  新的记录"),
            ("history", "📋  历史记录"),
            ("income", "💰  收支统计"),
            ("growth", "👤  角色信息"),
            ("settings", "⚙️  设置"),
        ]
        for key, label in menu_items:
            btn_frame = ctk.CTkFrame(sidebar, fg_color="transparent", corner_radius=CORNER_RADIUS_SM)
            btn_frame.pack(fill="x", padx=12, pady=1)
            # No side indicator for a clean look
            btn = ctk.CTkButton(
                btn_frame, text=label,
                command=lambda k=key: self.show_page(k),
                font=F["sidebar"], fg_color="transparent",
                text_color=C["text_muted"], hover_color=C["sidebar_hover"],
                anchor="w", height=28, corner_radius=CORNER_RADIUS_SM,
            )
            btn.pack(fill="x", expand=True, padx=(2, 0))
            self.menu_buttons[key] = btn

        # Sidebar footer — version
        sidebar_footer = ctk.CTkFrame(sidebar, fg_color=C["sidebar"], corner_radius=0)
        sidebar_footer.pack(side="bottom", fill="x")
        ctk.CTkFrame(sidebar_footer, fg_color=C["border"], height=1).pack(fill="x", padx=20)
        ctk.CTkLabel(
            sidebar_footer, text=f"  v{core.APP_VERSION}",
            font=F["tiny"], text_color=C["text_ghost"],
        ).pack(anchor="w", padx=20, pady=(10, 14))

        # ── Main content area ──
        # To make the main content look integrated with the sidebar (unified background),
        # we set the main container bg to the same color as the sidebar.
        main = ctk.CTkFrame(root, fg_color=C["sidebar"], corner_radius=0)
        main.pack(side="left", fill="both", expand=True)

        # We place a rounded main wrapper that has C["background"] and rounded corners (CORNER_RADIUS_LG)
        # to achieve the beautiful rounded content layout.
        content_wrapper = ctk.CTkFrame(main, fg_color=C["background"], corner_radius=CORNER_RADIUS_LG)
        content_wrapper.pack(fill="both", expand=True, padx=(0, 16), pady=16)

        # Page title (within the rounded wrapper)
        self.title_bar = ctk.CTkFrame(content_wrapper, fg_color=C["sidebar"], corner_radius=0)
        self.title_bar.pack(fill="x", padx=28, pady=(22, 6))
        self.title_label = ctk.CTkLabel(
            self.title_bar, textvariable=self.page_title_var,
            font=F["title"], text_color=C["text_primary"],
        )
        self.title_label.pack(side="left")

        # Page host (within the rounded wrapper)
        self.page_host = ctk.CTkFrame(content_wrapper, fg_color=C["background"], corner_radius=0)
        self.page_host.pack(fill="both", expand=True, padx=28, pady=(16, 16))
        self._current_page_key: str | None = None



        # Build all pages (extracted to page modules)
        build_new_page(self)
        build_history_page(self)
        build_income_page(self)
        build_growth_page(self)
        build_settings_page(self)

    def show_page(self, key: str) -> None:
        titles = {"new": "新的记录", "history": "历史记录", "income": "收支统计", "growth": "角色信息", "settings": "设置"}
        old_page = self.pages.get(self._current_page_key) if self._current_page_key else None
        for page in self.pages.values():
            page.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        self.page_title_var.set(titles[key])
        
        # Hide the redundant title bar card for all pages
        self.title_bar.pack_forget()
        self.page_host.pack_forget()
        self.page_host.pack(fill="both", expand=True, padx=28, pady=(22, 16))

        # Update sidebar button states
        for page_key, btn in self.menu_buttons.items():
            indicator = getattr(btn, "_indicator", None)
            if page_key == key:
                btn.configure(fg_color=C["sidebar_hover"], text_color=C["text_primary"], font=F["sidebar_active"])
                if indicator:
                    indicator.configure(fg_color=C["primary"])
            else:
                btn.configure(fg_color="transparent", text_color=C["text_muted"], font=F["sidebar"])
                if indicator:
                    indicator.configure(fg_color="transparent")

        self._current_page_key = key
        if key == "growth" and not self.growth_records:
            self.refresh_growth_page(silent=True)

    def card(self, parent: ctk.CTkFrame, title: str | None = None) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent, fg_color=C["card"],
            corner_radius=CORNER_RADIUS_LG,
            border_width=1, border_color=C["border_subtle"],
        )
        frame.pack(fill="x", pady=(0, 14))
        if title:
            ctk.CTkLabel(
                frame, text=title, font=F["card_title"],
                text_color=C["text_primary"],
            ).pack(anchor="w", padx=22, pady=(16, 8))
        return frame


    def style_table(self, table: CTkTable) -> None:
        table.set_theme_colors(
            bg_header=C["sidebar"], fg_header=C["text_primary"],
            bg_row_even=C["card"], bg_row_odd=C["card_alt"],
            bg_selected=C["table_selected"], fg_selected=C["table_selected_text"],
            fg_normal=C["text_primary"],
        )

    def history_columns(self) -> list[dict[str, object]]:
        return [
            {"name": "recorded_at", "text": "时间", "width": 160, "anchor": "w"},
            {"name": "source", "text": "来源", "width": 100, "anchor": "w"},
            {"name": "role", "text": "角色", "width": 120, "anchor": "w"},
            {"name": "instance", "text": "摘要", "width": 420, "anchor": "w"},
        ]

    def _season_date_row(self, parent: ctk.CTkFrame, label: str, var: ctk.StringVar, now_year: int) -> None:
        def make_callback(yv: ctk.StringVar, mv: ctk.StringVar, dv: ctk.StringVar):
            def cb(*_args: object) -> None:
                y = yv.get(); m = mv.get(); d = dv.get()
                if y and m and d:
                    var.set(f"{y}-{m}-{d}")
                else:
                    var.set("")
            return cb
        row = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=0)
        row.pack(fill="x", padx=22, pady=6)
        ctk.CTkLabel(
            row, text=label, width=90, anchor="w",
            font=F["body"], text_color=C["text_secondary"],
        ).pack(side="left")
        current = var.get().strip()
        parts = current.split("-") if current and "-" in current else []
        y0 = parts[0] if parts else str(now_year)
        m0 = parts[1] if len(parts) > 1 else "01"
        d0 = parts[2] if len(parts) > 2 else "01"
        year_var = ctk.StringVar(value=y0)
        month_var = ctk.StringVar(value=m0)
        day_var = ctk.StringVar(value=d0)
        years = [str(y) for y in range(now_year - 5, now_year + 2)]
        months = [f"{m:02d}" for m in range(1, 13)]
        days = [f"{d:02d}" for d in range(1, 32)]
        cb = make_callback(year_var, month_var, day_var)
        year_var.trace_add("write", cb)
        month_var.trace_add("write", cb)
        day_var.trace_add("write", cb)
        option_style = {
            "font": F["body"], "fg_color": C["entry_bg"],
            "text_color": C["text_primary"], "button_color": C["primary"],
            "button_hover_color": C["primary_hover"],
            "dropdown_fg_color": C["card"], "dropdown_text_color": C["text_primary"],
            "dropdown_hover_color": C["sidebar_hover"],
            "corner_radius": CORNER_RADIUS_SM,
        }
        ctk.CTkOptionMenu(row, variable=year_var, values=years, width=80, **option_style).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(row, text="年", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(2, 6))
        ctk.CTkOptionMenu(row, variable=month_var, values=months, width=62, **option_style).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(row, text="月", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(2, 6))
        ctk.CTkOptionMenu(row, variable=day_var, values=days, width=62, **option_style).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(row, text="日", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(2, 0))

    def export_data(self) -> None:
        path = filedialog.asksaveasfilename(title="导出软件数据", defaultextension=".zip", filetypes=[("Zip 文件", "*.zip")], initialfile=f"jx3_gold_monitor_export_{datetime.now().strftime('%Y%m%d')}.zip")
        if not path:
            return
        try:
            core.export_all_data(Path(path), CONFIG_PATH, INCOME_MEMORY_PATH)
            messagebox.showinfo("导出成功", f"数据已导出到：{path}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def import_data(self) -> None:
        path = filedialog.askopenfilename(title="导入软件数据", filetypes=[("Zip 文件", "*.zip")])
        if not path:
            return
        try:
            core.import_all_data(Path(path), CONFIG_PATH, INCOME_MEMORY_PATH)
            self.config_data = self.load_config()
            messagebox.showinfo("导入成功", "数据已恢复，请重启软件以完全生效。")
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))

    def choose_jx3(self) -> None:
        path = filedialog.askdirectory(title="选择剑三 zhcn_hd 目录", initialdir=self.jx3_var.get() or str(Path.home()))
        if path: self.jx3_var.set(path)

    def choose_out(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录", initialdir=self.out_var.get() or str(Path.home()))
        if path: self.out_var.set(path)

    def save_settings(self) -> None:
        self.save_config(); self.status_var.set("设置已保存"); messagebox.showinfo("保存成功", "设置已保存")

    def open_live_folder(self) -> None:
        path = Path(self.out_var.get() or DEFAULT_OUT_DIR); path.mkdir(parents=True, exist_ok=True); os.startfile(path)

    def start_monitor(self) -> None:
        try:
            self.status_var.set("正在启动监控……")
            self.update_idletasks()
            jx3_path = Path(self.jx3_var.get())
            out_dir = Path(self.out_var.get())
            if not jx3_path.exists():
                self.status_var.set(f"路径错误：{jx3_path}")
                messagebox.showerror("路径错误", f"请选择正确的剑三 zhcn_hd 目录：\n{jx3_path}")
                return
            if self.worker and self.worker.is_alive():
                self.status_var.set("已在监控中")
                messagebox.showinfo("提示", "已在监控中")
                return
            session_dir = core.create_session(jx3_path, out_dir, team_tag="gui", watch_mode="gui")
            self.session_dir = session_dir
            self.new_report = None
            self.worker = MonitorWorker(self, session_dir, interval=2.0, member_count=self.parse_member_count(), personal_subsidy=self.parse_personal_subsidy())
            self.worker.daemon = True
            self.worker.start()
            self.set_new_state("recording")
            self.stats_text.set(f"正在记录：{session_dir.name}")
            self.status_var.set(f"监控中 · 记录到 {session_dir.name} · v{core.APP_VERSION}")
            self.save_config()
        except Exception as exc:
            self.status_var.set(f"启动监控失败：{exc}")
            messagebox.showerror("启动监控失败", str(exc))

    def abandon_recording(self) -> None:
        if not self.worker:
            self.set_new_state("idle")
            self.status_var.set(f"已放弃 · v{core.APP_VERSION}")
            return
        from src.gui_ctk.dialogs import ask_yes_no
        if not ask_yes_no(
            self,
            "确认放弃",
            "是否确认放弃本次记录？\n放弃后不会生成结算，也不会写入历史记录和收支统计。"
        ):
            return
        worker = self.worker
        self.worker = None
        self.set_new_state("idle")
        self.stats_text.set("本次记录已放弃")
        self.status_var.set(f"已放弃 · v{core.APP_VERSION}")
        worker.stop(finalize=False, reason="abandon")

    def finish_wage_settlement(self) -> None:
        if not self.worker:
            messagebox.showinfo("提示", "当前没有正在记录的会话")
            return
        from src.gui_ctk.dialogs import ask_yes_no
        if not ask_yes_no(
            self,
            "确认已小退角色",
            "请确认收钱角色已经小退或下线（退出当前角色后聊天记录才会写盘）。\n\n如果您尚未小退，请先在游戏中小退角色。\n\n确认已完成小退后，点击“确定”开始生成结算账单。",
        ):
            return
        worker = self.worker
        self.worker = None
        self.set_new_state("writing")
        self.stats_text.set("正在采集并解析本次聊天记录……")
        self.status_var.set("等待小退写盘……")
        if worker:
            worker.stop(finalize=True, reason="settlement")

    def cancel_writeback_wait(self) -> None:
        """Cancel waiting for log writeback."""
        if self.worker:
            self.worker.stop(finalize=False, reason="cancel_wait")
        self.set_new_state("recording")
        self.status_var.set("已取消等待小退写盘")

    def wait_for_settlement(self, attempts: int = 0) -> None:
        if not self.session_dir:
            self.status_var.set("未设置监控目录，无法生成结算")
            return
        try:
            report = core.build_settlement_report(self.session_dir)
            if report and (report.get("items") or report.get("purchases") or report.get("purchase_count")):
                self.new_report = report
                self.stats_text.set(self.format_settlement_summary(report))
                self.set_new_state("ready")
                self.status_var.set("结算已就绪 · 点击『查看副本账单』入账")
                self.open_settlement_confirm_dialog()
                return
        except Exception as exc:
            self.status_var.set(f"结算读取异常：{exc}")

        if attempts >= 10:
            self.writeback_wait_var.set("等待超时：尚未检测到聊天日志写盘。请确认已在游戏中小退或退出角色。")
            self.status_var.set("日志读盘超时 · 请小退后重试")
            return

        self.writeback_wait_var.set(f"第 {attempts + 1} 次读取：等待聊天记录写盘。请确认已小退/退出角色。")
        self.after(2000, lambda: self.wait_for_settlement(attempts + 1))

    def format_settlement_summary(self, report: dict) -> str:
        def gold_text(value: object) -> str:
            try:
                amount = float(value or 0)
            except Exception:
                amount = 0
            if amount.is_integer():
                return f"{int(amount)}金"
            return f"{amount:.2f}金"

        member_count = int(report.get("member_count") or 1)
        if report.get("purchases") or report.get("purchase_count") is not None:
            purchase_count = int(report.get("purchase_count") or len(report.get("purchases") or []))
            total = float(report.get("total_auction_gold") or report.get("paid_purchase_total_gold") or report.get("calculated_purchase_total_gold") or 0)
            wage = report.get("average_wage_gold")
            if wage is None:
                wage = total / member_count if member_count else 0
            instance = report.get("instance_name") or "未识别剧本"
            return f"{instance}\n共 {purchase_count} 件成交，总额 {gold_text(total)}，{member_count} 人工资 {gold_text(wage)}/人"
        items = report.get("items", [])
        total = sum(item.get("price", 0) for item in items)
        return f"共 {len(items)} 件物品，总额 {fmt_money(total)}，{member_count} 人工资 {fmt_money(total / member_count)}/人"

    def make_report(self) -> None:
        if not self.session_dir:
            messagebox.showinfo("提示", "当前没有正在记录的会话")
            return
        report = self.new_report or core.build_settlement_report(self.session_dir)
        if not report:
            messagebox.showinfo("提示", "未读到有效的副本账单，请确认已在游戏中小退角色")
            return
        self.new_report = report
        self.open_settlement_confirm_dialog()

    def open_settlement_confirm_dialog(self) -> None:
        if not self.session_dir or not self.new_report:
            messagebox.showinfo("提示", "未读到有效的副本账单，请确认已在游戏中小退角色")
            return
        SettlementConfirmDialog(self, self, self.session_dir, self.new_report)

    def show_income_context_menu(self, event) -> None:
        # Track the last clicked label for context menu actions
        widget = event.widget
        target = widget
        while target and not hasattr(target, '_income_record') and target != self:
            target = getattr(target, 'master', None)
        if target and hasattr(target, '_income_record'):
            self._income_last_clicked = target
        else:
            self._income_last_clicked = None
        commands = [
            ("刷新页面", self.refresh_income_page),
            ("修改记录", self.edit_income_page_selected),
            ("删除记录", self.delete_income_page_selected)
        ]
        CTkContextMenu(self, commands, event)

    def edit_income_page_selected(self) -> None:
        """Open edit dialog for the right-clicked income record."""
        target = getattr(self, "_income_last_clicked", None)
        record = getattr(target, "_income_record", None) if target else None
        if not record:
            messagebox.showinfo("提示", "请先右键选择一条要修改的收支记录。")
            return

        record_idx = -1
        for idx, rec in enumerate(getattr(self, "income_records", [])):
            if rec is record or rec.get("id") == record.get("id") or (
                rec.get("recorded_at") == record.get("recorded_at") and rec.get("role") == record.get("role")
            ):
                record_idx = idx
                break

        from src.gui_ctk.dialogs.income_edit import IncomeEditDialog
        IncomeEditDialog(self, self, record, record_idx)

    def delete_income_page_selected(self) -> None:
        """Delete the right-clicked income record."""
        target = getattr(self, "_income_last_clicked", None)
        record = getattr(target, "_income_record", None) if target else None
        if not record:
            messagebox.showinfo("提示", "请先右键选择一条要删除的收支记录。")
            return

        from src.gui_ctk.dialogs import ask_yes_no
        role = record.get("role") or "未知角色"
        instance = record.get("instance") or "未命名副本"
        time_str = record.get("recorded_at") or ""
        if not ask_yes_no(self, "确认删除", f"确定要删除该条收支记录吗？\n\n【{time_str}】{role} - {instance}"):
            return

        import jx3_click_monitor as core
        try:
            records = core.load_income_memory(INCOME_MEMORY_PATH)
            rec_id = record.get("id")
            new_records = []
            for r in records:
                if rec_id and r.get("id") == rec_id:
                    continue
                if not rec_id and r.get("recorded_at") == record.get("recorded_at") and r.get("role") == record.get("role"):
                    continue
                new_records.append(r)
            core.save_income_memory(INCOME_MEMORY_PATH, new_records)
            self.refresh_income_page()
            self.status_var.set("✅ 已删除该收支记录")
        except Exception as exc:
            messagebox.showerror("删除失败", f"无法删除记录：{exc}")

    def show_growth_context_menu(self, event) -> None:
        selection = []
        # Try to find which row was clicked based on _orig_idx attribute
        w = event.widget
        # Navigate up to the master until we find _orig_idx
        while w and not hasattr(w, '_orig_idx') and w != self:
            w = w.master
            
        if w and hasattr(w, '_orig_idx'):
            selection = [str(w._orig_idx)]
            
        if not selection:
            return
            
        commands = []
        try:
            iid = selection[0]
            if int(iid) >= 0 and int(iid) < len(self.growth_records):
                rec = self.growth_records[int(iid)]
                ownerkey = self.growth_ownerkey(rec)
                
                def hide_role() -> None:
                    self.hidden_growth_ownerkeys.add(ownerkey)
                    self.refresh_growth_page()
                    
                commands.append(("隐藏此角色本周所有进度", hide_role))
        except Exception:
            pass

        if not commands:
            return
            
        from src.gui_ctk.widgets import CTkContextMenu
        CTkContextMenu(self, commands, event)

    def growth_ownerkey(self, rec: dict) -> str:
        return f"{rec.get('account', '')}:{rec.get('server', '')}:{rec.get('name', '')}"

    def growth_filtered_records(self) -> list[tuple[int, dict]]:
        out: list[tuple[int, dict]] = []
        for idx, rec in enumerate(self.growth_records):
            ownerkey = self.growth_ownerkey(rec)
            if ownerkey in self.hidden_growth_ownerkeys: continue
            if self.growth_role_selection_initialized and self.selected_growth_ownerkeys and ownerkey not in self.selected_growth_ownerkeys: continue
            out.append((idx, rec))
        return out

    def get_dungeon_progress_text(self, rec: dict, mid: str) -> str:
        for dungeon in rec.get("dungeons") or []:
            if str(dungeon.get("map_id")) == str(mid):
                bosses = dungeon.get("bosses") or []
                boss_names = dungeon.get("boss_names") or []
                if bosses and boss_names and len(bosses) <= len(boss_names):
                    res = []
                    for i, boss in enumerate(bosses):
                        if boss is True:
                            res.append("●")
                        elif boss is False:
                            res.append("○")
                        else:
                            res.append("·")
                    return " | ".join(res)
                return " ".join("●" if boss is True else "○" if boss is False else "·" for boss in bosses) if bosses else str(dungeon.get("progress") or "--")
        return "--"

    def get_role_password(self, rec: dict) -> str:
        """Get stored password for a character record."""
        key = self.growth_record_dedupe_key(rec)
        key_str = f"{key[0]}|{key[1]}|{key[2]}"
        passwords = self.config_data.get("role_passwords", {})
        return str(passwords.get(key_str) or "")

    def set_role_password(self, rec: dict, password: str) -> None:
        """Set and save password for a character record."""
        key = self.growth_record_dedupe_key(rec)
        key_str = f"{key[0]}|{key[1]}|{key[2]}"
        if "role_passwords" not in self.config_data:
            self.config_data["role_passwords"] = {}
        self.config_data["role_passwords"][key_str] = password.strip()
        self.save_config()
        self.refresh_growth_role_list()

    def prompt_set_role_password(self, rec: dict) -> None:
        """Open input dialog to add/edit password for a character."""
        from src.gui_ctk.dialogs import prompt_input
        role_name = rec.get("name") or "未命名角色"
        current_pwd = self.get_role_password(rec)
        val = prompt_input(
            self,
            title="设置角色密码",
            message=f"请输入【{role_name}】的账号密码：",
            default_value=current_pwd,
        )
        if val is not None:
            self.set_role_password(rec, val)
            if val.strip():
                self.status_var.set(f"🔑 已更新角色【{role_name}】的密码！")
            else:
                self.status_var.set(f"🔑 已清除角色【{role_name}】的密码！")

    def copy_to_clipboard(self, text: str, label_name: str = "内容") -> None:
        """Copy given text to OS clipboard and display a status hint."""
        text = str(text or "").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status_var.set(f"📋 已复制 {label_name} 到剪贴板：{text}")

    def on_password_cell_double_click(self, rec: dict) -> None:
        """Handle double-click on password cell."""
        pwd = self.get_role_password(rec)
        if pwd:
            self.copy_to_clipboard(pwd, "密码")
        else:
            self.prompt_set_role_password(rec)

    def update_growth_columns(self) -> None:
        if hasattr(self, "growth_role_tree"):
            self.growth_role_tree.configure_columns(self.growth_role_columns())

    def growth_role_columns(self) -> list[dict]:
        """Return growth page column metadata used by tests and legacy table code."""
        columns = [
            {"key": "account", "text": "账号", "anchor": "w"},
            {"key": "server", "text": "区服", "anchor": "w"},
            {"key": "name", "text": "角色", "anchor": "w"},
            {"key": "password", "text": "密码", "anchor": "center"},
            {"key": "score", "text": "装分", "anchor": "e"},
        ]
        for mid in self.growth_visible_dungeon_ids():
            mid_text = str(mid)
            columns.append({
                "key": f"dungeon_{mid_text}",
                "text": self.growth_dungeon_map.get(mid_text, f"秘境#{mid_text}"),
                "anchor": "center",
            })
        return columns

    def growth_visible_dungeon_ids(self) -> list[str]:
        """Return the list of visible dungeon IDs for the grid."""
        if hasattr(self, "selected_growth_dungeons") and self.selected_growth_dungeons:
            return sorted(list(self.selected_growth_dungeons))
            
        if hasattr(self, "growth_dungeon_map") and self.growth_dungeon_map:
            ids = list(self.growth_dungeon_map.keys())
            ids.sort(reverse=True)
            return ids[:4]
        return []

    def build_growth_dungeon_map(self, records: list[dict]) -> dict[str, str]:
        """Build a mapping of dungeon map_id to readable name."""
        dmap = {}
        for rec in records:
            for dungeon in rec.get("dungeons") or []:
                mid = str(dungeon.get("map_id", ""))
                name = dungeon.get("name", "")
                if mid and name and mid not in dmap:
                    dmap[mid] = name
        return dmap

    def show_growth_dungeon_menu(self, event):
        import tkinter as tk
        if not hasattr(self, "growth_dungeon_map") or not self.growth_dungeon_map: return
        
        menu = tk.Menu(self, tearoff=0, bg="#2d2d30", fg="#cccccc", activebackground="#007acc", activeforeground="white")
        all_ids = list(self.growth_dungeon_map.keys())
        all_ids.sort(reverse=True)
        
        def toggle_dungeon(mid):
            if not hasattr(self, "selected_growth_dungeons"):
                self.selected_growth_dungeons = set()
            if not self.selected_growth_dungeons:
                self.selected_growth_dungeons = set(all_ids[:4])
                
            if mid in self.selected_growth_dungeons:
                self.selected_growth_dungeons.remove(mid)
            else:
                self.selected_growth_dungeons.add(mid)
                
            self.config_data["selected_growth_dungeons"] = list(self.selected_growth_dungeons)
            if hasattr(self, "save_config"):
                self.save_config()
            else:
                import json
                CONFIG_PATH.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.refresh_growth_role_list()

        for mid in all_ids:
            name = self.growth_dungeon_map.get(mid, f"秘境#{mid}")
            has_explicit = hasattr(self, "selected_growth_dungeons") and bool(self.selected_growth_dungeons)
            if has_explicit:
                is_checked = mid in self.selected_growth_dungeons
            else:
                is_checked = mid in all_ids[:4]
                
            label = f"{'☑' if is_checked else '☐'} {name}"
            menu.add_command(label=label, command=lambda m=mid: toggle_dungeon(m))
            
        menu.tk_popup(event.x_root, event.y_root)

    def refresh_growth_role_list(self) -> None:
        if not hasattr(self, "growth_role_grid"): return

        import customtkinter as ctk
        from src.gui_ctk.themes import COLORS as C, FONTS as F

        # Clear existing children
        for child in self.growth_role_grid.winfo_children():
            child.destroy()

        dungeons = self.growth_visible_dungeon_ids()

        # Draw header row
        ctk.CTkLabel(self.growth_role_grid, text="账号", font=F["table_header"], text_color=C["text_secondary"], anchor="w").grid(row=0, column=0, padx=4, pady=10)
        ctk.CTkLabel(self.growth_role_grid, text="区服", font=F["table_header"], text_color=C["text_secondary"], anchor="w").grid(row=0, column=1, padx=4, pady=10)
        ctk.CTkLabel(self.growth_role_grid, text="角色", font=F["table_header"], text_color=C["text_secondary"], anchor="w").grid(row=0, column=2, padx=4, pady=10)
        ctk.CTkLabel(self.growth_role_grid, text="密码", font=F["table_header"], text_color=C["text_secondary"], anchor="center").grid(row=0, column=3, padx=4, pady=10)
        ctk.CTkLabel(self.growth_role_grid, text="装分", font=F["table_header"], text_color=C["text_secondary"], anchor="e").grid(row=0, column=4, padx=4, pady=10)

        for c, mid in enumerate(dungeons, 5):
            name = self.growth_dungeon_map.get(str(mid), f"秘境#{mid}")
            ctk.CTkLabel(self.growth_role_grid, text=name, font=F["table_header"], text_color=C["text_secondary"]).grid(row=0, column=c, padx=4, pady=10)

        roles = self.growth_filtered_records()
        for r_idx, (orig_idx, rec) in enumerate(roles, 1):
            account = str(rec.get("account") or "")
            server = str(rec.get("server") or "")
            name = str(rec.get("name") or "")
            score = str(rec.get("score") or "")
            pwd = self.get_role_password(rec)

            acc_lbl = ctk.CTkLabel(self.growth_role_grid, text=account, font=F["body"], text_color=C["text_primary"], anchor="w")
            acc_lbl.grid(row=r_idx, column=0, padx=4, pady=5)
            acc_lbl.bind("<Double-1>", lambda e, a=account: self.copy_to_clipboard(a, "账号"))

            ctk.CTkLabel(self.growth_role_grid, text=server, font=F["body"], text_color=C["text_primary"], anchor="w").grid(row=r_idx, column=1, padx=4, pady=5)
            ctk.CTkLabel(self.growth_role_grid, text=name, font=F["body"], text_color=C["text_primary"], anchor="w").grid(row=r_idx, column=2, padx=4, pady=5)

            pwd_text = "••••••" if pwd else "双击设置"
            pwd_color = C["text_primary"] if pwd else C["text_muted"]
            pwd_lbl = ctk.CTkLabel(self.growth_role_grid, text=pwd_text, font=F["body"], text_color=pwd_color, anchor="center")
            pwd_lbl.grid(row=r_idx, column=3, padx=4, pady=5)
            pwd_lbl.bind("<Double-1>", lambda e, r=rec: self.on_password_cell_double_click(r))

            ctk.CTkLabel(self.growth_role_grid, text=score, font=F["body"], text_color=C["text_primary"], anchor="e").grid(row=r_idx, column=4, padx=4, pady=5)

            for c, mid in enumerate(dungeons, 5):
                prog = self.get_dungeon_progress_text(rec, mid)
                has_not_killed = "○" in prog or "·" in prog
                has_killed = "●" in prog
                if has_killed and not has_not_killed:
                    color = C.get("green", "#2ecc71")
                elif has_not_killed:
                    color = C.get("red", "#e74c3c")
                else:
                    color = C["text_muted"]

                prog_short = prog.replace(" | ", " ")
                if len(prog_short) > 20:
                    prog_short = prog_short[:17] + "..."

                lbl = ctk.CTkLabel(self.growth_role_grid, text=prog_short,
                                   font=("Segoe UI Emoji", 16, "bold"), text_color=color)
                lbl.grid(row=r_idx, column=c, padx=4, pady=5)
                lbl._orig_idx = orig_idx

        # Re-apply bindings for the new widgets
        self.growth_role_grid.bind("<Button-3>", self.show_growth_dungeon_menu)
        for child in self.growth_role_grid.winfo_children():
            child.bind("<Button-3>", self.show_growth_dungeon_menu)

    def normalize_growth_text(self, value: object) -> str:
        return str(value or "").strip().lower()

    def normalize_growth_server(self, value: object) -> str:
        text = self.normalize_growth_text(value)
        for prefix in ("电信区", "双线区", "无界区", "缘起区", "网通区"):
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix):]
        return text

    def growth_record_dedupe_key(self, rec: dict) -> tuple:
        """委托给 GrowthService.record_dedupe_key（消除代码重复）。"""
        from src.services.growth_service import GrowthService
        return GrowthService.record_dedupe_key(rec)

    def merge_growth_record_values(self, base: dict, incoming: dict) -> dict:
        """委托给 GrowthService.merge_record_values（消除代码重复）。"""
        from src.services.growth_service import GrowthService
        return GrowthService.merge_record_values(base, incoming)

    def dedupe_growth_records(self, records: list) -> list:
        """委托给 GrowthService.dedupe_records（消除代码重复）。"""
        from src.services.growth_service import GrowthService
        return GrowthService.dedupe_records(records)

    def merge_growth_records(
        self,
        records: list,
        extra_records: list | None = None,
        *_unused_maps: dict,
    ) -> list:
        """委托给 GrowthService.merge_records（消除代码重复）。"""
        from src.services.growth_service import GrowthService
        return GrowthService.merge_records(records, extra_records)

    def refresh_growth_page(self, silent: bool = False) -> bool:
        jx3_path = self.jx3_var.get()
        if not jx3_path or not Path(jx3_path).exists():
            if not silent: messagebox.showerror("路径错误", "请先设置剑三 zhcn_hd 路径")
            return False
        if not hasattr(self, "_growth_service"):
            from src.services.growth_service import GrowthService
            self._growth_service = GrowthService()
        self.growth_source_var.set("正在读取茗伊角色统计数据库……"); self.update_idletasks()
        def on_data_loaded(records: list[dict]):
            self.growth_records = records
            self.growth_dungeon_map = self.build_growth_dungeon_map(records)
            self.refresh_growth_role_list()
            self.growth_source_var.set(f"共 {len(records)} 个角色 · 从茗伊数据库只读加载")
            self.save_config()
        def on_load_error(exc: Exception):
            self.growth_source_var.set("读取失败")
            if not silent: messagebox.showerror("读取失败", f"无法读取角色数据：{exc}")
        self._growth_service.load_async(
            jx3_path=jx3_path,
            callback=lambda recs: self.after(0, lambda: on_data_loaded(recs)),
            on_error=lambda err: self.after(0, lambda: on_load_error(err)),
            force=True
        )
        return True

    def parse_member_count(self) -> int | None:
        value = self.member_var.get().strip()
        return int(value) if value else None

    def parse_personal_subsidy(self) -> float | None:
        value = self.personal_subsidy_var.get().strip()
        return float(value) if value else None

    def log_message(self, text: str) -> None:
        self.status_var.set(str(text))

    def post_log(self, text: str) -> None:
        self.queue.put(("log", text))
        self.queue_event.set()

    def post_status(self, summary: dict, report: dict, context: str = "new") -> None:
        self.queue.put(("status", f"已解析 {summary.get('total_events', 0)} 条记录"))
        self.queue.put(("settlement", report))
        self.queue_event.set()

    def post_monitor_progress(self, summary: dict) -> None:
        self.queue.put(("status", f"监控中 · 新增 {summary.get('last_poll_added', 0)} 条 · 总计 {summary.get('total_events', 0)} 条"))
        self.queue_event.set()

    def post_recording_reset(self) -> None:
        self.queue.put(("recording_reset", None))
        self.queue_event.set()

    def post_settlement_ready(self, session_dir: Path, report: dict) -> None:
        self.session_dir = session_dir
        self.queue.put(("settlement_ready", {"session_dir": str(session_dir), "report": report}))
        self.queue_event.set()

    def post_writeback_waiting(self, attempt: int, session_dir: Path) -> None:
        self.queue.put(("status", f"等待小退写盘 · 第 {attempt} 次检查 · {session_dir.name}"))
        self.queue.put(("writeback_waiting", {"attempt": attempt, "session_dir": str(session_dir)}))
        self.queue_event.set()

    def apply_income_visible_columns(self, persist: bool = False) -> None:
        # Column visibility toggle is now handled via config (grid layout, no dynamic columns)
        if persist:
            self.save_config()
        self.refresh_income_page()

    def cancel_writeback_wait(self) -> None:
        from src.gui_ctk.dialogs import ask_yes_no
        if not ask_yes_no(
            self,
            "确认取消",
            "取消会导致本次自动入账失败。\n\n后续可在历史记录中手动导入本次记录。\n\n确认取消等待聊天数据库写盘吗？",
        ):
            return
        for thread in list(__import__("threading").enumerate()):
            if isinstance(thread, MonitorWorker) and self.session_dir and thread.session_dir == self.session_dir:
                thread.stop(finalize=False, reason="cancel_wait")
                break
        self.set_new_state("idle")
        self.stats_text.set("已取消等待写盘，本次未自动入账；可稍后从历史记录手动导入 Session。")
        self.writeback_wait_var.set("已取消等待写盘。")
        self.status_var.set(f"已取消等待 · v{core.APP_VERSION}")

    def set_new_state(self, state: str) -> None:
        for attr in ("new_idle_frame", "new_recording_frame", "new_writing_frame"):
            frame = getattr(self, attr, None)
            if frame is not None:
                frame.pack_forget()
        if hasattr(self, "generate_btn"):
            self.generate_btn.pack_forget()
        if state == "idle" and hasattr(self, "new_idle_frame"):
            self.new_idle_frame.pack(fill="x", padx=20, pady=(0, 20))
        elif state == "recording" and hasattr(self, "new_recording_frame"):
            self.new_recording_frame.pack(fill="x", padx=20, pady=(0, 20))
        elif state == "writing" and hasattr(self, "new_writing_frame"):
            self.new_writing_frame.pack(fill="x", padx=20, pady=(0, 20))
        elif state == "ready" and hasattr(self, "generate_btn"):
            self.generate_btn.pack(fill="x", padx=20, pady=(0, 14))

    def open_my_chat_importer(self) -> None:
        from src.gui_ctk.dialogs import ChatImporter
        ChatImporter(self, self)

    def open_income_analysis(self) -> None:
        from src.gui_ctk.dialogs import IncomeAnalysisWindow
        IncomeAnalysisWindow(self, self)

    def open_income_filter_window(self) -> None:
        from src.gui_ctk.dialogs import IncomeFilterWindow
        IncomeFilterWindow(self, self)

    def open_income_columns_window(self) -> None:
        from src.gui_ctk.dialogs import IncomeColumnsWindow
        IncomeColumnsWindow(self, self)

    def edit_income_page_selected(self) -> None:
        row = getattr(self, "_income_last_clicked", None)
        if row is None or not hasattr(row, '_income_record'):
            if not self.income_records:
                messagebox.showinfo("提示", "当前没有可编辑的记录")
                return
            IncomeEditDialog(self, self, self.income_records[0], 0)
        else:
            rec = row._income_record
            idx = self.income_records.index(rec) if rec in self.income_records else 0
            IncomeEditDialog(self, self, rec, idx)

    def delete_income_page_selected(self) -> None:
        row = getattr(self, "_income_last_clicked", None)
        if row is None or not hasattr(row, '_income_record'):
            if not self.income_records:
                messagebox.showinfo("提示", "当前没有可删除的记录")
                return
            del self.income_records[0]
        else:
            rec = row._income_record
            from src.gui_ctk.dialogs import ask_yes_no
            if not ask_yes_no(self, "确认删除", "确定删除选中的收支记录？"):
                return
            if rec in self.income_records:
                self.income_records.remove(rec)

        # Perform write IO in background
        def _async_delete():
            try:
                from src.core.income_memory import save_income_memory
                save_income_memory(INCOME_MEMORY_PATH, {"records": self.income_records})
                self.queue.put(("refresh_income", None))
            except Exception as e:
                self.queue.put(("error", {"title": "删除失败", "message": str(e)}))
        threading.Thread(target=_async_delete, daemon=True).start()

    def view_history_selected(self) -> None:
        # Use the last clicked history label
        row = getattr(self, "_history_last_clicked", None)
        if row is None or not hasattr(row, '_session_path'):
            if not self.history_sessions:
                return
            session_dir = self.history_sessions[0]["path"]
        else:
            session_dir = row._session_path
        if not session_dir:
            return
        self.show_history_body_window(session_dir)

    def history_body_text(self, session_dir: Path) -> str:
        report_path = session_dir / "settlement_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            return core.render_settlement_markdown(report)
        summary_path = session_dir / "summary.json"
        if summary_path.exists():
            data = json.loads(summary_path.read_text(encoding="utf-8-sig"))
            return json.dumps(data, ensure_ascii=False, indent=2)
        raw_path = session_dir / "raw_events.jsonl"
        if raw_path.exists():
            return raw_path.read_text(encoding="utf-8", errors="replace")[:200000]
        return "该历史记录暂无可查看正文。"

    def show_history_body_window(self, session_dir: Path) -> None:
        win = ctk.CTkToplevel(self)
        self._history_body_win = win
        win.title(f"历史记录正文 - {session_dir.name}")
        win.geometry("900x650")
        win.configure(fg_color="#1e1e1e")
        win.transient(self)
        win.lift(self)
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), setattr(self, "_history_body_win", None)))
        header = ctk.CTkFrame(win, fg_color="#2d2d30", corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=session_dir.name, font=("Segoe UI", 12, "bold"), text_color="#cccccc").pack(side="left", padx=16, pady=12)
        text = ctk.CTkTextbox(win, wrap="word", font=("Segoe UI", 12), fg_color="#1e1e1e", text_color="#cccccc", border_width=0, corner_radius=0)
        text.pack(fill="both", expand=True, padx=12, pady=12)
        try:
            text.insert("0.0", self.history_body_text(session_dir))
        except Exception as exc:
            text.insert("0.0", f"读取失败：{exc}")
        text.configure(state="disabled")

    def refresh_history_sessions(self) -> None:
        """Refresh the history session list using grid layout (same as Growth page)."""
        if not hasattr(self, "history_scroll"): return

        from pathlib import Path
        out_dir = self.out_var.get() or DEFAULT_OUT_DIR
        base = Path(out_dir).resolve()

        sessions = []
        if base.exists():
            dirs = [p for p in base.iterdir() if p.is_dir()]
            dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            display_idx = 1
            for sd in dirs:
                meta_file = sd / "session_meta.json"
                if not meta_file.exists():
                    meta_file = sd / "session.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as mf:
                            meta = json.load(mf)
                        
                        if meta.get("history_confirmed") is False:
                            continue
                        if meta.get("watch_mode") == "gui" and meta.get("history_confirmed") is not True:
                            continue
                        if meta.get("history_deleted") is True:
                            continue
                        
                        report_file = sd / "settlement_report.json"
                        report = core.read_json(report_file, {}) if report_file.exists() else {}
                        
                        created_val = report.get("session_start_label") or meta.get("created_label") or meta.get("start_label")
                        if not created_val:
                            created_at = meta.get("created_at") or meta.get("start_time")
                            if isinstance(created_at, (int, float)):
                                from datetime import datetime
                                created_val = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                created_val = str(created_at or "")
                        
                        identity = report.get("identity") or meta.get("identity") or {}
                        role_name = identity.get("role_name") or report.get("self_name") or meta.get("name") or meta.get("role_name") or ""
                        server = identity.get("server") or meta.get("server") or ""
                        if server and role_name:
                            role = f"{server} - {role_name}"
                        elif role_name:
                            role = role_name
                        elif server:
                            role = server
                        else:
                            role = "-"
                        
                        instance = report.get("instance_name") or identity.get("activity") or meta.get("activity") or meta.get("dungeon_name") or "未识别"
                        
                        item = {
                            "seq": str(display_idx),
                            "recorded_at": created_val[:19].replace("T", " "),
                            "source": meta.get("history_source", "未知"),
                            "role": role,
                            "instance": instance,
                            "path": sd
                        }
                        sessions.append(item)
                        display_idx += 1
                    except Exception as e:
                        pass

        self.history_sessions = sessions
        self.history_session_paths = {str(item["seq"]): item["path"] for item in sessions}

        # Clear existing children
        for child in self.history_scroll.winfo_children():
            child.destroy()

        # Define columns (no fixed width — adapt to content)
        col_defs = [
            ("#", "e"),
            ("时间", "w"),
            ("来源", "w"),
            ("角色", "w"),
            ("摘要", "w"),
        ]
        num_cols = len(col_defs)

        # Draw header row
        for c, (text, anchor) in enumerate(col_defs):
            ctk.CTkLabel(self.history_scroll, text=text, font=F["table_header"],
                         text_color=C["text_secondary"], anchor=anchor).grid(
                row=0, column=c, padx=4, pady=10)

        # Collect widgets per row for row hover effect
        row_widgets_history: dict[int, list[ctk.CTkLabel]] = {}

        # Draw data rows
        for r_idx, item in enumerate(sessions, 1):
            row_labels: list[ctk.CTkLabel] = []

            for c, (text, anchor) in enumerate(col_defs):
                if c == 0:
                    val = item["seq"]
                    text_color = C["text_muted"]
                elif c == 1:
                    val = item["recorded_at"]
                    text_color = C["text_primary"]
                elif c == 2:
                    val = item["source"]
                    text_color = C["text_primary"]
                elif c == 3:
                    val = item["role"]
                    text_color = C["text_primary"]
                else:
                    val = item["instance"]
                    text_color = C["text_primary"]

                lbl = ctk.CTkLabel(self.history_scroll, text=str(val), font=F["body"],
                                   text_color=text_color, anchor=anchor, fg_color="transparent")
                lbl.grid(row=r_idx, column=c, padx=4, pady=5)
                # Store session path on all labels for context menu & double-click
                lbl._session_path = item["path"]
                lbl._session_seq = item["seq"]
                if hasattr(lbl, "_label") and lbl._label:
                    lbl._label._session_path = item["path"]
                    lbl._label._session_seq = item["seq"]
                row_labels.append(lbl)

            row_widgets_history[r_idx] = row_labels

        # Bind hover events for history rows
        for r_idx, labels in row_widgets_history.items():
            def make_hover(labs=labels):
                def _enter(event):
                    for l in labs:
                        try:
                            l.configure(fg_color=C["table_hover"])
                        except Exception:
                            pass
                def _leave(event):
                    for l in labs:
                        try:
                            l.configure(fg_color="transparent")
                        except Exception:
                            pass
                return _enter, _leave

            _on_enter, _on_leave = make_hover(labels)
            for lbl in labels:
                lbl.bind("<Enter>", _on_enter)
                lbl.bind("<Leave>", _on_leave)
                if hasattr(lbl, "_label") and lbl._label:
                    lbl._label.bind("<Enter>", _on_enter)
                    lbl._label.bind("<Leave>", _on_leave)

        # Re-apply bindings (unbind first to avoid duplicate bindings on each refresh)
        try:
            self.history_scroll.unbind("<Button-3>")
            for child in self.history_scroll.winfo_children():
                child.unbind("<Button-3>")
                if hasattr(child, "_label"):
                    child._label.unbind("<Button-3>")
                if hasattr(child, "_canvas") and child._canvas:
                    child._canvas.unbind("<Button-3>")
                if hasattr(child, "_textbox") and child._textbox:
                    child._textbox.unbind("<Button-3>")
                for sub_child in child.winfo_children():
                    sub_child.unbind("<Button-3>")
        except Exception:
            pass

        self.history_scroll.bind("<Button-3>", self.show_history_context_menu)
        for child in self.history_scroll.winfo_children():
            child.bind("<Button-3>", self.show_history_context_menu)
            if hasattr(child, "_label"):
                child._label.bind("<Button-3>", self.show_history_context_menu)
            if hasattr(child, "_canvas") and child._canvas:
                child._canvas.bind("<Button-3>", self.show_history_context_menu)
            if hasattr(child, "_textbox") and child._textbox:
                child._textbox.bind("<Button-3>", self.show_history_context_menu)
            for sub_child in child.winfo_children():
                sub_child.bind("<Button-3>", self.show_history_context_menu)

        # Bind double-click to view history body
        def on_double_click(event):
            widget = event.widget
            target = widget
            while target and not hasattr(target, '_session_path'):
                target = target.master if hasattr(target, 'master') else None
            if target and hasattr(target, '_session_path'):
                self.show_history_body_window(target._session_path)
        try:
            self.history_scroll.unbind("<Double-1>")
            for child in self.history_scroll.winfo_children():
                child.unbind("<Double-1>")
                if hasattr(child, "_label"):
                    child._label.unbind("<Double-1>")
                if hasattr(child, "_canvas") and child._canvas:
                    child._canvas.unbind("<Double-1>")
                if hasattr(child, "_textbox") and child._textbox:
                    child._textbox.unbind("<Double-1>")
                for sub_child in child.winfo_children():
                    sub_child.unbind("<Double-1>")
        except Exception:
            pass

        self.history_scroll.bind("<Double-1>", on_double_click)
        for child in self.history_scroll.winfo_children():
            child.bind("<Double-1>", on_double_click)
            if hasattr(child, "_label"):
                child._label.bind("<Double-1>", on_double_click)
            if hasattr(child, "_canvas") and child._canvas:
                child._canvas.bind("<Double-1>", on_double_click)
            if hasattr(child, "_textbox") and child._textbox:
                child._textbox.bind("<Double-1>", on_double_click)
            for sub_child in child.winfo_children():
                sub_child.bind("<Double-1>", on_double_click)

        if hasattr(self, "status_var"):
            self.status_var.set(f"已加载历史记录 - {len(sessions)} 条")

    def refresh_income_page(self) -> None:
        """Refresh the income/expense list using grid layout (same as Growth page)."""
        if not hasattr(self, "income_scroll"): return

        import jx3_click_monitor as core

        query = ""
        if hasattr(self, "income_search_var"):
            query = self.income_search_var.get()

        records = core.search_income_memory(INCOME_MEMORY_PATH, query)
        if hasattr(self, "apply_income_filters"):
            records = self.apply_income_filters(records)

        self.income_records = records

        # Clear existing children
        for child in self.income_scroll.winfo_children():
            child.destroy()

        # Define columns (same as Growth page: header row + data rows, no fixed width)
        col_defs = [
            ("时间", "w", "recorded_at"),
            ("区服", "w", "server"),
            ("角色", "w", "role"),
            ("副本名称", "w", "instance"),
            ("收入", "e", "income_gold"),
            ("支出", "e", "expense_gold"),
            ("净收入", "e", "net_gold"),
            ("黑本角色", "w", "black_role"),
        ]
        num_cols = len(col_defs)

        # Draw header row
        for c, (text, anchor, _) in enumerate(col_defs):
            ctk.CTkLabel(self.income_scroll, text=text, font=F["table_header"],
                         text_color=C["text_secondary"], anchor=anchor).grid(
                row=0, column=c, padx=4, pady=10)

        # Collect widgets per row for row hover effect
        row_widgets_income: dict[int, list[ctk.CTkLabel]] = {}

        # Draw data rows
        for r_idx, r in enumerate(records, 1):
            row_labels: list[ctk.CTkLabel] = []

            for c, (text, anchor, key) in enumerate(col_defs):
                val = r.get(key, "")
                text_color = C["text_primary"]
                if key in ("income_gold", "expense_gold", "net_gold"):
                    try:
                        amt = float(val) if val else 0
                        if amt > 0:
                            text_color = C.get("green", "#2ecc71")
                        elif amt < 0:
                            text_color = C.get("red", "#e74c3c")
                    except (ValueError, TypeError):
                        pass
                lbl = ctk.CTkLabel(self.income_scroll, text=str(val), font=F["body"],
                                   text_color=text_color, anchor=anchor, fg_color="transparent")
                lbl.grid(row=r_idx, column=c, padx=4, pady=5)
                # Store record on ALL cell labels for context menu & double click
                lbl._income_record = r
                if hasattr(lbl, "_label") and lbl._label:
                    lbl._label._income_record = r
                row_labels.append(lbl)

            row_widgets_income[r_idx] = row_labels

        # Bind hover events for income rows
        for r_idx, labels in row_widgets_income.items():
            def make_hover(labs=labels):
                def _enter(event):
                    for l in labs:
                        try:
                            l.configure(fg_color=C["table_hover"])
                        except Exception:
                            pass
                def _leave(event):
                    for l in labs:
                        try:
                            l.configure(fg_color="transparent")
                        except Exception:
                            pass
                return _enter, _leave

            _on_enter, _on_leave = make_hover(labels)
            for lbl in labels:
                lbl.bind("<Enter>", _on_enter)
                lbl.bind("<Leave>", _on_leave)
                if hasattr(lbl, "_label") and lbl._label:
                    lbl._label.bind("<Enter>", _on_enter)
                    lbl._label.bind("<Leave>", _on_leave)

        if hasattr(self, "update_income_summary"):
            self.update_income_summary(records)

        # Re-apply bindings (unbind first to avoid duplicates)
        try:
            self.income_scroll.unbind("<Button-3>")
            self.income_scroll.unbind("<Double-1>")
            for child in self.income_scroll.winfo_children():
                child.unbind("<Button-3>")
                child.unbind("<Double-1>")
                if hasattr(child, "_label"):
                    child._label.unbind("<Button-3>")
                    child._label.unbind("<Double-1>")
                if hasattr(child, "_canvas") and child._canvas:
                    child._canvas.unbind("<Button-3>")
                    child._canvas.unbind("<Double-1>")
                if hasattr(child, "_textbox") and child._textbox:
                    child._textbox.unbind("<Button-3>")
                    child._textbox.unbind("<Double-1>")
                for sub_child in child.winfo_children():
                    sub_child.unbind("<Button-3>")
                    sub_child.unbind("<Double-1>")
        except Exception:
            pass

        def on_income_row_double_click(event):
            widget = event.widget
            target = widget
            while target and not hasattr(target, '_income_record') and target != self:
                target = getattr(target, 'master', None)
            if target and hasattr(target, '_income_record'):
                self._income_last_clicked = target
                self.edit_income_page_selected()

        self.income_scroll.bind("<Button-3>", self.show_income_context_menu)
        for child in self.income_scroll.winfo_children():
            child.bind("<Button-3>", self.show_income_context_menu)
            child.bind("<Double-1>", on_income_row_double_click)
            if hasattr(child, "_label"):
                child._label.bind("<Button-3>", self.show_income_context_menu)
                child._label.bind("<Double-1>", on_income_row_double_click)
            if hasattr(child, "_canvas") and child._canvas:
                child._canvas.bind("<Button-3>", self.show_income_context_menu)
                child._canvas.bind("<Double-1>", on_income_row_double_click)
            if hasattr(child, "_textbox") and child._textbox:
                child._textbox.bind("<Button-3>", self.show_income_context_menu)
                child._textbox.bind("<Double-1>", on_income_row_double_click)
            for sub_child in child.winfo_children():
                sub_child.bind("<Button-3>", self.show_income_context_menu)
                sub_child.bind("<Double-1>", on_income_row_double_click)

        # Trigger background cloud sync if enabled
        if self.cloud_sync_enabled_var.get():
            self.trigger_background_cloud_sync(upload_html=False, manual=False)

    def apply_income_filters(self, records: list[dict]) -> list[dict]:
        # Minimal filter implementation
        return records

    def show_history_context_menu(self, event) -> None:
        # Track the last clicked label for context menu actions
        widget = event.widget
        target = widget
        while target and not hasattr(target, '_session_path'):
            target = target.master if hasattr(target, 'master') else None
        if target and hasattr(target, '_session_path'):
            self._history_last_clicked = target
        else:
            self._history_last_clicked = None
        commands = [
            ("刷新记录", self.refresh_history_sessions),
            ("删除记录", self.delete_history_selected)
        ]
        CTkContextMenu(self, commands, event)

    def delete_history_selected(self) -> None:
        # Use the last clicked history label
        row = getattr(self, "_history_last_clicked", None)
        if row is None or not hasattr(row, '_session_path'):
            if not self.history_sessions:
                messagebox.showinfo("提示", "当前没有可删除的历史记录。")
                return
            session_dir = self.history_sessions[0]["path"]
        else:
            session_dir = row._session_path
        if not session_dir or not session_dir.exists():
            messagebox.showinfo("提示", "历史目录不存在或已被删除。")
            self.refresh_history_sessions()
            return
        from src.gui_ctk.dialogs import ask_yes_no
        if not ask_yes_no(self, "确认删除", f"确定删除这条历史记录吗？\n\n{session_dir.name}"):
            return
        self.delete_history_session(session_dir)
        self.refresh_history_sessions()

    def delete_history_session(self, session_dir: Path) -> None:
        live_dir = Path(self.out_var.get() or DEFAULT_OUT_DIR).resolve()
        target = session_dir.resolve()
        if live_dir not in target.parents:
            raise ValueError("只能删除 live 目录内的历史记录")
        trash_history = live_dir / ".trash_history"
        trash_history.mkdir(parents=True, exist_ok=True)
        dest = trash_history / session_dir.name
        if dest.exists():
            dest = trash_history / f"{session_dir.name}_{int(datetime.now().timestamp())}"
        session_dir.rename(dest)

    def update_growth_info(self) -> None:
        self.growth_source_var.set("正在重新解析插件角色信息……")
        self.refresh_growth_page(silent=False)

    def open_growth_filter_dialog(self) -> None:
        """Open the account/role filter dialog."""
        from src.gui_ctk.dialogs.growth_filter import GrowthFilterDialog
        GrowthFilterDialog(self)

    def show_growth_equipment_window(self, rec: dict) -> None:
        import io
        import threading
        import urllib.request
        import tkinter as tk
        from PIL import Image

        from jx3_click_monitor_gui import (
            fetch_jx3box_item_by_name, jx3box_item_effects_text,
            jx3box_plain_text, normalize_jx3box_attr_name,
            normalize_item_search_name, JX3BOX_ICON_URL,
        )

        raw_items = rec.get("items") or []
        win = ctk.CTkToplevel(self)
        win.title(f"装备详情 - {rec.get('name') or ''}")
        win.geometry("1100x680")
        win.transient(self)
        win.lift(self)

        # ── Helpers ──
        def _normalize_items(src: list) -> list[dict]:
            out: list[dict] = []
            for it in src:
                if isinstance(it, dict):
                    out.append(it)
                elif isinstance(it, str):
                    out.append({"name": it, "slot_name": "?"})
                else:
                    out.append({"name": str(it), "slot_name": "?"})
            return out

        # ── Suit data ──
        suit_items_dict: dict = rec.get("suit_items") or {}
        suit_keys = sorted(k for k in suit_items_dict if suit_items_dict[k])
        current_suit: int = int(rec.get("current_suit") or 1)

        if current_suit in suit_items_dict:
            base_items = _normalize_items(suit_items_dict[current_suit])
        elif suit_keys:
            base_items = _normalize_items(suit_items_dict[suit_keys[0]])
        else:
            base_items = _normalize_items(raw_items)

        if not base_items:
            ctk.CTkLabel(win, text="没有读取到装备明细。", font=F["body"],
                         text_color=C["text_muted"]).pack(pady=20)
            return

        # ── Header ──
        header = ctk.CTkFrame(win, fg_color=C["toolbar_bg"], corner_radius=0)
        header.pack(fill="x")
        header_label = ctk.CTkLabel(header,
                     text=f"{rec.get('server') or ''} · {rec.get('name') or ''}  |  装分 {rec.get('score') or '-'}",
                     font=F["card_title"], text_color=C["text_primary"])
        header_label.pack(anchor="w", padx=16, pady=12)

        # ── Body: left detail + right list ──
        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=220)
        body.grid_rowconfigure(0, weight=1)

        # ── Left: detail panel ──
        detail_panel = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=8,
                                    border_width=1, border_color=C["border"])
        detail_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        detail_header_frame = ctk.CTkFrame(detail_panel, fg_color="transparent")
        detail_header_frame.pack(fill="x", padx=14, pady=(14, 4))
        detail_name_var = ctk.StringVar(value="请在右侧选择装备")
        detail_name_label = ctk.CTkLabel(detail_header_frame, textvariable=detail_name_var,
                                         font=("Microsoft YaHei UI", 15, "bold"),
                                         text_color=C["text_primary"])
        detail_name_label.pack(anchor="w")

        detail_text = ctk.CTkTextbox(detail_panel, wrap="word", font=F["body"],
                                     fg_color=C["entry_bg"], text_color=C["text_primary"],
                                     border_width=1, border_color=C["border"])
        detail_text.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        detail_text.configure(state="disabled")

        # ── Right: suit selector + equipment list ──
        list_container = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=8,
                                      border_width=1, border_color=C["border"])
        list_container.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        list_header = ctk.CTkFrame(list_container, fg_color="transparent")
        list_header.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(list_header, text="装备栏", font=F["body"],
                     text_color=C["text_muted"]).pack(side="left")

        suit_var = ctk.StringVar(value=str(current_suit) if current_suit in suit_keys else "1")
        if len(suit_keys) > 1:
            suit_selector = ctk.CTkSegmentedButton(
                list_header, values=[str(s) for s in suit_keys],
                variable=suit_var, font=F["small"],
                selected_color=C["primary"], selected_hover_color=C["primary_hover"],
                corner_radius=4, height=22)
            suit_selector.pack(side="right")

        list_scroll = ctk.CTkScrollableFrame(list_container, fg_color="transparent")
        list_scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # ── State ──
        current_items: list[dict] = list(base_items)
        item_results: dict[int, dict] = {}
        card_widgets: dict[int, dict] = {}
        selected_idx: dict[str, int | None] = {"value": None}
        _next_icon_gen: list[int] = [0]  # generation counter to discard stale icon loads

        # ── Helpers ──
        def _query_jx3box(idx: int, item_name: str) -> None:
            if not item_name:
                return
            try:
                # Compare cached name: first look up in JX3BOX local cache file
                from jx3_click_monitor_gui import load_jx3box_cache
                cache = load_jx3box_cache()

                cache_key = f"name:{item_name}"
                cached_data = cache.get(cache_key)

                # Check if cached data exists and is valid
                if isinstance(cached_data, dict) and not cached_data.get("error"):
                    item_data = cached_data.get("item") or {}
                    cached_name = item_data.get("Name")
                    # Compare names: if exactly matching, just use the cache directly
                    if cached_name == item_name:
                        win.after(0, lambda: _on_result(idx, cached_data))
                        icon_id = item_data.get("IconID")
                        quality = int(item_data.get("Quality") or 0)
                        if icon_id:
                            gen = _next_icon_gen[0]
                            threading.Thread(
                                target=_fetch_icon, args=(idx, str(icon_id), gen, quality), daemon=True
                            ).start()
                        elif quality > 0:
                            gen = _next_icon_gen[0]
                            win.after(0, lambda: _apply_fallback_icon(idx, quality, gen))
                        return

                result = fetch_jx3box_item_by_name(item_name)
            except Exception as exc:
                result = {"error": f"JX3BOX 查询异常: {type(exc).__name__}: {exc}"}
            try:
                win.after(0, lambda: _on_result(idx, result))
            except Exception:
                pass
            # Separately fetch icon (can be slow)
            icon_id = None
            quality = 0
            if isinstance(result, dict) and not result.get("error"):
                item_data = result.get("item") or {}
                icon_id = item_data.get("IconID")
                quality = int(item_data.get("Quality") or 0)
            if icon_id:
                gen = _next_icon_gen[0]
                threading.Thread(
                    target=_fetch_icon, args=(idx, str(icon_id), gen, quality), daemon=True
                ).start()
            elif quality > 0:
                # No icon URL — show quality placeholder immediately
                gen = _next_icon_gen[0]
                win.after(0, lambda: _apply_fallback_icon(idx, quality, gen))

        def _fetch_icon(idx: int, icon_id: str, gen: int, quality: int = 0) -> None:
            cache_key = f"icon:{icon_id}"
            cached = type(self)._EQUIP_ICON_CACHE.get(cache_key)
            if cached is not None:
                win.after(0, lambda: _apply_icon(idx, cached, gen))
                return
            with type(self)._EQUIP_ICON_SEMAPHORE:
                if gen != _next_icon_gen[0]:
                    return
                try:
                    # Implement local persistence icon cache
                    cache_dir = APP_BASE_DIR / "icon_cache"
                    cache_dir.mkdir(exist_ok=True)
                    icon_path = cache_dir / f"{icon_id}.png"

                    if icon_path.exists():
                        data = icon_path.read_bytes()
                    else:
                        req = urllib.request.Request(
                            JX3BOX_ICON_URL.format(icon_id=icon_id),
                            headers={"User-Agent": "jx3-click-monitor/1.0"},
                        )
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            data = resp.read()
                        icon_path.write_bytes(data)

                    pil_image = Image.open(io.BytesIO(data))
                    photo = ctk.CTkImage(pil_image, size=(16, 16))
                    type(self)._EQUIP_ICON_CACHE[cache_key] = photo
                    win.after(0, lambda: _apply_icon(idx, photo, gen))
                except Exception:
                    # Icon download failed — fall back to colored placeholder
                    win.after(0, lambda: _apply_fallback_icon(idx, quality, gen))

        def _apply_icon(idx: int, photo: ctk.CTkImage, gen: int) -> None:
            if gen != _next_icon_gen[0] or not win.winfo_exists():
                return
            w = card_widgets.get(idx)
            if w is not None:
                w.get("name_label").configure(image=photo, compound="left", padx=4)
                w["photo"] = photo

        def _on_result(idx: int, result: dict) -> None:
            if not win.winfo_exists():
                return
            item_results[idx] = result
            _update_card(idx)
            if selected_idx.get("value") == idx:
                _render_detail(idx)

        def _update_card(idx: int) -> None:
            if idx not in item_results or idx not in card_widgets:
                return
            result = item_results[idx]
            local_item = current_items[idx]
            item_data = (result.get("item") or {}) if isinstance(result, dict) else {}
            name = str(item_data.get("Name") or local_item.get("name", "") or "-")
            w = card_widgets[idx]
            w["name_label"].configure(text=name)
            _set_card_color(w["name_label"], int(item_data.get("Quality") or 0))

        def _set_card_color(label: ctk.CTkLabel, quality: int) -> None:
            if quality >= 5:
                label.configure(text_color="#F28C28")
            elif quality >= 4:
                label.configure(text_color="#7B2CBF")
            else:
                label.configure(text_color=C["text_primary"])

        def _make_placeholder_icon(quality: int) -> ctk.CTkImage:
            """Create a small colored square as fallback icon based on quality."""
            color_map = {5: "#F28C28", 4: "#7B2CBF", 3: "#3B82F6", 2: "#6B7280", 1: "#9CA3AF"}
            hex_color = color_map.get(quality, "#6B7280")
            pil_image = Image.new("RGBA", (16, 16), hex_color)
            return ctk.CTkImage(pil_image, size=(16, 16))

        def _apply_fallback_icon(idx: int, quality: int, gen: int) -> None:
            """Apply a quality-colored placeholder icon when real icon unavailable."""
            if gen != _next_icon_gen[0] or not win.winfo_exists():
                return
            w = card_widgets.get(idx)
            if w is not None and w.get("photo") is None:
                photo = _make_placeholder_icon(quality)
                w.get("name_label").configure(image=photo, compound="left", padx=4)
                w["photo"] = photo

        def _local_detail_text(local_item: dict) -> str:
            parts = [f"装备名：{local_item.get('name', '-')}"]
            slot = local_item.get("slot_name") or ""
            if slot:
                parts.append(f"部位：{slot}")
            lv = local_item.get("item_level") or ""
            if lv:
                parts.append(f"品级：{lv}")
            eqs = local_item.get("equip_score_text") or ""
            if eqs:
                parts.append(f"装分：{eqs}")
            attr = local_item.get("attr_summary") or ""
            if attr:
                parts.extend(["", "属性：", str(attr)])
            attr_lines = local_item.get("attr_lines") or []
            if attr_lines and not attr:
                parts.extend(["", "属性：", "\n".join(str(x) for x in attr_lines)])
            enchant = local_item.get("enchant_summary") or ""
            if enchant:
                parts.extend(["", "附魔：", str(enchant)])
            return "\n".join(parts)

        # JX3BOX color names → hex
        _JX3BOX_COLOR_MAP = {
            "white": C["text_primary"],
            "orange": "#F28C28",
            "green": "#22C55E",
            "blue": "#3B82F6",
            "yellow": "#EAB308",
            "red": "#EF4444",
            "purple": "#7B2CBF",
            "gray": "#6B7280",
        }
        _tags_ready: list[bool] = [False]

        def _render_detail(idx: int) -> None:
            if idx < 0 or idx >= len(current_items):
                return
            local_item = current_items[idx]
            result = item_results.get(idx)
            item_data = (result.get("item") or {}) if result else {}
            name = str(item_data.get("Name") or local_item.get("name", "") or "-")
            level = str(item_data.get("Level") or "-")
            quality = int(item_data.get("Quality") or 0)
            detail_name_var.set(f"{name}（{level}）")
            # Color name label by quality
            if quality >= 5:
                detail_name_label.configure(text_color="#F28C28")
            elif quality >= 4:
                detail_name_label.configure(text_color="#7B2CBF")
            else:
                detail_name_label.configure(text_color=C["text_primary"])
            detail_text.configure(state="normal")
            detail_text.delete("1.0", "end")

            # Access underlying tk.Text for tag support
            _tk = detail_text._textbox

            # Configure color tags once
            if not _tags_ready[0]:
                _tags_ready[0] = True
                for cn, ch in _JX3BOX_COLOR_MAP.items():
                    _tk.tag_configure(f"jx3_{cn}", foreground=ch)
                _tk.tag_configure("jx3_label", foreground=C["text_secondary"])
                _tk.tag_configure("jx3_value", foreground=C["text_primary"])

            def _ins(text: str, tag: str = "jx3_value") -> None:
                _tk.insert("end", text, tag)

            if result and result.get("error"):
                _ins("─ 本地数据 ──\n" + _local_detail_text(local_item), "jx3_value")
                detail_text.configure(state="disabled")
                return

            if not result:
                _ins("正在查询 JX3BOX...\n\n─ 本地数据 ──\n" + _local_detail_text(local_item), "jx3_value")
                detail_text.configure(state="disabled")
                # still launch query
                search_name = normalize_item_search_name(local_item.get("name"))
                if search_name:
                    threading.Thread(target=_query_jx3box, args=(idx, search_name), daemon=True).start()
                return

            # ── Build detail text with per-line color tags ──

            # Name / Level / Type
            _ins("名称：", "jx3_label")
            _ins(f"{name}\n")
            _ins("等级：", "jx3_label")
            _ins(f"{level}\n")
            type_label = str(item_data.get("TypeLabel") or "-")
            _ins("类型：", "jx3_label")
            _ins(f"{type_label}\n")

            # Attributes — one per line with JX3BOX color
            _ins("属性：\n", "jx3_label")
            seen_attrs: set[str] = set()
            for attr in item_data.get("attributes") or []:
                if not isinstance(attr, dict):
                    continue
                # Skip effects (handled separately in orange)
                if attr.get("type") == "atSkillEventHandler" or str(attr.get("color") or "").lower() == "orange":
                    continue
                raw_label = str(attr.get("label") or "").strip()
                if not raw_label:
                    continue
                # Skip 速度 (speed)
                clean = jx3box_plain_text(raw_label)
                if "速度" in clean or "速度" in raw_label:
                    continue
                # Normalize name + extract value
                short_name = normalize_jx3box_attr_name(raw_label)
                vm = re.search(r"(?:提高|\+)?\s*([+-]?\d+(?:\.\d+)?)", raw_label)
                value = vm.group(1) if vm else ""
                entry = f"{short_name} {value}" if value else short_name
                if entry in seen_attrs:
                    continue
                seen_attrs.add(entry)
                color = str(attr.get("color") or "white").lower()
                tag = f"jx3_{color}" if color in _JX3BOX_COLOR_MAP else "jx3_value"
                _ins(f"  {entry}\n", tag)

            # GetType
            get_type = item_data.get("GetType") or item_data.get("GetSource") or ""
            if get_type:
                _ins("\n获取方式：", "jx3_label")
                _ins(f"{get_type}\n")

            # Effects — orange
            effects = jx3box_item_effects_text(item_data)
            if effects:
                _ins("\n特殊效果：\n", "jx3_label")
                for line in effects.splitlines():
                    _ins(f"{line}\n", "jx3_orange")

            # Requires
            requires = item_data.get("Requires")
            if isinstance(requires, dict):
                req_items = [str(v) for v in requires.values() if str(v or "").strip()]
                if req_items:
                    _ins("需求：", "jx3_label")
                    _ins(f"{'；'.join(req_items)}\n")

            # Desc
            desc = jx3box_plain_text(item_data.get("Desc"))
            if desc:
                _ins("\n说明：\n", "jx3_label")
                _ins(f"{desc}\n")

            # Recommend
            recommend = item_data.get("Recommend") or item_data.get("recommend") or ""
            if recommend:
                _ins("推荐门派：", "jx3_label")
                _ins(f"{recommend}\n")

            detail_text.configure(state="disabled")
            if idx not in item_results:
                search_name = normalize_item_search_name(local_item.get("name"))
                if search_name:
                    threading.Thread(target=_query_jx3box, args=(idx, search_name), daemon=True).start()

        def _select_item(idx: int) -> None:
            selected_idx["value"] = idx
            for i, w in card_widgets.items():
                w["frame"].configure(border_color=C["primary"] if i == idx else C["border"],
                                     border_width=2 if i == idx else 1)
            _render_detail(idx)

        def _rebuild_list(items_src: list[dict]) -> None:
            nonlocal current_items, item_results, card_widgets, selected_idx
            _next_icon_gen[0] += 1  # invalidate in-flight icon fetches
            for w in card_widgets.values():
                try:
                    w["frame"].destroy()
                except Exception:
                    pass
            current_items = items_src
            item_results = {}
            card_widgets = {}
            selected_idx = {"value": None}
            detail_name_var.set("请在右侧选择装备")
            detail_name_label.configure(text_color=C["text_primary"])
            detail_text.configure(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.configure(state="disabled")
            _build_cards()
            if current_items:
                win.after(200, lambda: _select_item(0))

        def _build_cards() -> None:
            for idx, item in enumerate(current_items):
                card = ctk.CTkFrame(list_scroll, fg_color=C["entry_bg"], corner_radius=6,
                                    border_width=1, border_color=C["border"])
                card.pack(fill="x", padx=4, pady=3)

                display_name = item.get("name") or item.get("item_name") or "-"
                name_label = ctk.CTkLabel(card, text=display_name,
                                          font=("Microsoft YaHei UI", 12, "bold"),
                                          text_color=C["text_primary"], anchor="w")
                name_label.pack(fill="x", padx=8, pady=8)

                card_widgets[idx] = {"frame": card, "name_label": name_label, "photo": None}

                for t in (card, name_label):
                    t.bind("<Button-1>", lambda e, i=idx: _select_item(i))

                # Implement name comparison before triggering thread query
                search_name = normalize_item_search_name(item.get("name"))
                if search_name:
                    # Look up in cache: if name matches, load from cache directly and skip HTTP thread
                    from jx3_click_monitor_gui import load_jx3box_cache
                    cache = load_jx3box_cache()

                    cache_key = f"name:{search_name}"
                    cached_data = cache.get(cache_key)
                    if isinstance(cached_data, dict) and not cached_data.get("error"):
                        item_data = cached_data.get("item") or {}
                        if item_data.get("Name") == search_name:
                            # Preload cache result immediately without starting query thread
                            item_results[idx] = cached_data
                            _update_card(idx)

                            # Preload icon if cached in _EQUIP_ICON_CACHE or disk
                            icon_id = item_data.get("IconID")
                            quality = int(item_data.get("Quality") or 0)
                            if icon_id:
                                gen = _next_icon_gen[0]
                                threading.Thread(
                                    target=_fetch_icon, args=(idx, str(icon_id), gen, quality), daemon=True
                                ).start()
                            elif quality > 0:
                                gen = _next_icon_gen[0]
                                win.after(0, lambda: _apply_fallback_icon(idx, quality, gen))
                            continue

                    threading.Thread(target=_query_jx3box, args=(idx, search_name), daemon=True).start()

        # ── Suit switch handler ──
        def _on_suit_changed(selected: str) -> None:
            suit_idx = int(selected)
            new_items = _normalize_items(suit_items_dict.get(suit_idx, []))
            if new_items:
                _rebuild_list(new_items)
                scores = rec.get("scores") or []
                if 0 <= suit_idx - 1 < len(scores):
                    header_label.configure(
                        text=f"{rec.get('server') or ''} · {rec.get('name') or ''}  |  装分 {scores[suit_idx - 1]}")

        if len(suit_keys) > 1:
            suit_selector.configure(command=_on_suit_changed)

        # ── Build initial cards ──
        _build_cards()
        if current_items:
            win.after(300, lambda: _select_item(0))

    def delete_growth_selected(self) -> None:
        selection = self.growth_role_tree.get_selection() if hasattr(self, "growth_role_tree") else []
        if not selection:
            messagebox.showinfo("提示", "请先选择一个角色")
            return
        for iid in selection:
            try:
                rec = self.growth_filtered_record_by_index(int(iid))
                self.hidden_growth_ownerkeys.add(self.growth_ownerkey(rec))
            except Exception:
                pass
        self.refresh_growth_role_list()
        self.save_config()

    def growth_filtered_record_by_index(self, idx: int) -> dict:
        for orig_idx, rec in self.growth_filtered_records():
            if orig_idx == idx:
                return rec
        if 0 <= idx < len(self.growth_records):
            return self.growth_records[idx]
        raise IndexError(idx)

    def drain_queue(self) -> None:
        """从后台线程消费 UI 消息队列（基于 Event 通信的变速轮询）。

        - 空闲时进入 300ms 长间隔等待。
        - 发生写入/队列推送时会立即唤醒，减少延迟，降低 CPU 空转。
        """
        # Reset event first
        self.queue_event.clear()

        count = 0
        try:
            while count < _MAX_PER_DRAIN:
                msg, data = self.queue.get_nowait()
                self._dispatch_msg(msg, data)
                count += 1
        except queue.Empty:
            pass

        # Dynamic polling frequency: if we have more messages or the queue event was set, poll fast (50ms), else wait 300ms
        if count > 0 or self.queue_event.is_set():
            interval = _POLL_FAST_MS
        else:
            interval = _POLL_IDLE_MS

        self.after(interval, self.drain_queue)

    def _dispatch_msg(self, msg: str, data: object) -> None:
        """集中处理所有队列消息类型（主线程安全）。"""
        try:
            if msg == "refresh_income":
                self.refresh_income_page()
            elif msg in ("log", "status"):
                self.status_var.set(str(data))
            elif msg == "progress":
                summary = data if isinstance(data, dict) else {}
                if summary.get("is_recording_tick"):
                    self.status_var.set("监控中 · 正在录制中（结算时自动汇总）")
                else:
                    self.status_var.set(
                        f"监控中 · 新增 {summary.get('last_poll_added', 0)} 条 · "
                        f"总计 {summary.get('total_events', 0)} 条"
                    )
            elif msg == "recording_reset":
                self.worker = None
                if not self.new_report:
                    self.set_new_state("idle")
            elif msg == "writeback_waiting":
                payload = data if isinstance(data, dict) else {}
                attempt = payload.get("attempt", 0)
                self.writeback_wait_var.set(
                    f"第 {attempt} 次读取：还没有读到本次聊天记录。"
                    "请确认已经小退/退出当前角色。"
                )
                self.status_var.set(
                    f"等待聊天数据库写盘中 · 第 {attempt} 次读取仍为空"
                )
            elif msg == "settlement_ready":
                payload = data if isinstance(data, dict) else {}
                report = payload.get("report") or {}
                session_text = payload.get("session_dir")
                if session_text:
                    self.session_dir = Path(session_text)
                self.new_report = report
                self.stats_text.set(self.format_settlement_summary(report))
                self.set_new_state("ready")
                self.status_var.set("结算已就绪 · 点击『生成结算』入账")
                self.open_settlement_confirm_dialog()
            elif msg == "settlement":
                self.new_report = data if isinstance(data, dict) else None
            elif msg == "error":
                # 后台线程发来的错误通知（通过 handle_thread_error 装饰器）
                payload = data if isinstance(data, dict) else {}
                title = payload.get("title", "后台错误")
                message = payload.get("message", "未知错误")
                logger.error("后台线程错误 [%s]: %s", title, message)
                messagebox.showerror(title, message)
            elif msg == "message_info":
                title, msg_text = data if isinstance(data, tuple) else ("提示", str(data))
                messagebox.showinfo(title, msg_text)
            elif msg == "message_error":
                title, msg_text = data if isinstance(data, tuple) else ("错误", str(data))
                messagebox.showerror(title, msg_text)
            elif msg == "growth_data":
                # GrowthService 后台加载完成
                records = data if isinstance(data, list) else []
                self.growth_records = records
                self.refresh_growth_page()
            else:
                logger.debug("drain_queue: 未知消息类型 %r", msg)
        except Exception:
            logger.exception("_dispatch_msg 处理消息 %r 时发生异常", msg)


def main() -> None:
    from src.logger import setup_logger
    from pathlib import Path
    
    # Configure global logger (Rolling file handler + sys.excepthook)
    log_dir = Path("logs")
    setup_logger(name="jx3_monitor", log_dir=log_dir)
    
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()