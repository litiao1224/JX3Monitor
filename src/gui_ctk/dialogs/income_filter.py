# -*- coding: utf-8 -*-
"""Income filter, column selection, and analysis dialogs."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

import jx3_click_monitor as core
from src.gui_ctk.dialogs.shared import C, F, position_dialog
from src.gui_ctk.widgets import CTkTable

logger = logging.getLogger("jx3_monitor.dialogs.income")


# ── IncomeFilterWindow ─────────────────────────────────────────


class IncomeFilterWindow(ctk.CTkToplevel):
    """Filter income records by date range, role, server, note."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("筛选收支统计")
        position_dialog(self, app, 720, 460, 620, 380)
        self.transient(parent or app)
        self.grab_set()

        filter_data = getattr(app, "income_filter", {}) or {}

        frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8,
                             border_width=1, border_color=C["border_light"])
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        now = datetime.now()
        start_picker = self._add_time_picker(frame, 0, "启用开始时间", "date_from", filter_data, now)
        end_picker = self._add_time_picker(frame, 1, "启用结束时间", "date_to", filter_data, now)

        fields = [
            ("role", "角色", "包含匹配"),
            ("server", "区服", "包含匹配"),
            ("note", "黑本角色", "包含匹配"),
        ]
        self.var_entries: dict[str, ctk.StringVar] = {}
        for i, (key, label, hint) in enumerate(fields, start=2):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.grid(row=i, column=0, columnspan=3, sticky="ew", pady=5, padx=14)
            ctk.CTkLabel(row, text=label, text_color=C["text_secondary"],
                         font=F["body"], width=80).pack(side="left")
            v = ctk.StringVar(value=(filter_data.get(key) or ""))
            self.var_entries[key] = v
            ctk.CTkEntry(row, textvariable=v, font=F["body"],
                         fg_color=C["entry_bg"], border_color=C["entry_border"],
                         border_width=1).pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(row, text=hint, text_color=C["text_muted"],
                         font=F["small"]).pack(side="left", padx=4)

        frame.grid_columnconfigure(1, weight=1)

        def picker_value(p: dict) -> str:
            if not p["enabled"].get():
                return ""
            try:
                dt = datetime(int(p["year"].get()), int(p["month"].get()),
                              int(p["day"].get()), int(p["hour"].get()), int(p["minute"].get()))
            except Exception:
                dt = now
            return dt.strftime("%Y-%m-%d %H:%M")

        def apply_filter() -> None:
            app.income_filter = {k: v.get().strip() for k, v in self.var_entries.items()}
            app.income_filter["date_from"] = picker_value(start_picker)
            app.income_filter["date_to"] = picker_value(end_picker)
            app.refresh_income_page()
            self.destroy()

        def clear_filter() -> None:
            app.income_filter = {"date_from": "", "date_to": "", "role": "", "server": "", "note": ""}
            app.refresh_income_page()
            self.destroy()

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0), padx=14)
        ctk.CTkButton(btns, text="清空筛选", command=clear_filter, font=F["button"],
                      fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6,
                      border_width=0).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="应用筛选", command=apply_filter, font=F["button"],
                      fg_color=C["primary"], text_color=C["text_on_primary"],
                      hover_color=C["primary_hover"], corner_radius=6,
                      border_width=0).pack(side="left", padx=4)

    def _add_time_picker(self, parent: ctk.CTkFrame, row: int, label: str,
                         key: str, filter_data: dict, now: datetime) -> dict:
        enabled = ctk.BooleanVar(value=bool((filter_data.get(key) or "").strip()))
        try:
            existing = (filter_data.get(key) or "").strip()
            if existing:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                            "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(existing, fmt)
                        break
                    except ValueError:
                        dt = now
            else:
                dt = now
        except Exception:
            dt = now

        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.grid(row=row, column=0, columnspan=3, sticky="w", pady=6, padx=14)
        ctk.CTkCheckBox(row_frame, text=label, variable=enabled, font=F["body"],
                        text_color=C["text_primary"],
                        fg_color=C["primary"], border_color=C["text_muted"],
                        hover_color=C["primary_hover"],
                        checkmark_color=C["text_on_primary"]
                        ).pack(side="left")

        picker_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        picker_frame.pack(side="left", padx=8)

        year_var = ctk.StringVar(value=f"{dt.year:04d}")
        month_var = ctk.StringVar(value=f"{dt.month:02d}")
        day_var = ctk.StringVar(value=f"{dt.day:02d}")

        years = [str(y) for y in range(2020, 2036)]
        months = [f"{m:02d}" for m in range(1, 13)]
        days = [f"{d:02d}" for d in range(1, 32)]

        dropdown_kw = dict(font=F["body"], fg_color=C["entry_bg"],
                           text_color=C["text_primary"], button_color=C["toolbar_bg"],
                           button_hover_color=C["toolbar_hover"],
                           dropdown_fg_color=C["card"], dropdown_text_color=C["text_primary"],
                           dropdown_hover_color=C["table_selected"])

        ctk.CTkOptionMenu(picker_frame, variable=year_var, values=years, width=80, **dropdown_kw).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(picker_frame, text="年", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(0, 4))
        ctk.CTkOptionMenu(picker_frame, variable=month_var, values=months, width=65, **dropdown_kw).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(picker_frame, text="月", font=F["small"], text_color=C["text_muted"]).pack(side="left", padx=(0, 4))
        ctk.CTkOptionMenu(picker_frame, variable=day_var, values=days, width=65, **dropdown_kw).pack(side="left", padx=(0, 2))
        ctk.CTkLabel(picker_frame, text="日", font=F["small"], text_color=C["text_muted"]).pack(side="left")

        return {"enabled": enabled, "year": year_var, "month": month_var,
                "day": day_var, "hour": ctk.StringVar(value="0"), "minute": ctk.StringVar(value="0")}


