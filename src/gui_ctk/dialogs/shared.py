# -*- coding: utf-8 -*-
"""Shared dialog helpers for JX3 Click Monitor GUI dialogs.

Provides positioning, color/font constants, and custom dialog windows.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

if TYPE_CHECKING:
    from src.gui_ctk.themes import COLORS as _COLORS, FONTS as _FONTS

logger = logging.getLogger("jx3_monitor.dialogs")


# ── Color / font constants (re-exported from themes for convenience) ──

try:
    from src.gui_ctk.themes import COLORS as C, FONTS as F
except ImportError:
    C: dict = {}  # type: ignore[misc]
    F: dict = {}  # type: ignore[misc]


# ── Dialog positioning helper ──────────────────────────────────


def position_dialog(
    win: ctk.CTkToplevel,
    app: ctk.CTk | ctk.CTkToplevel | None,
    width: int,
    height: int,
    min_width: int | None = None,
    min_height: int | None = None,
) -> None:
    """Place a dialog window precisely centered over the parent main window."""
    try:
        win.update_idletasks()
    except Exception:
        pass
    min_width = min_width or width
    min_height = min_height or height
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    width = max(min_width, min(width, screen_w - 60))
    height = max(min_height, min(height, screen_h - 80))

    parent_x, parent_y, parent_w, parent_h = 0, 0, screen_w, screen_h
    if app and hasattr(app, "winfo_exists") and app.winfo_exists():
        try:
            app.update_idletasks()
            parent_x = app.winfo_rootx()
            parent_y = app.winfo_rooty()
            parent_w = app.winfo_width()
            parent_h = app.winfo_height()
        except Exception:
            pass

    if parent_w > 100 and parent_h > 100:
        x = parent_x + (parent_w - width) // 2
        y = parent_y + (parent_h - height) // 2
    else:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

    x = max(10, min(x, screen_w - width - 10))
    y = max(10, min(y, screen_h - height - 40))
    win.geometry(f"{width}x{height}+{x}+{y}")
    win.minsize(min_width, min_height)
    if app and hasattr(app, "lift"):
        win.transient(app)
        win.lift(app)


# ── Custom Yes/No Confirm Dialog ───────────────────────────────


class CustomMessageBox(ctk.CTkToplevel):
    """Custom premium dark-styled confirm / alert dialog."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkToplevel,
        title: str,
        message: str,
        yes_text: str = "确定",
        no_text: str = "取消",
    ):
        super().__init__(parent)
        self.parent = parent
        self.result = False

        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=C.get("background", "#1e1e1e"))

        position_dialog(self, parent, 440, 210, 440, 210)
        self.transient(parent)
        self.grab_set()

        try:
            self.wm_iconbitmap("")
        except Exception:
            pass

        card = ctk.CTkFrame(
            self,
            fg_color=C.get("card", "#2d2d30"),
            corner_radius=8,
            border_width=1,
            border_color=C.get("border", "#3c3c3c"),
        )
        card.pack(fill="both", expand=True, padx=10, pady=10)

        lbl = ctk.CTkLabel(
            card,
            text=message,
            font=F.get("body", ("Segoe UI", 12)),
            text_color=C.get("text_primary", "#cccccc"),
            wraplength=380,
            justify="left",
            anchor="nw",
        )
        lbl.pack(fill="both", expand=True, padx=22, pady=(18, 10))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom", padx=20, pady=(0, 16))

        if no_text:
            ctk.CTkButton(
                btn_row,
                text=no_text,
                command=self._on_no,
                font=F.get("button", ("Segoe UI", 12)),
                fg_color=C.get("toolbar_bg", "#2d2d30"),
                text_color=C.get("text_secondary", "#969696"),
                hover_color=C.get("toolbar_hover", "#37373d"),
                width=88,
                corner_radius=6,
            ).pack(side="right", padx=4)

        ctk.CTkButton(
            btn_row,
            text=yes_text,
            command=self._on_yes,
            font=F.get("button", ("Segoe UI", 12)),
            fg_color=C.get("primary", "#0e639c"),
            text_color=C.get("text_on_primary", "#ffffff"),
            hover_color=C.get("primary_hover", "#1a8ad4"),
            width=88,
            corner_radius=6,
        ).pack(side="right", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._on_no)
        self.wait_window()

    def _on_yes(self) -> None:
        self.result = True
        self.destroy()

    def _on_no(self) -> None:
        self.result = False
        self.destroy()


