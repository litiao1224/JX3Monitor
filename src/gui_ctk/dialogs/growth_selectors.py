# -*- coding: utf-8 -*-
"""Growth page dialogs: role selector, dungeon selector, equipment viewer."""
from __future__ import annotations

import base64
import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

from src.gui_ctk.dialogs.shared import C, F, position_dialog
from src.gui_ctk.widgets import CTkTable

logger = logging.getLogger("jx3_monitor.dialogs.growth")


# ── GrowthRoleSelector ─────────────────────────────────────────


class GrowthRoleSelector(ctk.CTkToplevel):
    """Select which growth roles to display/track."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("选择账号和角色")
        position_dialog(self, app, 620, 520, 500, 400)
        self.transient(parent or app)
        self.grab_set()

        if not app.growth_records:
            if not app.refresh_growth_page():
                self.destroy()
                return

        ctk.CTkLabel(self,
            text="勾选要显示/刷新的账号和角色；未勾选的角色会从角色成长列表隐藏，但不会删除数据。",
            text_color=C["text_muted"], font=F["small"],
            justify="left").pack(anchor="w", padx=14, pady=(12, 6))

        visible_records = [
            (i, r) for i, r in enumerate(app.growth_records)
            if app.growth_ownerkey(r) not in app.hidden_growth_ownerkeys
        ]
        visible_records.sort(key=lambda item: (
            str(item[1].get("account") or "").lower(),
            str(item[1].get("server") or "").lower(),
            str(item[1].get("name") or "").lower(),
        ))

        self._selected: set[str] = set(app.selected_growth_ownerkeys)
        if not app.growth_role_selection_initialized:
            self._selected = {app.growth_ownerkey(r) for _i, r in visible_records if app.growth_ownerkey(r)}

        def mark(key: str) -> str:
            return "☑" if key in self._selected else "☐"

        table_frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=8,
                                   border_width=1, border_color=C["border_light"])
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.role_table = CTkTable(
            table_frame,
            columns=[
                {"name": "selected", "text": "选中", "width": 60, "anchor": "center"},
                {"name": "account", "text": "账号", "width": 160, "anchor": "w"},
                {"name": "server", "text": "服务器", "width": 140, "anchor": "w"},
                {"name": "name", "text": "角色", "width": 180, "anchor": "w"},
            ],
            row_height=32, select_mode="browse",
        )
        self.role_table.set_theme_colors(
            bg_header=C["table_header"], fg_header=C["table_header_text"],
            bg_row_even=C["card"], bg_row_odd=C["table_alt"],
            bg_selected=C["table_selected"], fg_selected=C["table_selected_text"],
            fg_normal=C["text_primary"],
        )
        self.role_table.pack(fill="both", expand=True)
        self.role_table.set_sort_key("selected", lambda v: (0, v))

        self._row_keys: dict[str, str] = {}
        for i, r in visible_records:
            key = app.growth_ownerkey(r)
            iid = str(i)
            self._row_keys[iid] = key
            self.role_table.insert(values=(mark(key), r.get("account"), r.get("server"), r.get("name")),
                                   iid=iid)

        self.role_table.bind("<Button-1>", lambda e: self.after(1, self._toggle_current_selection))

        toolbar = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        toolbar.pack(fill="x", padx=10, pady=6)
        ctk.CTkButton(toolbar, text="全选", command=lambda: self._set_all(True),
                      font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="全不选", command=lambda: self._set_all(False),
                      font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="left", padx=4)

        actions = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        actions.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(actions, text="确定", command=self._apply,
                      font=F["button"], fg_color=C["primary"], text_color=C["text_on_primary"],
                      hover_color=C["primary_hover"], corner_radius=6, border_width=0).pack(side="right", padx=4)
        ctk.CTkButton(actions, text="取消", command=self.destroy, font=F["button"],
                      fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="right", padx=4)

    def _toggle_current_selection(self) -> None:
        for iid in self.role_table.get_selection():
            self._toggle_iid(iid)

    def _toggle_iid(self, iid: str) -> None:
        key = self._row_keys.get(iid)
        if not key:
            return
        if key in self._selected:
            self._selected.remove(key)
        else:
            self._selected.add(key)
        self._rebuild()

    def _set_all(self, value: bool) -> None:
        keys = {self._row_keys[iid] for iid in self.role_table.get_children() if self._row_keys.get(iid)}
        if value:
            self._selected.update(keys)
        else:
            self._selected.difference_update(keys)
        self._rebuild()

    def _rebuild(self) -> None:
        self.role_table.delete_all()
        app = self.app
        for iid, key in self._row_keys.items():
            rec = app.growth_records[int(iid)] if iid.isdigit() and int(iid) < len(app.growth_records) else {}
            mark = "☑" if key in self._selected else "☐"
            self.role_table.insert(values=(mark, rec.get("account"), rec.get("server"), rec.get("name")), iid=iid)

    def _apply(self) -> None:
        self.app.selected_growth_ownerkeys = set(self._selected)
        self.app.growth_role_selection_initialized = True
        self.app.save_config()
        if hasattr(self.app, "update_growth_filter_options"):
            self.app.update_growth_filter_options()
        self.app.refresh_growth_role_list()
        self.app.status_var.set(
            f"角色成长 · 当前显示 {len(self.app.growth_filtered_records())} 个已选角色")
        self.destroy()


# ── GrowthDungeonSelector ──────────────────────────────────────


class GrowthDungeonSelector(ctk.CTkToplevel):
    """Select which dungeons to track in the growth page."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("选择秘境")
        position_dialog(self, app, 620, 560, 520, 420)
        self.transient(parent or app)
        self.grab_set()

        if not app.growth_dungeon_map:
            if not app.refresh_growth_page():
                self.destroy()
                return

        ctk.CTkLabel(self,
            text="勾选要显示在角色列表中的秘境，选中后将自动添加为列。",
            text_color=C["text_muted"], font=F["small"],
            justify="left").pack(anchor="w", padx=14, pady=(10, 4))

        scroll = ctk.CTkScrollableFrame(self, fg_color=C["card"], corner_radius=8,
                                        border_width=1, border_color=C["border_light"])
        scroll.pack(fill="both", expand=True, padx=10, pady=6)

        dungeons = sorted(app.growth_dungeon_map.items(), key=lambda x: x[1])
        selected = set(app.selected_growth_dungeons)

        self.check_vars: dict[str, ctk.BooleanVar] = {}
        self.check_boxes: dict[str, ctk.CTkCheckBox] = {}
        for mid, name in dungeons:
            var = ctk.BooleanVar(value=mid in selected)
            self.check_vars[mid] = var
            cb = ctk.CTkCheckBox(
                scroll, text=name, variable=var, font=F["body"],
                text_color=C["text_primary"], fg_color=C["primary"],
                border_color=C["border"], hover_color=C["primary_hover"],
            )
            cb.pack(anchor="w", padx=12, pady=3)
            self.check_boxes[mid] = cb

        toolbar = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        toolbar.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(toolbar, text="全选", command=lambda: self._toggle_all(True),
                      font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="全不选", command=lambda: self._toggle_all(False),
                      font=F["button"], fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="left", padx=4)

        actions = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        actions.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(actions, text="确定", command=self._apply,
                      font=F["button"], fg_color=C["primary"], text_color=C["text_on_primary"],
                      hover_color=C["primary_hover"], corner_radius=6, border_width=0).pack(side="right", padx=4)
        ctk.CTkButton(actions, text="取消", command=self.destroy, font=F["button"],
                      fg_color=C["toolbar_bg"], text_color=C["text_secondary"],
                      hover_color=C["toolbar_hover"], corner_radius=6, border_width=0).pack(side="right", padx=4)

    def _toggle_all(self, state: bool) -> None:
        for var in self.check_vars.values():
            var.set(state)

    def _apply(self) -> None:
        app = self.app
        app.selected_growth_dungeons = {
            mid for mid, var in self.check_vars.items() if var.get()
        }
        app.growth_dungeon_selection_initialized = True
        if hasattr(app, "update_growth_columns"):
            app.update_growth_columns()
        app.refresh_growth_role_list()
        app.save_config()
        self.destroy()


