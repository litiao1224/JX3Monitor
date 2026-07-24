# -*- coding: utf-8 -*-
"""Page modules for JX3 Click Monitor CustomTkinter GUI.

Each page module contains the build_*_page method extracted from the
main App class, plus any page-specific helper functions.
"""
from __future__ import annotations

import customtkinter as ctk

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jx3_click_monitor_gui_ctk import App

# Shared helpers
from src.gui_ctk.themes import (
    CORNER_RADIUS, CORNER_RADIUS_SM, CORNER_RADIUS_LG,
    BUTTON_HEIGHT, BUTTON_HEIGHT_LG, INPUT_HEIGHT,
)
from src.gui_ctk.themes import COLORS as C, FONTS as F


def build_new_page(app: "App") -> None:
    """Build the 'New' page (monitoring controls)."""
    page = ctk.CTkFrame(app.page_host, fg_color=C["background"], corner_radius=0)
    app.pages["new"] = page
    actions = app.card(page, "记录金团")

    app.new_idle_frame = ctk.CTkFrame(actions, fg_color=C["card"], corner_radius=0)
    app.new_idle_frame.pack(fill="x", padx=22, pady=(0, 20))
    app.start_btn = ctk.CTkButton(
        app.new_idle_frame, text="开始记录",
        command=app.start_monitor,
        font=F["button_large"], fg_color=C["primary"],
        text_color=C["text_on_primary"], hover_color=C["primary_hover"],
        height=BUTTON_HEIGHT_LG, corner_radius=CORNER_RADIUS,
    )
    app.start_btn.pack(fill="x")

    app.new_recording_frame = ctk.CTkFrame(actions, fg_color=C["card"], corner_radius=0)
    ctk.CTkLabel(
        app.new_recording_frame, text="● 正在记录中",
        font=F["subtitle"], text_color=C["primary"],
    ).pack(anchor="center", pady=(16, 12))
    rec_actions = ctk.CTkFrame(app.new_recording_frame, fg_color=C["card"], corner_radius=0)
    rec_actions.pack(fill="x", pady=(4, 16), padx=22)
    ctk.CTkButton(
        rec_actions, text="放弃记录",
        command=app.abandon_recording,
        font=F["button"], fg_color=C["toolbar_bg"],
        text_color=C["text_secondary"], hover_color=C["toolbar_hover"],
        corner_radius=CORNER_RADIUS,
    ).pack(side="left", fill="x", expand=True, padx=(0, 8))
    ctk.CTkButton(
        rec_actions, text="工资完成结算",
        command=app.finish_wage_settlement,
        font=F["button_large"], fg_color=C["primary"],
        text_color=C["text_on_primary"], hover_color=C["primary_hover"],
        corner_radius=CORNER_RADIUS,
    ).pack(side="left", fill="x", expand=True)

    app.new_writing_frame = ctk.CTkFrame(actions, fg_color=C["card"], corner_radius=0)
    ctk.CTkLabel(
        app.new_writing_frame, text="正在等待小退写盘，读取聊天记录中……",
        font=F["subtitle"], text_color=C["primary"],
    ).pack(anchor="center", pady=(16, 8))
    app.writeback_wait_var = ctk.StringVar(
        value="请先小退/退出当前角色。小鹦鹉会继续等待，读到数据后自动弹出入账窗口。",
    )
    ctk.CTkLabel(
        app.new_writing_frame, textvariable=app.writeback_wait_var,
        justify="center", text_color=C["text_muted"], font=F["body"],
    ).pack(anchor="center", pady=(0, 12))
    writing_btns = ctk.CTkFrame(app.new_writing_frame, fg_color="transparent")
    writing_btns.pack(anchor="center", pady=(0, 16))
    ctk.CTkButton(
        writing_btns, text="取消等待",
        command=app.cancel_writeback_wait,
        font=F["button"], fg_color=C["toolbar_bg"],
        text_color=C["text_secondary"], hover_color=C["toolbar_hover"],
        corner_radius=CORNER_RADIUS,
    ).pack(side="left")

    app.generate_btn = ctk.CTkButton(
        actions, text="查看副本账单",
        command=app.make_report,
        font=F["button"], fg_color=C["primary"],
        text_color=C["text_on_primary"], hover_color=C["primary_hover"],
        corner_radius=CORNER_RADIUS,
    )

    app.stats_text = ctk.StringVar(value="尚未开始")
    stats = app.card(page, "本次概览")
    ctk.CTkLabel(
        stats, textvariable=app.stats_text,
        font=F["body"], text_color=C["text_primary"], justify="left",
    ).pack(anchor="w", padx=22, pady=(4, 18))

    hint = ctk.CTkFrame(
        page, fg_color=C["card"],
        corner_radius=CORNER_RADIUS_LG,
        border_width=1, border_color=C["border_subtle"],
    )
    hint.pack(fill="x")
    ctk.CTkLabel(
        hint,
        text="重要提示：\n1. 剑三只有在角色小退或下线后，才会将聊天记录写入本地磁盘。\n2. 若您在领工资时换号，请确保所有参与的角色（包含打本角色和收钱角色）均已小退/下线，再点击『工资完成结算』进行账单生成！",
        font=F["body"], text_color=C["text_muted"],
        wraplength=760, justify="left",
    ).pack(anchor="nw", padx=22, pady=18)


