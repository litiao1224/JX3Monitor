# -*- coding: utf-8 -*-
"""Config datetime picker and chat HTML importer dialogs."""
from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import filedialog, messagebox

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

import jx3_click_monitor as core
from src.gui_ctk.dialogs.shared import C, F, position_dialog
from src.gui_ctk.widgets import CTkTable

logger = logging.getLogger("jx3_monitor.dialogs.config")


# ── ConfigDatetimePicker ───────────────────────────────────────


class ConfigDatetimePicker(ctk.CTkToplevel):
    """Simple date/time picker for config settings (season start/end)."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None,
                 config_key: str = "season_start") -> None:
        super().__init__(parent or app)
        self.app = app
        self.config_key = config_key
        self.title("选择日期时间")
        position_dialog(self, app, 320, 340, 300, 320)
        self.transient(parent or app)
        self.grab_set()

        var = app.season_start_var if config_key == "season_start" else app.season_end_var
        current_value = var.get()

        default_dt = datetime.now()
        if current_value:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
                try:
                    default_dt = datetime.strptime(current_value, fmt)
                    break
                except ValueError:
                    pass

        frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(frame, text="选择日期时间：", font=F["card_title"],
                     text_color=C["text_primary"]).pack(pady=(12, 8))

        self.year_var = ctk.IntVar(value=default_dt.year)
        self.month_var = ctk.IntVar(value=default_dt.month)
        self.day_var = ctk.IntVar(value=default_dt.day)
        self.hour_var = ctk.IntVar(value=default_dt.hour)
        self.minute_var = ctk.IntVar(value=default_dt.minute)

        fields = [
            ("年", self.year_var, list(range(2020, 2036))),
            ("月", self.month_var, list(range(1, 13))),
            ("日", self.day_var, list(range(1, 32))),
            ("时", self.hour_var, list(range(0, 24))),
            ("分", self.minute_var, list(range(0, 60))),
        ]
        for label, var_, values in fields:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(pady=3)
            ctk.CTkLabel(row, text=label, text_color=C["text_secondary"],
                         font=F["body"], width=30).pack(side="left")
            ctk.CTkComboBox(row, variable=var_, values=[str(v) for v in values],
                            font=F["body"], width=80,
                            fg_color=C["entry_bg"], border_color=C["entry_border"],
                            button_color=C["toolbar_bg"], button_hover_color=C["toolbar_hover"],
                            dropdown_fg_color=C["card"], dropdown_hover_color=C["table_hover"],
                            state="readonly").pack(side="left", padx=4)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(12, 8))
        ctk.CTkButton(btn_frame, text="确定", command=self._confirm, font=F["button"],
                      fg_color=C["primary"], text_color=C["text_on_primary"],
                      hover_color=C["primary_hover"], corner_radius=6,
                      border_width=0).pack(side="right", padx=4)
        ctk.CTkButton(btn_frame, text="取消", command=self.destroy, font=F["button"],
                      fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6,
                      border_width=0).pack(side="right", padx=4)

    def _confirm(self) -> None:
        try:
            dt = datetime(int(self.year_var.get()), int(self.month_var.get()),
                          int(self.day_var.get()), int(self.hour_var.get()),
                          int(self.minute_var.get()))
        except ValueError as exc:
            messagebox.showerror("时间无效", str(exc), parent=self)
            return

        fmt = "%Y-%m-%d %H:%M:%S"
        var = self.app.season_start_var if self.config_key == "season_start" else self.app.season_end_var
        var.set(dt.strftime(fmt))
        self.destroy()
