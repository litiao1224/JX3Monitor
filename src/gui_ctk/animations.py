# -*- coding: utf-8 -*-
"""Animation utilities for smooth UI transitions."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk


def fade_in(
    widget: ctk.CTkBaseClass | tk.Widget,
    duration_ms: int = 200,
    steps: int = 10,
    on_complete: Callable | None = None,
) -> None:
    """Fade a toplevel window from transparent to opaque.

    Works only on CTkToplevel / Tk root windows that support
    ``wm_attributes('-alpha', ...)``.
    """
    toplevel = widget.winfo_toplevel()
    if not hasattr(toplevel, "attributes"):
        if on_complete:
            on_complete()
        return

    step_delay = max(1, duration_ms // steps)
    current = [0]

    def _step() -> None:
        current[0] += 1
        alpha = min(1.0, current[0] / steps)
        try:
            toplevel.attributes("-alpha", alpha)
        except Exception:
            pass
        if current[0] < steps:
            toplevel.after(step_delay, _step)
        elif on_complete:
            on_complete()

    try:
        toplevel.attributes("-alpha", 0.0)
    except Exception:
        pass
    toplevel.after(step_delay, _step)


def fade_out(
    widget: ctk.CTkBaseClass | tk.Widget,
    duration_ms: int = 150,
    steps: int = 8,
    on_complete: Callable | None = None,
) -> None:
    """Fade a toplevel window from opaque to transparent."""
    toplevel = widget.winfo_toplevel()
    if not hasattr(toplevel, "attributes"):
        if on_complete:
            on_complete()
        return

    step_delay = max(1, duration_ms // steps)
    current = [steps]

    def _step() -> None:
        current[0] -= 1
        alpha = max(0.0, current[0] / steps)
        try:
            toplevel.attributes("-alpha", alpha)
        except Exception:
            pass
        if current[0] > 0:
            toplevel.after(step_delay, _step)
        elif on_complete:
            on_complete()

    toplevel.after(step_delay, _step)


def slide_in(
    widget: ctk.CTkBaseClass,
    direction: str = "left",
    distance: int = 30,
    duration_ms: int = 200,
    steps: int = 10,
    on_complete: Callable | None = None,
) -> None:
    """Slide a widget into view by adjusting its pack padding.

    This works by temporarily adding extra padding on the entry side
    and animating it to zero. Best used for page host containers.
    """
    step_delay = max(1, duration_ms // steps)
    current = [0]

    def _step() -> None:
        current[0] += 1
        progress = current[0] / steps
        # Ease-out cubic
        t = 1 - (1 - progress) ** 3
        offset = int(distance * (1 - t))
        try:
            if direction == "left":
                widget.pack_configure(padx=(offset, 0))
            elif direction == "right":
                widget.pack_configure(padx=(0, offset))
            elif direction == "top":
                widget.pack_configure(pady=(offset, 0))
            elif direction == "bottom":
                widget.pack_configure(pady=(0, offset))
        except Exception:
            pass
        if current[0] < steps:
            widget.after(step_delay, _step)
        else:
            # Reset to normal padding
            try:
                widget.pack_configure(padx=0, pady=0)
            except Exception:
                pass
            if on_complete:
                on_complete()

    widget.after(1, _step)


def animate_page_transition(
    page_host: ctk.CTkFrame,
    old_page: ctk.CTkFrame | None,
    new_page: ctk.CTkFrame,
    duration_ms: int = 200,
) -> None:
    """Animate switching between two pages inside a host frame.

    The old page is instantly hidden and the new page slides in
    from the right with a subtle fade.
    """
    if old_page is not None:
        old_page.pack_forget()

    new_page.pack(fill="both", expand=True)

    # Slide from right
    slide_in(new_page, direction="left", distance=20, duration_ms=duration_ms)


def hover_glow(
    widget: ctk.CTkBaseClass,
    normal_color: str,
    hover_color: str,
    glow_color: str | None = None,
) -> None:
    """Attach hover color transition to a widget.

    If the widget supports ``configure(border_color=...)``,
    a subtle glow border is applied on hover.
    """
    def on_enter(_event: tk.Event) -> None:
        try:
            widget.configure(fg_color=hover_color)
            if glow_color:
                widget.configure(border_color=glow_color)
        except Exception:
            pass

    def on_leave(_event: tk.Event) -> None:
        try:
            widget.configure(fg_color=normal_color)
            if glow_color:
                widget.configure(border_color=normal_color)
        except Exception:
            pass

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<Leave>", on_leave, add="+")


def pulse_widget(
    widget: ctk.CTkBaseClass,
    color_a: str,
    color_b: str,
    duration_ms: int = 800,
    steps: int = 20,
    repeat: int = 1,
) -> None:
    """Pulse a widget's fg_color between two colors."""
    step_delay = max(1, duration_ms // steps)
    half = steps // 2

    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        return f"#{r:02x}{g:02x}{b:02x}"

    def _lerp(a: int, b: int, t: float) -> int:
        return int(a + (b - a) * t)

    rgb_a = _hex_to_rgb(color_a)
    rgb_b = _hex_to_rgb(color_b)
    iteration = [0]
    current = [0]

    def _step() -> None:
        current[0] += 1
        step_in_cycle = current[0] % (steps + 1)
        if step_in_cycle <= half:
            t = step_in_cycle / half
        else:
            t = 1 - (step_in_cycle - half) / half
        color = _rgb_to_hex(
            _lerp(rgb_a[0], rgb_b[0], t),
            _lerp(rgb_a[1], rgb_b[1], t),
            _lerp(rgb_a[2], rgb_b[2], t),
        )
        try:
            widget.configure(fg_color=color)
        except Exception:
            return

        if current[0] >= steps:
            iteration[0] += 1
            current[0] = 0
            if iteration[0] >= repeat:
                try:
                    widget.configure(fg_color=color_a)
                except Exception:
                    pass
                return

        widget.after(step_delay, _step)

    widget.after(1, _step)
