# -*- coding: utf-8 -*-
"""Custom CTk table widget replacing ttk.Treeview with full CTk styling."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import customtkinter as ctk

# ── Global Tkinter safety patch for focus callbacks on destroyed widgets ──
_orig_focus_set = tk.Misc.focus_set
def _safe_focus_set(self: tk.Misc) -> None:
    try:
        if hasattr(self, "winfo_exists") and not self.winfo_exists():
            return
        _orig_focus_set(self)
    except tk.TclError as err:
        if "bad window path name" in str(err) or "invalid command name" in str(err):
            return
        raise
tk.Misc.focus_set = _safe_focus_set

_orig_focus_force = getattr(tk.Misc, "focus_force", None)
if _orig_focus_force:
    def _safe_focus_force(self: tk.Misc) -> None:
        try:
            if hasattr(self, "winfo_exists") and not self.winfo_exists():
                return
            _orig_focus_force(self)
        except tk.TclError as err:
            if "bad window path name" in str(err) or "invalid command name" in str(err):
                return
            raise
    tk.Misc.focus_force = _safe_focus_force

# Type for a row identifier
RowId = int | str


class CTkTable(ctk.CTkFrame):
    """A fully CTk-styled table widget with sortable headers, selection,
    alternating row colors, and scroll support.
    Uses ttk.Treeview internally for high performance.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        columns: list[dict[str, Any]] | None = None,
        *,
        row_height: int = 32,
        header_height: int = 32,
        select_mode: str = "browse",
        show_header: bool = True,
        header_font: ctk.CTkFont | tuple | None = None,
        body_font: ctk.CTkFont | tuple | None = None,
        show_scrollbars: bool | None = None,
        show_vsb: bool = True,
        show_hsb: bool = False,
        **kwargs,
    ):
        super().__init__(master, **kwargs)

        self._columns = columns or []
        self._row_height = row_height
        self._select_mode = select_mode
        self._show_header = show_header
        
        try:
            from src.gui_ctk.themes import COLORS, FONTS
            self._bg_header = COLORS.get("table_header", "#18181b")
            self._fg_header = COLORS.get("table_header_text", "#f0f0f3")
            self._bg_row_even = COLORS.get("card", "#1c1c20")
            self._bg_row_odd = COLORS.get("card_alt", "#212126")
            self._bg_selected = COLORS.get("table_selected", "#2563eb")
            self._fg_selected = COLORS.get("table_selected_text", "#ffffff")
            self._fg_normal = COLORS.get("text_secondary", "#a1a1aa")
            self._border_color = COLORS.get("border", "#27272a")
        except Exception:
            self._bg_header = "#18181b"
            self._fg_header = "#f0f0f3"
            self._bg_row_even = "#1c1c20"
            self._bg_row_odd = "#212126"
            self._bg_selected = "#2563eb"
            self._fg_selected = "#ffffff"
            self._fg_normal = "#a1a1aa"
            self._border_color = "#27272a"

        self._col_key_fn: dict[str, Callable] = {}
        self._sort_col: str | None = None
        self._sort_reverse: bool = False
        self._row_bindings: dict[str, Callable] = {}

        self._next_seq = 0
        self._rows: dict[RowId, dict] = {}
        
        # CustomTkinter disables native tkinter DPI scaling and handles it manually.
        # We MUST apply the scaling factor to standard ttk widgets so they don't look tiny.
        # AND we must use NEGATIVE font sizes so Tkinter treats them as pixels, preventing
        # double-scaling (CustomTkinter manual scaling + Windows point scaling).
        scaling = self._get_widget_scaling()
        scaled_row_height = int(row_height * scaling)

        # Resolve fonts to ttk-compatible tuples, applying scaling to the size
        def resolve_font(font_obj, default_family="Segoe UI", default_size=14, default_weight=None):
            if font_obj is None:
                size = -int(default_size * scaling)
                if default_weight:
                    return (default_family, size, default_weight)
                return (default_family, size)
            if isinstance(font_obj, tuple):
                family = font_obj[0]
                base_size = font_obj[1] if len(font_obj) > 1 else default_size
                size = -int(abs(base_size) * scaling)
                weight = font_obj[2] if len(font_obj) > 2 else None
                if weight and weight.lower() != "normal":
                    return (family, size, weight)
                return (family, size)
            if hasattr(font_obj, "cget"): # CTkFont
                try:
                    family = font_obj.cget("family")
                    base_size = font_obj.cget("size")
                    size = -int(abs(base_size) * scaling)
                    weight = font_obj.cget("weight")
                    if weight and weight.lower() != "normal":
                        return (family, size, weight)
                    return (family, size)
                except Exception:
                    pass
            size = -int(default_size * scaling)
            if default_weight:
                return (default_family, size, default_weight)
            return (default_family, size)

        ttk_body_font = resolve_font(body_font, "Segoe UI", 14, None)
        ttk_header_font = resolve_font(header_font, "Segoe UI", 14, "bold")
        
        style = ttk.Style(self)
        style.theme_use("default")
        
        style.configure(
            "CTkTable.Treeview",
            background=self._bg_row_even,
            foreground=self._fg_normal,
            fieldbackground=self._bg_row_even,
            borderwidth=0,
            relief="flat",
            rowheight=scaled_row_height,
            font=ttk_body_font
        )
        style.map(
            "CTkTable.Treeview",
            background=[("selected", self._bg_selected)],
            foreground=[("selected", self._fg_selected)],
        )
        
        style.configure(
            "CTkTable.Treeview.Heading",
            background=self._bg_header,
            foreground=self._fg_header,
            borderwidth=0,
            font=ttk_header_font,
            relief="flat",
        )
        style.map(
            "CTkTable.Treeview.Heading",
            background=[("active", "#2C2C2C")],
        )

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(
            self,
            style="CTkTable.Treeview",
            selectmode=select_mode if select_mode != "none" else "none",
            show="headings" if show_header else ""
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        if show_scrollbars is not None:
            show_vsb = show_scrollbars
            show_hsb = show_scrollbars

        self.vsb = ctk.CTkScrollbar(self, orientation="vertical", command=self.tree.yview)
        if show_vsb:
            self.vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=self.vsb.set)

        self.hsb = ctk.CTkScrollbar(self, orientation="horizontal", command=self.tree.xview)
        if show_hsb:
            self.hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=self.hsb.set)

        self.tree.tag_configure("odd", background=self._bg_row_odd)
        self.tree.tag_configure("even", background=self._bg_row_even)

        self._apply_columns()

    def configure_columns(
        self,
        columns: list[dict[str, Any]],
        headings: dict[str, str] | None = None,
        widths: dict[str, int] | None = None,
    ) -> None:
        self._columns = columns
        self.delete_all()
        self._apply_columns()

    def _apply_columns(self):
        col_ids = [c.get("name", c.get("text")) for c in self._columns]
        self.tree.configure(columns=col_ids)
        for c in self._columns:
            cid = c.get("name", c.get("text"))
            self.tree.heading(
                cid, 
                text=c.get("text", cid),
                command=c.get("command") or (lambda col=cid: self.sort_by(col))
            )
            anchor = {"w": "w", "e": "e", "center": "center"}.get(c.get("anchor", "w"), "w")
            self.tree.column(cid, width=c.get("width", 100), anchor=anchor, stretch=True)

    def heading(self, col: str, text: str | None = None, command: Callable | None = None) -> str | None:
        if text is not None:
            self.tree.heading(col, text=text)
        return self.tree.heading(col, "text")

    def column(self, col: str, *, width: int | None = None, anchor: str | None = None) -> None:
        kwargs = {}
        if width is not None:
            kwargs["width"] = width
        if anchor is not None:
            kwargs["anchor"] = {"w": "w", "e": "e", "center": "center"}.get(anchor, "w")
        if kwargs:
            self.tree.column(col, **kwargs)

    def insert(
        self,
        parent: str = "",
        index: str = tk.END,
        *,
        iid: RowId | None = None,
        values: tuple = (),
        tags: tuple[str, ...] = (),
    ) -> RowId:
        if iid is None:
            iid = str(self._next_seq)
            self._next_seq += 1
            
        is_odd = len(self.tree.get_children()) % 2 == 1
        effective_tags = list(tags)
        effective_tags.append("odd" if is_odd else "even")
        
        self.tree.insert(parent, index, iid=iid, values=values, tags=effective_tags)
        self._rows[iid] = {"values": values, "tags": tags}
        return iid

    def delete(self, iid: RowId) -> None:
        if self.exists(iid):
            self.tree.delete(iid)
            self._rows.pop(iid, None)
        self._refresh_stripe_tags()

    def delete_all(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()

    def get_children(self) -> list[RowId]:
        return list(self.tree.get_children())

    def get_selection(self) -> list[RowId]:
        return list(self.tree.selection())

    def selection_set(self, iid: RowId) -> None:
        self.tree.selection_set(iid)

    def focus(self, iid: RowId) -> None:
        self.tree.focus(iid)
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def set(self, iid: RowId, column: str, value: str) -> None:
        self.tree.set(iid, column, value)
        if iid in self._rows:
            col_idx = -1
            for i, c in enumerate(self._columns):
                if c.get("name", c.get("text")) == column:
                    col_idx = i
                    break
            if col_idx >= 0:
                vals = list(self._rows[iid]["values"])
                while len(vals) <= col_idx:
                    vals.append("")
                vals[col_idx] = value
                self._rows[iid]["values"] = tuple(vals)

    def item(self, iid: RowId, option: str | None = None) -> Any:
        if not self.exists(iid):
            return None if option else {}
        if option == "values":
            return self.tree.item(iid, "values")
        if option == "tags":
            return self.tree.item(iid, "tags")
        return self.tree.item(iid)

    def exists(self, iid: RowId) -> bool:
        return self.tree.exists(iid)

    def bind(self, sequence: str | None = None, command: Callable | None = None, add: str | None = None) -> str:
        if sequence in {"<Double-1>", "<Button-3>"}:
            self._row_bindings[sequence] = command
            return self.tree.bind(sequence, self._on_event, add)
        return super().bind(sequence, command, add)

    def _on_event(self, event):
        seq = "<Double-1>" if event.type == tk.EventType.ButtonPress and event.num == 1 else "<Button-3>"
        cmd = self._row_bindings.get(seq)
        if cmd:
            region = self.tree.identify_region(event.x, event.y)
            if region == "cell":
                iid = self.tree.identify_row(event.y)
                if iid:
                    self.tree.selection_set(iid)
                    cmd(event)

    def yview(self, *args) -> str | None:
        return self.tree.yview(*args)

    def set_sort_key(self, col: str, fn: Callable) -> None:
        self._col_key_fn[col] = fn

    def sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        key_fn = self._col_key_fn.get(col)
        
        rows = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children("")]
        
        def sort_key(item):
            val = item[0]
            if key_fn:
                return key_fn(val)
            try:
                return (0, float(str(val).replace(",", "")))
            except (ValueError, AttributeError):
                return (1, str(val))
                
        rows.sort(key=sort_key, reverse=self._sort_reverse)
        
        for idx, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", idx)
            
        self._refresh_stripe_tags()
        self._update_header_indicators()

    def _refresh_stripe_tags(self):
        for idx, iid in enumerate(self.tree.get_children()):
            tags = [t for t in self.tree.item(iid, "tags") if t not in ("odd", "even")]
            tags.append("odd" if idx % 2 == 1 else "even")
            self.tree.item(iid, tags=tags)

    def _update_header_indicators(self):
        for c in self._columns:
            cid = c.get("name", c.get("text"))
            base_text = c.get("text", cid).rstrip(" ▲▼")
            if cid == self._sort_col:
                arrow = " ▼" if self._sort_reverse else " ▲"
                self.tree.heading(cid, text=base_text + arrow)
            else:
                self.tree.heading(cid, text=base_text)

    def set_theme_colors(self, **kwargs):
        pass

