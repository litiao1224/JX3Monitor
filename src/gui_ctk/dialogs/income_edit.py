# -*- coding: utf-8 -*-
"""Income record edit dialog for JX3 Click Monitor."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import messagebox

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

import jx3_click_monitor as core
from src.config import INCOME_MEMORY_PATH

from src.gui_ctk.dialogs.shared import C, F, position_dialog

logger = logging.getLogger("jx3_monitor.dialogs.income_edit")


class IncomeEditDialog(ctk.CTkToplevel):
    """Edit a single income record."""

    def __init__(self, parent: ctk.CTk, app: App, record: dict, record_idx: int) -> None:
        super().__init__(parent)
        self.app = app
        self.record = dict(record)
        self.record_idx = record_idx

        self.title("编辑收支记录")
        self.configure(fg_color=C["background"])
        position_dialog(self, parent, 740, 550, 660, 500)
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
        self.income_var = ctk.StringVar(value=self._fmt_gold(income_gold))
        self.expense_var = ctk.StringVar(value=self._fmt_gold(expense_gold))
        self.net_var = ctk.StringVar(value=self._fmt_gold(net_gold))
        self.note_var = ctk.StringVar(value=str(record.get("note") or ""))
        self.black_role_var = ctk.StringVar(value=str(record.get("black_role") or ""))
        self.add_income_amount_var = ctk.StringVar(value="")
        self.add_income_reason_var = ctk.StringVar(value="")
        self.add_expense_amount_var = ctk.StringVar(value="")
        self.add_expense_reason_var = ctk.StringVar(value="")

        self._build_ui()

    def _fmt_gold(self, value: object) -> str:
        try:
            amount = float(value or 0)
        except Exception:
            amount = 0
        return f"{int(amount)}金" if amount.is_integer() else f"{amount:.2f}金"

    def _build_ui(self) -> None:
        ctk.CTkLabel(self, text="编辑收支记录", font=F["title"], text_color=C["text_primary"]).pack(anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(self, text="修改后点击保存，取消则不保留更改。", font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=18, pady=(0, 12))

        metrics = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        metrics.pack(fill="x", padx=18, pady=(0, 12))
        top_row = ctk.CTkFrame(metrics, fg_color=C["card"], corner_radius=0)
        top_row.pack(fill="x", padx=14, pady=(12, 8))
        for label, var in [("收入", self.income_var), ("支出", self.expense_var), ("净收入", self.net_var)]:
            box = ctk.CTkFrame(top_row, fg_color=C["entry_bg"], corner_radius=8, border_width=1, border_color=C["border"])
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(box, text=label, font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=10, pady=(7, 0))
            ctk.CTkLabel(box, textvariable=var, font=F["card_title"], text_color=C["text_primary"]).pack(anchor="w", padx=10, pady=(0, 7))

        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10, border_width=1, border_color=C["border"])
        card.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        fields = ctk.CTkFrame(card, fg_color=C["card"], corner_radius=0)
        fields.pack(fill="x", padx=14, pady=(12, 6))
        for label, var, width in [
            ("时间", self.recorded_at_var, 130), ("区服", self.server_var, 80),
            ("副本名称", self.instance_var, 130), ("角色", self.role_var, 90),
            ("黑本角色", self.black_role_var, 80),
        ]:
            col = ctk.CTkFrame(fields, fg_color=C["card"], corner_radius=0)
            col.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(col, text=label, font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
            ctk.CTkEntry(col, textvariable=var, width=width, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(anchor="w")

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

        row4 = ctk.CTkFrame(card, fg_color=C["card"], corner_radius=0)
        row4.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(row4, text="备注", font=F["small"], text_color=C["text_secondary"]).pack(anchor="w")
        ctk.CTkEntry(row4, textvariable=self.note_var, fg_color=C["entry_bg"], text_color=C["text_primary"], border_color=C["border"], font=F["body"]).pack(fill="x")

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
        self.income_var.set(self._fmt_gold(total_income))
        self.expense_var.set(self._fmt_gold(total_expense))
        net = round(total_income - total_expense, 2)
        self.net_var.set(self._fmt_gold(net))

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
                notes.append("添加收入：" + "；".join(f"{self._fmt_gold(item.get('amount'))}：{item.get('reason')}" for item in self.added_income_items))
            if self.added_expense_items:
                notes.append("添加支出：" + "；".join(f"{self._fmt_gold(item.get('amount'))}：{item.get('reason')}" for item in self.added_expense_items))
            note_text = self.note_var.get().strip()
            if notes:
                note_text = ("；" + "；".join(notes)) if note_text else "；".join(notes)
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

            def _async_save() -> None:
                try:
                    seq = self.record.get("seq")
                    if seq is not None:
                        core.update_income_memory_record(INCOME_MEMORY_PATH, int(seq), patch)
                    else:
                        if 0 <= self.record_idx < len(self.app.income_records):
                            self.app.income_records[self.record_idx].update(patch)
                            INCOME_MEMORY_PATH.write_text(
                                json.dumps({"records": self.app.income_records}, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                    self.app.queue.put(("refresh_income", None))
                except Exception as e:
                    self.app.queue.put(("error", {"title": "保存失败", "message": str(e)}))

            threading.Thread(target=_async_save, daemon=True).start()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def close(self) -> None:
        self.destroy()