# ── GrowthEquipmentWindow ──────────────────────────────────────


class GrowthEquipmentWindow(ctk.CTkToplevel):
    """Display equipment details for a selected growth character."""

    def __init__(self, app: App, parent: ctk.CTkBaseClass | None = None,
                 rec: dict | None = None) -> None:
        super().__init__(parent or app)
        self.app = app
        self.title("装备详情")
        position_dialog(self, app, 1280, 820, 1080, 680)
        self.transient(parent or app)
        self.grab_set()

        if not rec:
            self.destroy()
            return

        self.rec = rec
        self._icon_cache: dict[str, object] = {}
        self._icon_labels: dict[str, object] = {}
        self._item_lookup_loading: set[str] = set()
        self._selected_item_name = ""
        self._big_icon_label: ctk.CTkLabel | None = None

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=C["toolbar_bg"], corner_radius=0)
        header.pack(fill="x")

        role_title = f"{rec.get('server') or ''} · {rec.get('name') or ''}"
        ctk.CTkLabel(header, text=role_title, font=("Microsoft YaHei UI", 18, "bold"),
                     text_color=C["text_primary"]).pack(side="left", padx=18, pady=12)
        ctk.CTkLabel(header, text=f"装备分 {rec.get('score') or '-'}",
                     font=F["card_title"],
                     text_color=C["text_secondary"]).pack(side="left", padx=8)

        # ── Body ──
        body = ctk.CTkFrame(self, fg_color=C["background"], corner_radius=0)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        detail_panel = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=8,
                                    border_width=1, border_color=C["border_light"])
        detail_panel.pack(side="left", fill="both", expand=True, padx=(0, 6))

        list_panel = ctk.CTkFrame(body, fg_color=C["card"], width=430, corner_radius=8,
                                  border_width=1, border_color=C["border_light"])
        list_panel.pack(side="right", fill="y")
        list_panel.pack_propagate(False)

        ctk.CTkLabel(list_panel, text="装备栏", font=F["card_title"],
                     text_color=C["text_primary"]).pack(anchor="w", padx=12, pady=(12, 2))
        ctk.CTkLabel(list_panel, text="本地只读取装备名称",
                     font=F["small"], text_color=C["text_muted"]).pack(anchor="w", padx=12, pady=(0, 6))

        self.suit_selector_frame = ctk.CTkFrame(list_panel, fg_color=C["card"], corner_radius=0)
        self.suit_selector_frame.pack(fill="x", padx=8, pady=(0, 6))
        self.equip_scroll = ctk.CTkScrollableFrame(list_panel, fg_color=C["card"], corner_radius=0)
        self.equip_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        detail_header = ctk.CTkFrame(detail_panel, fg_color=C["card"], corner_radius=0)
        detail_header.pack(fill="x", padx=14, pady=(12, 0))
        self._big_icon_label = ctk.CTkLabel(
            detail_header, text="图标", width=48, height=48,
            fg_color=C["background_alt"], text_color=C["text_muted"],
            corner_radius=6, font=F["small"],
        )
        self._big_icon_label.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(detail_header, text="装备详情",
                     font=F["card_title"], text_color=C["text_primary"]
                     ).pack(side="left", anchor="w")
        self.detail_text = ctk.CTkTextbox(detail_panel, wrap="word", font=F["body"],
                                          fg_color=C["entry_bg"], text_color=C["text_primary"],
                                          border_width=1, border_color=C["entry_border"])
        self.detail_text.pack(fill="both", expand=True, padx=12, pady=12)
        self.detail_text.insert("0.0", "在右侧选择装备查看详情")
        self.detail_text.configure(state="disabled")

        self.suit_items = self._normalize_suit_items(rec)
        self.suit_keys = sorted(self.suit_items.keys(), key=lambda value: (str(value) != str(rec.get("current_suit") or ""), str(value)))
        self.suit_label_to_key: dict[str, object] = {}
        self.current_suit_key: object | None = None
        self._build_suit_selector(rec)
        initial_suit = rec.get("current_suit") if rec.get("current_suit") in self.suit_items else (self.suit_keys[0] if self.suit_keys else None)
        self._load_suit_items(initial_suit)

    def _normalize_suit_items(self, rec: dict) -> dict[object, list[dict]]:
        raw = rec.get("suit_items")
        if isinstance(raw, dict) and raw:
            return {key: list(items) for key, items in raw.items() if isinstance(items, list)}
        raw = rec.get("equip_items") or rec.get("items") or []
        if isinstance(raw, list):
            return {rec.get("current_suit") or "当前": list(raw)}
        return {}

    def _build_suit_selector(self, rec: dict) -> None:
        for child in self.suit_selector_frame.winfo_children():
            child.destroy()
        if len(self.suit_keys) <= 1:
            return
        ctk.CTkLabel(self.suit_selector_frame, text="选择套装", font=F["small"],
                     text_color=C["text_muted"]).pack(anchor="w", padx=4, pady=(0, 4))
        current_suit = rec.get("current_suit")
        labels = []
        for key in self.suit_keys:
            count = len(self.suit_items.get(key) or [])
            label = f"套装 {key}" + ("（当前）" if str(key) == str(current_suit) else f"（{count} 件）")
            labels.append(label)
            self.suit_label_to_key[label] = key
        self.suit_var = ctk.StringVar(value=labels[0])
        ctk.CTkSegmentedButton(
            self.suit_selector_frame, values=labels, variable=self.suit_var,
            command=lambda label: self._load_suit_items(self.suit_label_to_key.get(label)),
            font=F["small"], fg_color=C["toolbar_bg"], selected_color=C["primary"],
            selected_hover_color=C["primary_hover"], unselected_color=C["toolbar_bg"],
            unselected_hover_color=C["toolbar_hover"], text_color=C["text_primary"],
        ).pack(fill="x", padx=4, pady=(0, 4))

    def _load_suit_items(self, suit_key: object | None) -> None:
        self.current_suit_key = suit_key
        self._icon_labels.clear()
        if self._big_icon_label and self._big_icon_label.winfo_exists():
            self._big_icon_label.configure(image=None, text="图标")
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0", "end")
        self.detail_text.insert("0.0", "在右侧选择装备查看详情")
        self.detail_text.configure(state="disabled")
        for child in self.equip_scroll.winfo_children():
            child.destroy()
        items = self.suit_items.get(suit_key) or []
        if not items:
            ctk.CTkLabel(self.equip_scroll, text="暂无装备数据",
                         text_color=C["text_muted"], font=F["body"]).pack(pady=20)
            return
        for item in items:
            self._add_equip_card(self.equip_scroll, item, str(suit_key or ""))

    def _add_equip_card(self, parent: ctk.CTkFrame, item: dict, suit: str) -> None:
        name = item.get("name") or item.get("Name") or "未知装备"
        icon = item.get("icon") or item.get("Icon") or "?"

        card = ctk.CTkFrame(parent, fg_color=C["background_alt"], corner_radius=6,
                            border_width=1, border_color=C["border_light"])
        card.pack(fill="x", pady=3)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(5, 0))
        icon_label = ctk.CTkLabel(
            row, text=str(item.get("slot_name") or icon or "图")[:2], width=36, height=36,
            fg_color=C["card"], text_color=C["text_muted"], corner_radius=5,
            font=F["small"],
        )
        icon_label.pack(side="left", padx=(0, 8))
        self._icon_labels[name] = icon_label

        line1 = name
        line2 = ""
        level = item.get("item_level") or item.get("equip_score_text") or item.get("Level") or item.get("level") or item.get("Quality")
        if level:
            line2 += f"等级 {level}"
        if suit:
            line2 += f" 套装 {suit}" if line2 else f"套装 {suit}"

        text_box = ctk.CTkFrame(row, fg_color="transparent")
        text_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text_box, text=line1, font=F["body"],
                     text_color=C["text_primary"], anchor="w"
                     ).pack(fill="x")
        if line2:
            ctk.CTkLabel(text_box, text=line2, font=F["small"],
                         text_color=C["text_muted"], anchor="w"
                         ).pack(fill="x")

        def on_click(_event=None, n=name, it=item) -> None:
            self._show_item_detail(n, it)

        for widget in (card, row, icon_label, text_box, *text_box.winfo_children()):
            widget.bind("<Button-1>", on_click)

    def _show_item_detail(self, name: str, item: dict) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0", "end")
        lines = [
            f"名称：{name}",
            f"部位：{item.get('slot_name') or '-' }",
            f"等级：{item.get('item_level') or item.get('equip_score_text') or item.get('Level') or item.get('level') or '-' }",
            f"精炼等级：{item.get('strength') or 0}",
        ]
        attrs = item.get("attr_lines") or item.get("attributes") or []
        if attrs:
            lines.extend(["", "属性："])
            if isinstance(attrs, list):
                lines.extend(f"  {attr}" for attr in attrs)
            else:
                lines.append(f"  {attrs}")
        enchants = item.get("enchant_lines") or []
        if enchants:
            lines.extend(["", "附魔/特殊效果："])
            lines.extend(f"  {line}" for line in enchants)
        sockets = item.get("socket_lines") or []
        if sockets:
            lines.extend(["", "镶嵌孔："])
            lines.extend(f"  {line}" for line in sockets)
        text = "\n".join(str(line) for line in lines if line is not None)
        self.detail_text.insert("0.0", f"本地数据\n\n{text}")
        self.detail_text.configure(state="disabled")