# ── Simple pagination / container for label-value pairs ─────────

class CTkPropertyGrid(ctk.CTkFrame):
    """A simple key-value property grid for displaying stats."""

    def __init__(self, master: ctk.CTkBaseClass, columns: int = 4, **kwargs):
        super().__init__(master, **kwargs)
        self._columns = columns
        self._cells: list[ctk.CTkFrame] = []

    def add_card(self, title: str, value_var: ctk.StringVar, color: str = "#242424") -> None:
        """Add a stat card with title and dynamic value."""
        idx = len(self._cells)
        row = idx // self._columns
        col = idx % self._columns

        card = ctk.CTkFrame(self, fg_color=color, corner_radius=8)
        card.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0), pady=(0, 6))
        self.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                      text_color="#F4F4F1").pack(anchor="center", pady=(8, 2))
        ctk.CTkLabel(card, textvariable=value_var, font=ctk.CTkFont(size=16, weight="bold"),
                      text_color="#F4F4F1").pack(anchor="center", pady=(2, 8))

        self._cells.append(card)


# ── Calendar Dropdown ──────────────────────────────────────────

class CalendarDropdown(ctk.CTkToplevel):
    """Inline calendar popup with CTk styling."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        var: ctk.StringVar,
        on_confirm: Callable[[], None] | None = None,
    ):
        super().__init__(master)
        self.var = var
        self.on_confirm = on_confirm
        self.title("")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel() if hasattr(master, "winfo_toplevel") else master)
        self.overrideredirect(True)

        try:
            import datetime
            base = datetime.datetime.strptime(var.get(), "%Y-%m-%d %H:%M:%S")
        except Exception:
            import datetime as dt
            base = dt.datetime.now()

        self._year = base.year
        self._month = base.month
        self._day = base.day
        self._hour = ctk.IntVar(value=base.hour)
        self._minute = ctk.IntVar(value=base.minute)
        self._second = ctk.IntVar(value=base.second)
        self._selected_day = base.day
        self._day_buttons: dict[int, ctk.CTkButton] = {}

        outer = ctk.CTkFrame(self, fg_color="white", corner_radius=8, border_width=1, border_color="#333333")
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        # Navigation
        nav = ctk.CTkFrame(outer, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkButton(nav, text="◀", width=30, command=self._prev_month, fg_color="transparent",
                       text_color="#F4F4F1", hover_color="#303030", border_width=0).pack(side="left")
        self._month_label = ctk.CTkLabel(nav, text="", font=ctk.CTkFont(size=13, weight="bold"),
                                          text_color="#F4F4F1", anchor="center")
        self._month_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(nav, text="▶", width=30, command=self._next_month, fg_color="transparent",
                       text_color="#F4F4F1", hover_color="#303030", border_width=0).pack(side="left")

        # Weekday headers
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=8)
        for wd in ["一", "二", "三", "四", "五", "六", "日"]:
            ctk.CTkLabel(header, text=wd, width=36, anchor="center", text_color="#8E8E86",
                          font=ctk.CTkFont(size=11)).pack(side="left")

        # Day grid
        self._grid_frame = ctk.CTkFrame(outer, fg_color="transparent")
        self._grid_frame.pack(fill="both", padx=8, pady=4)

        # Time picker
        time_frame = ctk.CTkFrame(outer, fg_color="transparent")
        time_frame.pack(fill="x", padx=8, pady=(2, 4))
        import tkinter as tk
        for label, var_, lo, hi in [("时", self._hour, 0, 23), ("分", self._minute, 0, 59), ("秒", self._second, 0, 59)]:
            ctk.CTkLabel(time_frame, text=label, text_color="#C8C8C0").pack(side="left", padx=(4, 0))
            spin = tk.Spinbox(time_frame, from_=lo, to=hi, textvariable=var_, width=4, wrap=True,
                              justify="center", relief="flat", bd=1, highlightthickness=1,
                              highlightbackground="#333333", font=("Microsoft YaHei UI", 10),
                              bg="#111111", fg="#F4F4F1", buttonbackground="#242424")
            spin.pack(side="left", padx=2)

        # Buttons
        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(2, 8))
        ctk.CTkButton(btn_frame, text="今天", command=self._today, width=60, height=28,
                       fg_color="#242424", text_color="#C8C8C0", hover_color="#303030",
                       border_width=0, font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkButton(btn_frame, text="取消", command=self.destroy, width=60, height=28,
                       fg_color="#242424", text_color="#C8C8C0", hover_color="#303030",
                       border_width=0, font=ctk.CTkFont(size=11)).pack(side="right", padx=2)
        ctk.CTkButton(btn_frame, text="确定", command=self._confirm, width=60, height=28,
                       fg_color="#F4F4F1", text_color="#111111", hover_color="#FFFFFF",
                       border_width=0, font=ctk.CTkFont(size=11, weight="bold")).pack(side="right", padx=2)

        self._render_days()
        self.after(50, self._position_near)
        self.after(100, lambda: self.focus_force())
        self.bind("<FocusOut>", self._on_focus_out)

    def _position_near(self) -> None:
        try:
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            wh = self.winfo_height()
        except Exception:
            return
        # Try to get parent widget position
        master = self.master
        try:
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            mh = master.winfo_height()
        except Exception:
            mx, my, mh = 0, 0, 0
        self.update_idletasks()
        sw = self.winfo_reqwidth()
        sh = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = mx
        y = my + mh + 2
        if x + sw > screen_w:
            x = screen_w - sw - 10
        if y + sh > screen_h:
            y = my - sh - 2
        if x < 0:
            x = 10
        if y < 0:
            y = 10
        self.geometry(f"+{x}+{y}")

    def _on_focus_out(self, event=None) -> None:
        try:
            focused = self.focus_get()
            if focused is not None and str(focused).startswith(str(self)):
                return
        except Exception:
            pass
        self.destroy()

    def _render_days(self) -> None:
        import calendar
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._day_buttons.clear()
        self._month_label.configure(text=f"{self._year}年{self._month:02d}月")
        cal = calendar.monthcalendar(self._year, self._month)
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(self._grid_frame, text="", width=36).grid(row=r, column=c)
                else:
                    is_sel = day == self._selected_day
                    bg = "#34332E" if is_sel else ("transparent")
                    fg = "#FFFFFF" if is_sel else "#F4F4F1"
                    hover = "#303030" if not is_sel else "#34332E"
                    b = ctk.CTkButton(
                        self._grid_frame, text=str(day), width=36, height=28,
                        fg_color=bg, text_color=fg, hover_color=hover,
                        border_width=0, corner_radius=4,
                        command=lambda d=day: self._pick_day(d),
                        font=ctk.CTkFont(size=11),
                    )
                    b.grid(row=r, column=c, padx=1, pady=1)
                    self._day_buttons[day] = b

    def _pick_day(self, day: int) -> None:
        self._selected_day = day
        self._render_days()

    def _prev_month(self) -> None:
        import calendar
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self._selected_day = min(self._selected_day, calendar.monthrange(self._year, self._month)[1])
        self._render_days()

    def _next_month(self) -> None:
        import calendar
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self._selected_day = min(self._selected_day, calendar.monthrange(self._year, self._month)[1])
        self._render_days()

    def _today(self) -> None:
        from datetime import datetime
        now = datetime.now()
        self._year, self._month, self._selected_day = now.year, now.month, now.day
        self._hour.set(now.hour)
        self._minute.set(now.minute)
        self._second.set(now.second)
        self._render_days()

    def _confirm(self) -> None:
        from datetime import datetime
        try:
            dt = datetime(self._year, self._month, self._selected_day,
                          int(self._hour.get()), int(self._minute.get()), int(self._second.get()))
        except ValueError as exc:
            import tkinter.messagebox as mb
            mb.showerror("时间无效", str(exc), parent=self)
            return
        self.var.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
        if self.on_confirm:
            self.on_confirm()
        self.destroy()


# ── Custom Round-Corner Context Menu ──────────────────────────

class CTkContextMenu:
    """Dark-styled native popup context menu replacing custom CTkToplevel to avoid Tcl focus errors."""

    def __init__(self, master: tk.Misc, commands: list[tuple[str, Callable]], event: tk.Event):
        menu = tk.Menu(
            master,
            tearoff=0,
            bg="#1E1E22",
            fg="#E0E0E0",
            activebackground="#0E639C",
            activeforeground="#FFFFFF",
            activeborderwidth=0,
            bd=1,
            relief="solid",
            font=("Microsoft YaHei UI", 10),
        )

        for label, cmd in commands:
            if not label or label == "separator":
                menu.add_separator()
            else:
                menu.add_command(label=label, command=cmd)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass
