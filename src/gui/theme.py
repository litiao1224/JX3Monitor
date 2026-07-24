# -*- coding: utf-8 -*-
"""Modern theme for JX3 Click Monitor GUI.

Applies consistent styling to ttk widgets for a polished look.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Color palette
COLORS = {
    # Primary
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "primary_light": "#dbeafe",
    # Success
    "success": "#16a34a",
    "success_hover": "#15803d",
    # Warning
    "warning": "#f59e0b",
    "warning_hover": "#d97706",
    # Danger
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    # Sidebar
    "sidebar_bg": "#1e293b",
    "sidebar_text": "#e2e8f0",
    "sidebar_hover": "#334155",
    "sidebar_active": "#2563eb",
    # Content
    "content_bg": "#f8fafc",
    "card_bg": "#ffffff",
    "border": "#e2e8f0",
    "border_focus": "#2563eb",
    # Text
    "text_primary": "#1e293b",
    "text_secondary": "#64748b",
    "text_muted": "#94a3b8",
    # Table
    "table_header_bg": "#f1f5f9",
    "table_header_text": "#475569",
    "table_row_hover": "#f1f5f9",
    "table_selected": "#dbeafe",
    "table_alternate": "#fafbfc",
    # Scrollbar
    "scrollbar_bg": "#e2e8f0",
    "scrollbar_hover": "#cbd5e1",
}

FONTS = {
    "title": ("Microsoft YaHei UI", 16, "bold"),
    "subtitle": ("Microsoft YaHei UI", 12, "bold"),
    "body": ("Microsoft YaHei UI", 10),
    "small": ("Microsoft YaHei UI", 9),
    "button": ("Microsoft YaHei UI", 10),
    "table": ("Microsoft YaHei UI", 9),
    "table_header": ("Microsoft YaHei UI", 9, "bold"),
}


def apply_theme(root: tk.Tk) -> None:
    """Apply modern theme to all ttk widgets in the application."""
    style = ttk.Style()

    # Use clam theme as base for better customization
    style.theme_use("clam")

    # Configure default frame
    style.configure("TFrame", background=COLORS["content_bg"])

    # Configure LabelFrame
    style.configure(
        "TLabelframe",
        background=COLORS["card_bg"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=COLORS["card_bg"],
        foreground=COLORS["text_primary"],
        font=FONTS["subtitle"],
        padding=(8, 0),
    )

    # Configure buttons
    style.configure(
        "TButton",
        background=COLORS["primary"],
        foreground="white",
        bordercolor=COLORS["primary"],
        focuscolor=COLORS["primary_hover"],
        font=FONTS["button"],
        padding=(12, 6),
        borderwidth=1,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", COLORS["primary_hover"]), ("pressed", COLORS["primary_hover"])],
        foreground=[("active", "white"), ("pressed", "white")],
    )

    # Sidebar button style
    style.configure(
        "Sidebar.TButton",
        background=COLORS["sidebar_bg"],
        foreground=COLORS["sidebar_text"],
        bordercolor=COLORS["sidebar_bg"],
        font=("Microsoft YaHei UI", 11),
        padding=(16, 10),
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "Sidebar.TButton",
        background=[("active", COLORS["sidebar_hover"])],
        foreground=[("active", "white")],
    )

    # Active sidebar button style
    style.configure(
        "Sidebar.Active.TButton",
        background=COLORS["sidebar_active"],
        foreground="white",
        bordercolor=COLORS["sidebar_active"],
        font=("Microsoft YaHei UI", 11, "bold"),
        padding=(16, 10),
        borderwidth=0,
        relief="flat",
    )

    # Treeview
    style.configure(
        "Treeview",
        background=COLORS["card_bg"],
        foreground=COLORS["text_primary"],
        fieldbackground=COLORS["card_bg"],
        borderwidth=0,
        font=FONTS["table"],
        rowheight=32,
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["table_selected"])],
        foreground=[("selected", COLORS["text_primary"])],
    )

    style.configure(
        "Treeview.Heading",
        background=COLORS["table_header_bg"],
        foreground=COLORS["table_header_text"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        relief="solid",
        font=FONTS["table_header"],
        padding=(10, 8),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["primary_light"]), ("pressed", COLORS["primary_light"])],
        foreground=[("active", COLORS["primary"]), ("pressed", COLORS["primary"])],
    )

    # Treeview layout adjustments
    style.configure("Treeview", padding=(6, 4))
    style.configure("Treeview.Heading", padding=(10, 6))

    # Entry
    style.configure(
        "TEntry",
        fieldbackground=COLORS["card_bg"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        padding=(8, 4),
        font=FONTS["body"],
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", COLORS["border_focus"])],
    )

    # Combobox
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["card_bg"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        padding=(8, 4),
        font=FONTS["body"],
    )
    style.configure(
        "TCombobox.Listbox",
        background=COLORS["card_bg"],
        foreground=COLORS["text_primary"],
        font=FONTS["body"],
    )

    # Separator
    style.configure(
        "TSeparator",
        background=COLORS["border"],
    )

    # Radiobutton/Checkbutton
    style.configure(
        "TRadiobutton",
        background=COLORS["content_bg"],
        foreground=COLORS["text_primary"],
        font=FONTS["body"],
        padding=(4, 2),
    )
    style.configure(
        "TCheckbutton",
        background=COLORS["content_bg"],
        foreground=COLORS["text_primary"],
        font=FONTS["body"],
        padding=(4, 2),
    )

    # Notebook (if used)
    style.configure(
        "TNotebook",
        background=COLORS["content_bg"],
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=COLORS["card_bg"],
        foreground=COLORS["text_secondary"],
        padding=(12, 8),
        font=FONTS["body"],
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["primary_light"])],
        foreground=[("selected", COLORS["primary"])],
    )

    # Progressbar
    style.configure(
        "TProgressbar",
        background=COLORS["primary"],
        troughcolor=COLORS["border"],
        borderwidth=0,
        thickness=8,
    )

    # Scrollbar
    style.configure(
        "TScrollbar",
        background=COLORS["border"],
        borderwidth=0,
        troughcolor=COLORS["card_bg"],
        arrowsize=12,
    )
    style.map(
        "TScrollbar",
        background=[("active", COLORS["text_muted"])],
    )

    # PanedWindow
    style.configure(
        "TPanedwindow",
        background=COLORS["border"],
        sashthickness=3,
    )

    # Set root window background
    root.configure(background=COLORS["content_bg"])
