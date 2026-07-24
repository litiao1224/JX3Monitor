# -*- coding: utf-8 -*-
"""Account/role filter dialog for the Growth page."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

from src.gui_ctk.dialogs.shared import C, F, position_dialog
from src.gui_ctk.widgets import CTkTable
from src.gui_ctk.themes import CORNER_RADIUS_SM


class GrowthFilterDialog(ctk.CTkToplevel):
    """Select which accounts and roles to display on the Growth page."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("筛选账号和角色")
        position_dialog(self, app, 680, 560, 500, 400)
        self.transient(parent or app)
        self.grab_set()

        self._selected: set[str] = set(self.app.selected_growth_ownerkeys)
        self._all_entries: list[dict] = []
        self._filtered_entries: list[dict] = []

        search_frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8)
        search_frame.pack(fill="x", padx=10, pady=(10, 6))

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(
            search_frame, textvariable=self.search_var,
            placeholder_text="搜索账号、区服或角色名...",
            font=F["body"], height=32, corner_radius=CORNER_RADIUS_SM,
            fg_color=C["entry_bg"], text_color=C["text_primary"],
            border_color=C["border"],
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=4)
        self.search_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        toolbar = ctk.CTkFrame(search_frame, fg_color="transparent")
        toolbar.pack(side="right", padx=6, pady=4)
        ctk.CTkButton(toolbar, text="全选", font=F["small"], width=56, height=28,
                       fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                       hover_color=C["toolbar_hover"], corner_radius=CORNER_RADIUS_SM,
                       command=lambda: self._set_all(True)).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="全不选", font=F["small"], width=56, height=28,
                       fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                       hover_color=C["toolbar_hover"], corner_radius=CORNER_RADIUS_SM,
                       command=lambda: self._set_all(False)).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="反选", font=F["small"], width=56, height=28,
                       fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                       hover_color=C["toolbar_hover"], corner_radius=CORNER_RADIUS_SM,
                       command=self._invert).pack(side="left", padx=2)

        table_frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8,
                                    border_width=1, border_color=C["border_light"])
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.filter_table = CTkTable(
            table_frame,
            columns=[
                {"name": "selected", "text": "选中", "width": 50, "anchor": "center"},
                {"name": "info", "text": "角色信息", "width": 450, "anchor": "w"},
            ],
            row_height=30, select_mode="extended",
        )
        self.filter_table.set_theme_colors(
            bg_header=C["table_header"], fg_header=C["table_header_text"],
            bg_row_even=C["card"], bg_row_odd=C["table_alt"],
            bg_selected=C["table_selected"], fg_selected=C["table_selected_text"],
            fg_normal=C["text_primary"],
        )
        self.filter_table.pack(fill="both", expand=True)

        # Bind click on selected column to toggle selection
        self.filter_table._select_toggle_fn = lambda iid: self._toggle_select(iid)
        self.filter_table.tree.bind("<Button-1>", self._on_table_click)

        self._build_entries()
        self._populate_table()

        # Bind click on the tree to toggle selection when clicking the selected column
        self.filter_table.tree.bind("<Button-1>", self._on_table_click)

        status_bar = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        status_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.status_label = ctk.CTkLabel(
            status_bar, text="共 0 个角色",
            font=F["small"], text_color=C["text_muted"],
        )
        self.status_label.pack(side="left", padx=6, pady=4)

        btn_frame = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="取消", font=F["button"], width=80, height=32,
                       fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                       hover_color=C["toolbar_hover"], corner_radius=CORNER_RADIUS_SM,
                       command=self.destroy).pack(side="right", padx=4)
        ok_btn = ctk.CTkButton(btn_frame, text="确定", font=F["button"], width=80, height=32,
                                fg_color=C["primary"], text_color=C["text_on_primary"],
                                hover_color=C["primary_hover"], corner_radius=CORNER_RADIUS_SM,
                                command=self._apply)
        ok_btn.pack(side="right", padx=4)

    def _on_table_click(self, event) -> None:
        """Handle clicks on the table to toggle selection on the selected column."""
        item = self.filter_table.tree.identify_row(event.y)
        col = self.filter_table.tree.identify_column(event.x)
        if item and col == "#1":
            self._toggle_select(item)

    def _toggle_select(self, iid: str) -> None:
        """Toggle selection state for a row."""
        key = iid
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)
        self._refresh_table_display()
        self._update_status()

    def _build_entries(self) -> None:
        """Build the list of unique account/server/name entries."""
        records = getattr(self.app, "growth_records", None)
        if records:
            self._all_entries = self._extract_entries(records)
            self._populate_table()
        else:
            # Data not loaded yet. Show loading status and poll.
            self._poll_count = 0
            self.status_label.configure(text="正在加载角色数据...", text_color=C["text_secondary"])
            self._poll_records()

    def _poll_records(self):
        """Retry loading records, called periodically until data arrives."""
        self._poll_count += 1
        if self._poll_count > 10:
            # Give up after 3 seconds - show error status
            self.status_label.configure(
                text="角色数据加载超时，请检查剑三路径设置后重试",
                text_color=C["red"] if "red" in C else "#e74c3c",
            )
            return
        records = getattr(self.app, "growth_records", None)
        if records:
            self._all_entries = self._extract_entries(records)
            self._populate_table()
        else:
            self.after(300, self._poll_records)

    def _extract_entries(self, records):
        """Extract unique entries from a list of records."""
        seen = {}
        for rec in records:
            account = rec.get('account') or ''
            server = rec.get('server') or ''
            name = rec.get('name') or ''
            # Build display label from whatever fields are available
            parts = [p for p in [account, server, name] if p]
            if not parts:
                # No identifying info at all, skip
                continue
            display = ' / '.join(parts)
            # Use display text as the key to avoid duplicates
            key = display
            if key not in seen:
                seen[key] = {
                    "ownerkey": f"{account}:{server}:{name}",
                    "account": account,
                    "server": server,
                    "name": name,
                    "display": display,
                }
        return sorted(seen.values(), key=lambda e: e["display"].lower())

    def _populate_table(self) -> None:
        search = self.search_var.get().strip().lower()
        if search:
            self._filtered_entries = [
                e for e in self._all_entries
                if search in str(e["account"]).lower()
                or search in str(e["server"]).lower()
                or search in str(e["name"]).lower()
            ]
        else:
            self._filtered_entries = list(self._all_entries)
        self._refresh_table_display()

    def _apply_filter(self) -> None:
        self._populate_table()

    def _refresh_table_display(self) -> None:
        self.filter_table.delete_all()
        for entry in self._filtered_entries:
            key = entry["ownerkey"]
            checked = chr(9733) if key in self._selected else chr(9675)
            self.filter_table.insert(
                values=(checked, entry.get("display", entry["account"]) or entry["name"] or entry["server"]),
                iid=key,
            )

    def _set_all(self, state: bool) -> None:
        for entry in self._filtered_entries:
            key = entry["ownerkey"]
            if state:
                self._selected.add(key)
            else:
                self._selected.discard(key)
        self._refresh_table_display()
        self._update_status()

    def _invert(self) -> None:
        for entry in self._filtered_entries:
            key = entry["ownerkey"]
            if key in self._selected:
                self._selected.discard(key)
            else:
                self._selected.add(key)
        self._refresh_table_display()
        self._update_status()

    def _update_status(self) -> None:
        self.status_label.configure(
            text=f"\u5171 {len(self._filtered_entries)} \u4e2a\u89d2\u8272 \u8def \u5df2\u9009 {len(self._selected)} "
        )

    def _apply(self) -> None:
        self.app.selected_growth_ownerkeys = self._selected
        self.app.growth_role_selection_initialized = True
        self.app.save_config()
        self.app.refresh_growth_role_list()
        self.destroy()

    def _on_table_click(self, event) -> None:
        """Handle clicks on the table to toggle selection."""
        item = self.filter_table.tree.identify_row(event.y)
        col = self.filter_table.tree.identify_column(event.x)
        if item:
            # Only toggle if they click the checkbox column '#1' or the row info column '#2'
            if col in ("#1", "#2"):
                self._toggle_select(item)