def build_history_page(app: "App") -> None:
    """Build the 'History' page (session list)."""
    page = ctk.CTkFrame(app.page_host, fg_color=C["background"], corner_radius=0)
    app.pages["history"] = page
    table_card = app.card(page)
    table_card.pack_propagate(False)
    table_card.configure(height=550)

    history_list_header = ctk.CTkFrame(table_card, fg_color=C["card"], corner_radius=0)
    history_list_header.pack(fill="x", padx=22, pady=(12, 6))
    ctk.CTkLabel(
        history_list_header, text="记录列表",
        font=F["sidebar"], text_color=C["text_primary"],
    ).pack(side="left")
    ctk.CTkLabel(
        history_list_header, text="  (双击记录可查看结算明细；右键记录可刷新或删除)",
        font=F["small"], text_color=C["text_muted"],
    ).pack(side="left", padx=6)

    ctk.CTkButton(
        history_list_header, text="手动导入",
        command=app.open_my_chat_importer,
        font=F["small"], fg_color=C["toolbar_bg"],
        text_color=C["text_secondary"], hover_color=C["toolbar_hover"],
        width=90, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="right")

    # Use CTkScrollableFrame with grid layout (same as Growth page)
    app.history_body_win: ctk.CTkToplevel | None = None
    history_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
    history_scroll.pack(fill="both", expand=True, padx=22, pady=(0, 14))
    app.history_scroll = history_scroll

    # Recursively bind Button-3 (right-click)
    def bind_recursive(w: object) -> None:
        w.bind("<Button-3>", app.show_history_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_canvas") and w._canvas:
            w._canvas.bind("<Button-3>", app.show_history_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_textbox") and w._textbox:
            w._textbox.bind("<Button-3>", app.show_history_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_label") and w._label:
            w._label.bind("<Button-3>", app.show_history_context_menu)  # type: ignore[union-attr]
        for child in w.winfo_children():  # type: ignore[union-attr]
            bind_recursive(child)

    app._bind_history_recursive = bind_recursive
    bind_recursive(page)

    app.refresh_history_sessions()


def build_income_page(app: "App") -> None:
    """Build the 'Income' page (income/expense table)."""
    page = ctk.CTkFrame(app.page_host, fg_color=C["background"], corner_radius=0)
    app.pages["income"] = page
    table_card = app.card(page)
    table_card.pack_propagate(False)
    table_card.configure(height=550)
    header = ctk.CTkFrame(table_card, fg_color=C["card"], corner_radius=0)
    header.pack(fill="x", padx=22, pady=(12, 6))
    ctk.CTkLabel(
        header, text="收支明细",
        font=F["sidebar"], text_color=C["text_primary"],
    ).pack(side="left")

    ctk.CTkButton(
        header, text="统计分析",
        command=app.open_income_analysis,
        font=F["small"], fg_color=C["toolbar_bg"],
        text_color=C["text_secondary"], hover_color=C["toolbar_hover"],
        width=80, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="right", padx=(4, 0))
    ctk.CTkButton(
        header, text="筛选",
        command=app.open_income_filter_window,
        font=F["small"], fg_color=C["toolbar_bg"],
        text_color=C["text_secondary"], hover_color=C["toolbar_hover"],
        width=60, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="right", padx=(4, 0))

    # Use CTkScrollableFrame with grid layout (same as Growth page)
    income_scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
    income_scroll.pack(fill="both", expand=True)
    app.income_scroll = income_scroll

    # Recursively bind Button-3 (right-click)
    def bind_recursive(w: object) -> None:
        w.bind("<Button-3>", app.show_income_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_canvas") and w._canvas:
            w._canvas.bind("<Button-3>", app.show_income_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_textbox") and w._textbox:
            w._textbox.bind("<Button-3>", app.show_income_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_label") and w._label:
            w._label.bind("<Button-3>", app.show_income_context_menu)  # type: ignore[union-attr]
        for child in w.winfo_children():  # type: ignore[union-attr]
            bind_recursive(child)

    app._bind_income_recursive = bind_recursive
    bind_recursive(page)
    app.income_records: list[dict] = []
    app.refresh_income_page()


def build_growth_page(app: "App") -> None:
    """Build the 'Growth' page (character growth tracking)."""
    page = ctk.CTkFrame(app.page_host, fg_color=C["background"], corner_radius=0)
    app.pages["growth"] = page

    table_card = app.card(page, "角色副本进度全家桶")
    table_card.pack_propagate(False)
    table_card.configure(height=650)

    # Filter toolbar row above the grid
    filter_bar = ctk.CTkFrame(table_card, fg_color=C['card'], corner_radius=0)
    filter_bar.pack(fill='x', padx=10, pady=(10, 4))
    app.growth_filter_btn = ctk.CTkButton(
        filter_bar, text='筛选', font=F['small'], fg_color=C['toolbar_bg'],
        text_color=C['text_secondary'], hover_color=C['toolbar_hover'], corner_radius=CORNER_RADIUS_SM,
        width=80, height=28,
    )
    app.growth_filter_btn.pack(side='right', padx=(0, 6), pady=4)
    app.growth_filter_btn.configure(command=app.open_growth_filter_dialog)
    ctk.CTkLabel(filter_bar, text='点击筛选按钮选择要显示的账号和角色', font=F['small'], text_color=C['text_muted']).pack(side='left', padx=6, pady=4)

    # Use CTkScrollableFrame with grid for colored text
    app.growth_role_grid = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
    app.growth_role_grid.pack(fill="both", expand=True, padx=10, pady=10)
    app.growth_role_columns()

    # Recursively bind Button-3 (right-click) to all components inside the growth page
    def bind_recursive(w: object) -> None:
        w.bind("<Button-3>", app.show_growth_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_canvas") and w._canvas:
            w._canvas.bind("<Button-3>", app.show_growth_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_textbox") and w._textbox:
            w._textbox.bind("<Button-3>", app.show_growth_context_menu)  # type: ignore[union-attr]
        if hasattr(w, "_label") and w._label:
            w._label.bind("<Button-3>", app.show_growth_context_menu)  # type: ignore[union-attr]
        for child in w.winfo_children():  # type: ignore[union-attr]
            bind_recursive(child)

    app._bind_growth_recursive = bind_recursive
    bind_recursive(page)
    app.refresh_growth_page()


def build_settings_page(app: "App") -> None:
    """Build the 'Settings' page with a responsive 2-column dashboard layout."""
    from datetime import datetime

    # Scrollable container for settings page to fit all resolutions
    scroll = ctk.CTkScrollableFrame(app.page_host, fg_color="transparent")
    app.pages["settings"] = scroll

    # Main 2-column grid container
    grid = ctk.CTkFrame(scroll, fg_color="transparent")
    grid.pack(fill="both", expand=True)
    grid.grid_columnconfigure(0, weight=1, minsize=400)
    grid.grid_columnconfigure(1, weight=1, minsize=440)

    left_col = ctk.CTkFrame(grid, fg_color="transparent")
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)

    right_col = ctk.CTkFrame(grid, fg_color="transparent")
    right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)

    # ── Left Column Card 1: 路径与数据管理 ──
    paths = app.card(left_col, "路径与数据管理")
    ctk.CTkLabel(
        paths, text="用于设置游戏路径、日志输出目录及数据备份导出",
        font=F["small"], text_color=C["text_muted"],
    ).pack(anchor="w", padx=22, pady=(0, 10))

    def _path_row(frame, label, var, cmd) -> None:
        row = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=0)
        row.pack(fill="x", padx=22, pady=6)
        ctk.CTkLabel(
            row, text=label, width=80, anchor="w",
            font=F["body"], text_color=C["text_secondary"],
        ).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=var,
            fg_color=C["entry_bg"], text_color=C["text_primary"],
            border_color=C["border"], font=F["body"],
            corner_radius=CORNER_RADIUS_SM, height=INPUT_HEIGHT,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            row, text="浏览", command=cmd,
            font=F["small"], fg_color=C["toolbar_bg"],
            text_color=C["text_secondary"], hover_color=C["toolbar_hover"],
            width=64, height=INPUT_HEIGHT, corner_radius=CORNER_RADIUS_SM,
        ).pack(side="right")

    _path_row(paths, "游戏路径", app.jx3_var, app.choose_jx3)
    _path_row(paths, "输出目录", app.out_var, app.choose_out)

    data_row_top = ctk.CTkFrame(paths, fg_color=C["card"], corner_radius=0)
    data_row_top.pack(fill="x", padx=22, pady=(6, 4))
    ctk.CTkButton(
        data_row_top, text="📁 打开数据文件夹",
        command=app.open_live_folder,
        font=F["button"], fg_color=C["primary"],
        text_color=C["text_on_primary"], hover_color=C["primary_hover"],
        height=BUTTON_HEIGHT, corner_radius=CORNER_RADIUS_SM,
    ).pack(fill="x")

    data_row_sub = ctk.CTkFrame(paths, fg_color=C["card"], corner_radius=0)
    data_row_sub.pack(fill="x", padx=22, pady=(0, 16))
    ctk.CTkButton(
        data_row_sub, text="📤 导出数据备份",
        command=app.export_data,
        font=F["button"], fg_color=C["entry_bg"],
        text_color=C["text_primary"], hover_color=C["primary_hover"],
        border_width=1, border_color=C["border"],
        height=BUTTON_HEIGHT, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="left", fill="x", expand=True, padx=(0, 4))
    ctk.CTkButton(
        data_row_sub, text="📥 导入数据备份",
        command=app.import_data,
        font=F["button"], fg_color=C["entry_bg"],
        text_color=C["text_primary"], hover_color=C["primary_hover"],
        border_width=1, border_color=C["border"],
        height=BUTTON_HEIGHT, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="left", fill="x", expand=True, padx=(4, 0))

    # ── Left Column Card 2: 启动方式与偏好 ──
    startup = app.card(left_col, "启动方式")
    ctk.CTkLabel(
        startup, text="设置记账软件启动与监控联动行为",
        font=F["small"], text_color=C["text_muted"],
    ).pack(anchor="w", padx=22, pady=(0, 10))

    radio_row = ctk.CTkFrame(startup, fg_color=C["card"], corner_radius=0)
    radio_row.pack(fill="x", padx=22, pady=(0, 14))
    for text, value in [("手动启动", "manual"), ("开机自动启动", "boot"), ("跟随剑三启动", "jx3")]:
        ctk.CTkRadioButton(
            radio_row, text=text, value=value,
            variable=app.startup_mode_var,
            font=F["body"], text_color=C["text_primary"],
            fg_color=C["primary"], border_color=C["border"],
        ).pack(side="left", padx=(0, 16), pady=4)

    # ── Left Column Card 3: 保存按钮卡片 ──
    save_card = app.card(left_col)
    save_row = ctk.CTkFrame(save_card, fg_color=C["card"], corner_radius=0)
    save_row.pack(fill="x", padx=22, pady=14)
    ctk.CTkButton(
        save_row, text="💾 保存所有设置",
        command=app.save_settings,
        font=F["button_large"], fg_color=C["primary"],
        text_color=C["text_on_primary"], hover_color=C["primary_hover"],
        height=BUTTON_HEIGHT_LG, corner_radius=CORNER_RADIUS,
    ).pack(fill="x")

    # ── Right Column Card 1: 赛季时间设置 ──
    now_year = datetime.now().year
    season = app.card(right_col, "赛季时间设置")
    ctk.CTkLabel(
        season, text="用于筛选和统计指定时间段的数据",
        font=F["small"], text_color=C["text_muted"],
    ).pack(anchor="w", padx=22, pady=(0, 10))
    app._season_date_row(season, "开始日期", app.season_start_var, now_year)
    app._season_date_row(season, "结束日期", app.season_end_var, now_year)

    # ── Right Column Card 2: 网页云端同步设置 ──
    cloud = app.card(right_col, "网页云端同步设置")
    ctk.CTkLabel(
        cloud, text="将账目与全家桶进度上传至云存储，手机扫码即可联网查阅。",
        font=F["small"], text_color=C["text_muted"],
    ).pack(anchor="w", padx=22, pady=(0, 10))

    ctk.CTkCheckBox(
        cloud, text="启用云端自动同步",
        variable=app.cloud_sync_enabled_var,
        font=F["body"], text_color=C["text_primary"],
        fg_color=C["primary"], border_color=C["border"],
    ).pack(anchor="w", padx=22, pady=(0, 8))

    prov_row = ctk.CTkFrame(cloud, fg_color=C["card"], corner_radius=0)
    prov_row.pack(fill="x", padx=22, pady=4)
    ctk.CTkLabel(
        prov_row, text="云服务商", width=110, anchor="w",
        font=F["body"], text_color=C["text_secondary"],
    ).pack(side="left")
    ctk.CTkSegmentedButton(
        prov_row, values=["cos", "oss"],
        variable=app.cloud_provider_var,
        font=F["body"], fg_color=C["entry_bg"],
        selected_color=C["primary"],
    ).pack(side="left", fill="x", expand=True)

    def _field_row(frame, label, var, placeholder="") -> None:
        row = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=0)
        row.pack(fill="x", padx=22, pady=4)
        ctk.CTkLabel(
            row, text=label, width=110, anchor="w",
            font=F["body"], text_color=C["text_secondary"],
        ).pack(side="left")
        ctk.CTkEntry(
            row, textvariable=var, placeholder_text=placeholder,
            fg_color=C["entry_bg"], text_color=C["text_primary"],
            border_color=C["border"], font=F["body"],
            corner_radius=CORNER_RADIUS_SM, height=INPUT_HEIGHT,
        ).pack(side="left", fill="x", expand=True)

    _field_row(cloud, "SecretId / AK", app.cloud_secret_id_var, "COS SecretId 或 OSS AccessKeyId")
    _field_row(cloud, "SecretKey / SK", app.cloud_secret_key_var, "COS SecretKey 或 OSS AccessKeySecret")
    _field_row(cloud, "存储桶 (Bucket)", app.cloud_bucket_var, "存储桶名称")
    _field_row(cloud, "地域 (COS Region)", app.cloud_region_var, "仅腾讯云(如 ap-shanghai)")
    _field_row(cloud, "端点 (OSS Endpoint)", app.cloud_endpoint_var, "仅阿里云(如 oss-cn-hangzhou...)")
    _field_row(cloud, "自定义看板域名", app.cloud_url_path_var, "选填，静态网站 URL 或自定义域名")

    act_row = ctk.CTkFrame(cloud, fg_color=C["card"], corner_radius=0)
    act_row.pack(fill="x", padx=22, pady=(10, 16))
    ctk.CTkButton(
        act_row, text="手动同步数据 (data.js)",
        command=lambda: app.trigger_background_cloud_sync(upload_html=False, manual=True),
        font=F["small"], fg_color=C["entry_bg"],
        text_color=C["text_primary"], hover_color=C["primary_hover"],
        border_width=1, border_color=C["border"],
        height=INPUT_HEIGHT, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="left", padx=(0, 4), expand=True, fill="x")
    ctk.CTkButton(
        act_row, text="初始化上传主页 (index.html)",
        command=lambda: app.trigger_background_cloud_sync(upload_html=True, manual=True),
        font=F["small"], fg_color=C["entry_bg"],
        text_color=C["text_primary"], hover_color=C["primary_hover"],
        border_width=1, border_color=C["border"],
        height=INPUT_HEIGHT, corner_radius=CORNER_RADIUS_SM,
    ).pack(side="left", padx=(4, 0), expand=True, fill="x")