# ── Custom Input Dialog ────────────────────────────────────────


class CustomInputDialog(ctk.CTkToplevel):
    """Custom premium dark-styled input dialog."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkToplevel,
        title: str,
        message: str,
        default_value: str = "",
        placeholder: str = "",
    ):
        super().__init__(parent)
        self.parent = parent
        self.result: Optional[str] = None

        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=C.get("background", "#1e1e1e"))

        position_dialog(self, parent, 440, 220, 440, 220)
        self.transient(parent)
        self.grab_set()

        try:
            self.wm_iconbitmap("")
        except Exception:
            pass

        card = ctk.CTkFrame(
            self,
            fg_color=C.get("card", "#2d2d30"),
            corner_radius=8,
            border_width=1,
            border_color=C.get("border", "#3c3c3c"),
        )
        card.pack(fill="both", expand=True, padx=10, pady=10)

        lbl = ctk.CTkLabel(
            card,
            text=message,
            font=F.get("body", ("Segoe UI", 12)),
            text_color=C.get("text_primary", "#cccccc"),
            wraplength=380,
            justify="center",
        )
        lbl.pack(fill="x", padx=16, pady=(16, 12))

        self.entry = ctk.CTkEntry(
            card,
            fg_color=C.get("entry_bg", "#252526"),
            text_color=C.get("text_primary", "#cccccc"),
            border_color=C.get("border", "#3c3c3c"),
            font=F.get("body", ("Segoe UI", 12)),
            placeholder_text=placeholder,
            corner_radius=6,
            height=34,
        )
        self.entry.pack(fill="x", padx=24, pady=(0, 16))
        if default_value:
            self.entry.insert(0, default_value)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._on_ok())

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="取消",
            command=self._on_cancel,
            font=F.get("button", ("Segoe UI", 12)),
            fg_color=C.get("toolbar_bg", "#2d2d30"),
            text_color=C.get("text_secondary", "#969696"),
            hover_color=C.get("toolbar_hover", "#37373d"),
            width=88,
            corner_radius=6,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            btn_row,
            text="确定",
            command=self._on_ok,
            font=F.get("button", ("Segoe UI", 12)),
            fg_color=C.get("primary", "#0e639c"),
            text_color=C.get("text_on_primary", "#ffffff"),
            hover_color=C.get("primary_hover", "#1a8ad4"),
            width=88,
            corner_radius=6,
        ).pack(side="right", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_window()

    def _on_ok(self) -> None:
        self.result = self.entry.get()
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


# ── Helper functions ───────────────────────────────────────────


def ask_yes_no(
    parent: ctk.CTk | ctk.CTkToplevel,
    title: str,
    message: str,
    yes_text: str = "确定",
    no_text: str = "取消",
) -> bool:
    """Helper function to show a custom Yes/No confirm dialog."""
    dialog = CustomMessageBox(parent, title, message, yes_text=yes_text, no_text=no_text)
    return dialog.result


def show_info(parent: ctk.CTk | ctk.CTkToplevel, title: str, message: str) -> None:
    """Helper function to show a custom Info dialog."""
    CustomMessageBox(parent, title, message, yes_text="确定", no_text="")


def prompt_input(
    parent: ctk.CTk | ctk.CTkToplevel,
    title: str,
    message: str,
    default_value: str = "",
    placeholder: str = "",
) -> Optional[str]:
    """Helper function to prompt user for text input in a styled dark dialog."""
    dialog = CustomInputDialog(parent, title, message, default_value=default_value, placeholder=placeholder)
    return dialog.result