# ── IncomeColumnsWindow ────────────────────────────────────────


class IncomeColumnsWindow(ctk.CTkToplevel):
    """Select which columns to show/hide in the income table."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("选择显示列")
        position_dialog(self, app, 520, 500, 440, 420)
        self.transient(parent or app)
        self.grab_set()

        frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8,
                             border_width=1, border_color=C["border_light"])
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        presets = ctk.CTkFrame(frame, fg_color="transparent")
        presets.grid(row=0, column=0, sticky="ew", pady=(12, 4), padx=14)
        for text, columns in [
            ("默认视图", ["seq", "recorded_at", "server", "role", "income", "expense", "net", "note"]),
            ("结算视图", ["seq", "recorded_at", "server", "role", "instance", "income", "expense", "net", "session_time"]),
            ("完整视图", list(getattr(app, "income_columns_all", []))),
        ]:
            ctk.CTkButton(
                presets, text=text, command=lambda cols=columns: self._apply_preset(app, cols),
                font=F["small"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                hover_color=C["toolbar_hover"], corner_radius=6, border_width=0,
            ).pack(side="left", padx=(0, 6))

        selectable = ["seq", "recorded_at", "role", "server", "instance", "income",
                      "expense", "net", "note", "session_time"]
        for i, col in enumerate(selectable):
            heading = app.income_headings.get(col, col)
            var = getattr(app, "income_column_vars", {}).get(col)
            ctk.CTkCheckBox(
                frame, text=heading, variable=var, font=F["body"],
                text_color=C["text_primary"],
                fg_color=C["primary"], border_color=C["border"],
                hover_color=C["primary_hover"],
                command=lambda: self._apply_columns(app),
            ).grid(row=i + 1, column=0, sticky="w", pady=4, padx=14)

        ctk.CTkLabel(frame, text="勾选显示，不勾选隐藏；也可以一键切换预设。",
                     text_color=C["text_muted"], font=F["small"]
                     ).grid(row=len(selectable) + 1, column=0, sticky="w", pady=(12, 0), padx=14)
        ctk.CTkButton(frame, text="关闭", command=self.destroy, font=F["button"],
                      fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6,
                      border_width=0).grid(row=len(selectable) + 2, column=0, sticky="e",
                                           pady=(12, 0), padx=14)

    def _apply_columns(self, app: App) -> None:
        if hasattr(app, "apply_income_visible_columns"):
            app.apply_income_visible_columns(persist=True)

    def _apply_preset(self, app: App, columns: list[str]) -> None:
        visible = set(columns)
        for key, var in getattr(app, "income_column_vars", {}).items():
            var.set(key in visible)
        self._apply_columns(app)


# ── IncomeAnalysisWindow ───────────────────────────────────────


class IncomeAnalysisWindow(ctk.CTkToplevel):
    """Income analysis with trend chart and expense breakdown."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("收支统计分析")
        position_dialog(self, app, 1180, 760, 900, 600)
        self.transient(parent or app)
        self.grab_set()

        app.refresh_income_page()
        records = list(getattr(app, "income_records", []) or
                       core.search_income_memory(
                           getattr(app, "INCOME_MEMORY_PATH",
                                   Path("income_memory.json")), ""))

        # ── Filters ──
        toolbar = ctk.CTkFrame(self, fg_color=C["toolbar_bg"], corner_radius=0)
        toolbar.pack(fill="x", padx=0, pady=0)

        accounts = ["全部"] + sorted({str(r.get("account") or "") for r in records if r.get("account")})
        roles = ["全部"] + sorted({str(r.get("role") or "") for r in records if r.get("role")})
        instances = ["全部"] + sorted({str(r.get("instance") or "") for r in records if r.get("instance")})

        self.account_var = ctk.StringVar(value="全部")
        self.role_var = ctk.StringVar(value="全部")
        self.instance_var = ctk.StringVar(value="全部")

        for item in [
            ("账号", accounts, self.account_var),
            ("角色", roles, self.role_var),
            ("副本", instances, self.instance_var),
        ]:
            lbl, values, var = item
            row = ctk.CTkFrame(toolbar, fg_color="transparent")
            row.pack(side="left", padx=6, pady=8)
            ctk.CTkLabel(row, text=lbl, text_color=C["text_secondary"],
                         font=F["body"]).pack(side="left", padx=(0, 4))
            ctk.CTkComboBox(row, variable=var, values=values,
                            font=F["body"], width=160,
                            fg_color=C["entry_bg"], border_color=C["entry_border"],
                            button_color=C["toolbar_bg"], button_hover_color=C["toolbar_hover"],
                            dropdown_fg_color=C["card"], dropdown_hover_color=C["table_hover"],
                            state="readonly").pack(side="left")

        ctk.CTkButton(toolbar, text="更新图表", command=self._draw,
                      font=F["button"],
                      fg_color=C["primary"], text_color=C["text_on_primary"],
                      hover_color=C["primary_hover"], corner_radius=6,
                      border_width=0).pack(side="left", padx=12, pady=8)

        self.records = records

        # ── Two-pane layout ──
        panes = ctk.CTkFrame(self, fg_color="transparent")
        panes.pack(fill="both", expand=True, padx=8, pady=8)
        panes.grid_columnconfigure(0, weight=1)
        panes.grid_columnconfigure(1, weight=1)
        panes.grid_rowconfigure(0, weight=1)

        chart_card = ctk.CTkFrame(panes, fg_color=C["card"], corner_radius=10,
                                  border_width=1, border_color=C["border"])
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(chart_card, text="入账趋势", font=F["card_title"],
                     text_color=C["text_primary"]).pack(anchor="w", padx=14, pady=(10, 2))
        self._build_chart_tab(chart_card)

        expense_card = ctk.CTkFrame(panes, fg_color=C["card"], corner_radius=10,
                                    border_width=1, border_color=C["border"])
        expense_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        ctk.CTkLabel(expense_card, text="支出明细", font=F["card_title"],
                     text_color=C["text_primary"]).pack(anchor="w", padx=14, pady=(10, 2))
        self._build_expense_tab(expense_card)

        self._draw()

    def _build_chart_tab(self, parent: ctk.CTkFrame) -> None:
        metrics_frame = ctk.CTkFrame(parent, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=8, pady=(8, 4))
        self._metric_cards: dict[str, ctk.CTkLabel] = {}
        for label in ("今日收入", "本周收入", "月度收入", "赛季收入"):
            box = ctk.CTkFrame(metrics_frame, fg_color=C["card"], corner_radius=8,
                               border_width=1, border_color=C["border"])
            box.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkLabel(box, text=label, font=F["small"], text_color=C["text_muted"]
                         ).pack(anchor="w", padx=10, pady=(7, 0))
            val_label = ctk.CTkLabel(box, text="0 金", font=("Microsoft YaHei UI", 15, "bold"),
                                     text_color=C["text_primary"])
            val_label.pack(anchor="w", padx=10, pady=(0, 7))
            self._metric_cards[label] = val_label

        canvas_frame = ctk.CTkFrame(parent, fg_color=C["entry_bg"], corner_radius=6)
        canvas_frame.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = __import__("tkinter").Canvas(canvas_frame, bg=C["entry_bg"], highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        v_scroll = ctk.CTkScrollbar(canvas_frame, orientation="vertical",
                                    command=self.canvas.yview, height=0)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll = ctk.CTkScrollbar(canvas_frame, orientation="horizontal",
                                    command=self.canvas.xview, width=0)
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.summary_var = ctk.StringVar(value="")
        ctk.CTkLabel(parent, textvariable=self.summary_var, font=F["body"],
                     text_color=C["text_secondary"], justify="left"
                     ).pack(anchor="w", pady=(4, 8), padx=8)

    def _build_expense_tab(self, parent: ctk.CTkFrame) -> None:
        self.expense_text = ctk.CTkTextbox(parent, wrap="word", font=F["body"],
                                           fg_color=C["entry_bg"], text_color=C["text_primary"],
                                           border_width=1, border_color=C["entry_border"])
        self.expense_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _filtered_records(self) -> list[dict]:
        out = []
        for r in self.records:
            if self.account_var.get() != "全部" and r.get("account") != self.account_var.get():
                continue
            if self.role_var.get() != "全部" and r.get("role") != self.role_var.get():
                continue
            if self.instance_var.get() != "全部" and r.get("instance") != self.instance_var.get():
                continue
            out.append(r)
        return out

    def _draw(self) -> None:
        rows = self._filtered_records()
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")
        season_start_str = getattr(self.app, "season_start_var", ctk.StringVar(value="")).get().strip()
        season_end_str = getattr(self.app, "season_end_var", ctk.StringVar(value="")).get().strip()

        daily: dict[str, dict[str, float]] = {}
        expense_rows: list[dict] = []
        today_income = 0.0
        week_income = 0.0
        month_income = 0.0
        season_income = 0.0

        for r in rows:
            dt = self._parse_record_datetime(r)
            if not dt:
                continue
            day = dt.strftime("%Y-%m-%d")
            daily.setdefault(day, {"income": 0.0, "expense": 0.0})
            income_val = float(r.get("income_gold") or 0)
            expense_val = float(r.get("expense_gold") or 0)
            daily[day]["income"] += income_val
            daily[day]["expense"] += expense_val
            if day == today_key:
                today_income += income_val
            if day >= week_start:
                week_income += income_val
            if day.startswith(month_key):
                month_income += income_val
            if (not season_start_str or day >= season_start_str) and \
               (not season_end_str or day <= season_end_str):
                season_income += income_val
            for item in r.get("expense_items") or []:
                expense_rows.append({
                    "date": day,
                    "account": r.get("account"),
                    "role": r.get("role"),
                    "instance": r.get("instance"),
                    "item": item.get("item") or item.get("note") or "手动支出",
                    "amount": float(item.get("amount_gold") or 0),
                    "note": item.get("note") or " / ".join(
                        x for x in [item.get("buyer"), item.get("target")] if x),
                })

        self._update_metric_cards(today_income, week_income, month_income, season_income)
        self._draw_line_chart(daily)
        self._render_expenses(expense_rows)

        total_income = round(sum(v["income"] for v in daily.values()), 2)
        total_expense = round(sum(v["expense"] for v in daily.values()), 2)
        self.summary_var.set(
            f"筛选记录：{len(rows)} 条    收入合计：{total_income} 金    支出合计：{total_expense} 金    支出物品：{len(expense_rows)} 件")

    def _update_metric_cards(self, today: float, week: float, month: float, season: float) -> None:
        def fmt(v: float) -> str:
            return f"{int(v)} 金" if v.is_integer() else f"{v:.2f} 金"
        for label, val in [("今日收入", today), ("本周收入", week),
                           ("月度收入", month), ("赛季收入", season)]:
            if label in self._metric_cards:
                self._metric_cards[label].configure(text=fmt(val))

    def _parse_record_datetime(self, record: dict) -> datetime | None:
        for key in ("recorded_at", "session_end", "session_start"):
            value = str(record.get(key) or "").strip()
            if not value:
                continue
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    pass
        return None

    def _draw_line_chart(self, daily: dict[str, dict[str, float]]) -> None:
        self.canvas.delete("all")
        try:
            width = max(self.canvas.winfo_width(), 600)
            height = max(self.canvas.winfo_height(), 360)
        except Exception:
            width, height = 600, 360
        pad_l, pad_r, pad_t, pad_b = 65, 30, 40, 55
        days = sorted(daily.keys())

        if not days:
            self.canvas.create_text(width / 2, height / 2,
                                    text="暂无可分析收入记录", fill=C["text_muted"],
                                    font=("Microsoft YaHei UI", 14))
            return

        raw_max = max([daily[d]["income"] for d in days] +
                      [daily[d]["expense"] for d in days] + [10])

        import math
        exp = math.floor(math.log10(raw_max))
        frac = raw_max / (10 ** exp)
        if frac <= 1.25:
            nice_frac = 1.25
        elif frac <= 2.5:
            nice_frac = 2.5
        elif frac <= 5.0:
            nice_frac = 5.0
        else:
            nice_frac = 10.0
        max_y = nice_frac * (10 ** exp)

        plot_w = width - pad_l - pad_r
        plot_h = height - pad_t - pad_b

        grid_color = "#2d2d30"
        text_color = C["text_muted"]

        # Y-axis & horizontal grid lines
        for i in range(5):
            y = pad_t + plot_h - plot_h * i / 4
            val = max_y * i / 4
            if val >= 10000:
                val_text = f"{val / 10000:.1f}万金" if (val / 10000) % 1 != 0 else f"{int(val // 10000)}万金"
            else:
                val_text = f"{int(val)}"
            self.canvas.create_line(pad_l, y, pad_l + plot_w, y, fill=grid_color, dash=(3, 3))
            self.canvas.create_text(pad_l - 8, y, text=val_text, anchor="e", fill=text_color, font=("Microsoft YaHei UI", 9))

        def point(day: str, kind: str) -> tuple[float, float]:
            idx = days.index(day)
            x = pad_l + (plot_w * idx / max(len(days) - 1, 1))
            y = pad_t + plot_h - (daily[day][kind] / max_y) * plot_h
            return x, y

        # Legend header
        self.canvas.create_oval(pad_l + 10, 14, pad_l + 18, 22, fill="#6BBF7A", outline="")
        self.canvas.create_text(pad_l + 22, 18, text="每日收入", fill="#6BBF7A", anchor="w", font=("Microsoft YaHei UI", 10, "bold"))
        self.canvas.create_oval(pad_l + 110, 14, pad_l + 118, 22, fill="#E26D64", outline="")
        self.canvas.create_text(pad_l + 122, 18, text="每日支出", fill="#E26D64", anchor="w", font=("Microsoft YaHei UI", 10, "bold"))

        def catmull_rom(pts: list[tuple[float, float]], samples: int = 16) -> list[tuple[float, float]]:
            if len(pts) <= 2:
                return pts
            p = [pts[0]] + list(pts) + [pts[-1]]
            out: list[tuple[float, float]] = []
            for i_ in range(1, len(p) - 2):
                p0, p1, p2, p3 = p[i_ - 1], p[i_], p[i_ + 1], p[i_ + 2]
                for t_idx in range(samples):
                    t = t_idx / float(samples)
                    t2 = t * t
                    t3 = t2 * t
                    x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                    y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                    out.append((x, y))
            out.append(pts[-1])
            return out

        for kind, color in [("income", "#6BBF7A"), ("expense", "#E26D64")]:
            pts = [point(d, kind) for d in days]
            if len(pts) == 1:
                x, y = pts[0]
                self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="#1e1e1e", width=1.5)
            else:
                spline_pts = catmull_rom(pts)
                flat = [v for p in spline_pts for v in p]
                self.canvas.create_line(*flat, fill=color, width=2.5)
                for x, y in pts:
                    self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline="#1e1e1e", width=1.5)

        step = max(1, len(days) // 10)
        for i, day in enumerate(days):
            if i % step == 0 or i == len(days) - 1:
                x, _ = point(day, "income")
                self.canvas.create_text(x, height - 25, text=day[5:], anchor="n", fill=text_color, font=("Microsoft YaHei UI", 9))

        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _render_expenses(self, expense_rows: list[dict]) -> None:
        self.expense_text.configure(state="normal")
        self.expense_text.delete("0.0", "end")
        for e in sorted(expense_rows, key=lambda x: x["amount"], reverse=True):
            self.expense_text.insert("end",
                f"[{e['date']}] {e['account']} · {e['role']} @ {e['instance']}\n"
                f"  {e['item']}: {e['amount']} 金"
                f"{'  (' + e['note'] + ')' if e.get('note') else ''}\n\n")
        self.expense_text.configure(state="disabled")
