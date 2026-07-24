# -*- coding: utf-8 -*-
"""JX3 Click Monitor - GUI widget components.

Reusable Tkinter widgets: calendar picker, tree sorting helpers.
"""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Callable


class CalendarDropdown(tk.Toplevel):
    """Inline calendar popup that appears near a widget."""

    def __init__(self, master: tk.Misc, var: tk.StringVar, on_confirm: Callable[[], None] | None = None):
        super().__init__(master)
        self.var = var
        self.on_confirm = on_confirm
        self.title("")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel() if hasattr(master, 'winfo_toplevel') else master)
        self.overrideredirect(True)
        try:
            base = datetime.strptime(var.get(), "%Y-%m-%d %H:%M:%S")
        except Exception:
            base = datetime.now()
        self._year = base.year
        self._month = base.month
        self._day = base.day
        self._hour = tk.IntVar(value=base.hour)
        self._minute = tk.IntVar(value=base.minute)
        self._second = tk.IntVar(value=base.second)
        self._selected_day = base.day
        self._day_buttons: dict[int, tk.Button] = {}
        outer = ttk.Frame(self, relief="solid", borderwidth=1)
        outer.pack(fill=tk.BOTH, expand=True)
        nav = ttk.Frame(outer)
        nav.pack(fill=tk.X, padx=6, pady=(6, 2))
        ttk.Button(nav, text="◀", width=3, command=self._prev_month).pack(side=tk.LEFT)
        self._month_label = ttk.Label(nav, anchor="center", font=("", 11, "bold"))
        self._month_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(nav, text="▶", width=3, command=self._next_month).pack(side=tk.LEFT)
        header = ttk.Frame(outer)
        header.pack(fill=tk.X, padx=6)
        for wd in ["一", "二", "三", "四", "五", "六", "日"]:
            ttk.Label(header, text=wd, width=4, anchor="center", foreground="#888").pack(side=tk.LEFT)
        self._grid_frame = ttk.Frame(outer)
        self._grid_frame.pack(fill=tk.BOTH, padx=6, pady=2)
        time_frame = ttk.Frame(outer)
        time_frame.pack(fill=tk.X, padx=6, pady=(2, 2))
        for label, var_, lo, hi in [("时", self._hour, 0, 23), ("分", self._minute, 0, 59), ("秒", self._second, 0, 59)]:
            ttk.Label(time_frame, text=label).pack(side=tk.LEFT, padx=(6, 0))
            tk.Spinbox(time_frame, from_=lo, to=hi, textvariable=var_, width=4, wrap=True, justify="center").pack(side=tk.LEFT, padx=2)
        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill=tk.X, padx=6, pady=(2, 6))
        ttk.Button(btn_frame, text="今天", command=self._today).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="确定", command=self._confirm).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)
        self._render_days()
        self._near_widget = master
        self.after(50, self._position_near)
        self.after(100, lambda: self.focus_force())
        self.bind("<FocusOut>", self._on_focus_out)

    def _position_near(self, widget: tk.Misc = None) -> None:
        widget = widget or getattr(self, "_near_widget", None)
        if not widget:
            return
        try:
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            wh = widget.winfo_height()
        except Exception:
            return
        self.update_idletasks()
        sw = self.winfo_reqwidth()
        sh = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = wx
        y = wy + wh + 2
        if x + sw > screen_w:
            x = screen_w - sw - 10
        if y + sh > screen_h:
            y = wy - sh - 2
        if x < 0:
            x = 10
        if y < 0:
            y = 10
        self.wm_geometry(f"+{x}+{y}")

    def _on_focus_out(self, event=None) -> None:
        try:
            focused = self.focus_get()
            if focused is not None and str(focused).startswith(str(self)):
                return
        except Exception:
            pass

    def _render_days(self) -> None:
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._day_buttons.clear()
        self._month_label.configure(text=f"{self._year}年{self._month:02d}月")
        cal = calendar.monthcalendar(self._year, self._month)
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(self._grid_frame, text="", width=4).grid(row=r, column=c)
                else:
                    is_selected = (day == self._selected_day and self._year == datetime.now().year and self._month == datetime.now().month)
                    bg = "#4a90d9" if day == self._selected_day else ("#f0f0f0" if (r * 7 + c) % 7 < 5 else "#fafafa")
                    fg = "white" if day == self._selected_day else "black"
                    b = tk.Button(self._grid_frame, text=str(day), width=4, relief="flat",
                                  bg=bg, fg=fg, activebackground="#6ab0ff", activeforeground="white",
                                  command=lambda d=day: self._pick_day(d))
                    b.grid(row=r, column=c, padx=1, pady=1)
                    self._day_buttons[day] = b

    def _pick_day(self, day: int) -> None:
        self._selected_day = day
        self._render_days()

    def _prev_month(self) -> None:
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self._selected_day = min(self._selected_day, calendar.monthrange(self._year, self._month)[1])
        self._render_days()

    def _next_month(self) -> None:
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self._selected_day = min(self._selected_day, calendar.monthrange(self._year, self._month)[1])
        self._render_days()

    def _today(self) -> None:
        now = datetime.now()
        self._year, self._month, self._selected_day = now.year, now.month, now.day
        self._hour.set(now.hour)
        self._minute.set(now.minute)
        self._second.set(now.second)
        self._render_days()

    def _confirm(self) -> None:
        try:
            dt = datetime(self._year, self._month, self._selected_day,
                          int(self._hour.get()), int(self._minute.get()), int(self._second.get()))
        except ValueError as exc:
            messagebox.showerror("时间无效", str(exc), parent=self)
            return
        self.var.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
        if self.on_confirm:
            self.on_confirm()
        self.destroy()


def attach_tree_sorting(tree: ttk.Treeview, columns: tuple[str, ...]) -> Callable:
    """Add click-to-sort behavior to a Treeview's column headings."""
    import re
    sort_state: dict[str, bool] = {}

    def value_key(value: str) -> Any:
        text = str(value or "").strip()
        try:
            return (0, float(text.replace(",", "")))
        except ValueError:
            return (1, text)

    def sort_by(col: str) -> None:
        descending = not sort_state.get(col, False)
        sort_state[col] = descending
        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        rows.sort(key=lambda x: value_key(x[0]), reverse=descending)
        for idx, (_value, iid) in enumerate(rows):
            tree.move(iid, "", idx)
        for c in columns:
            label = tree.heading(c).get("text", c)
            label = re.sub(r" [▲▼]", "", label)
            if c == col:
                label += " ▼" if descending else " ▲"
            tree.heading(c, text=label)

    for col in columns:
        tree.heading(col, command=lambda c=col: sort_by(c))

    return sort_by
