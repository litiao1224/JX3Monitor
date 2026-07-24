# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Main GUI application.

Thin wrapper that delegates to the CustomTkinter GUI module, with the legacy
Tkinter module kept as a fallback.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_gui() -> Path:
    """Locate the CustomTkinter GUI entry file."""
    candidates = []
    gui_names = ["jx3_click_monitor_gui_ctk.py"]

    # 1. _MEIPASS (PyInstaller frozen)
    if getattr(sys, "_MEIPASS", None):
        candidates.extend(Path(sys._MEIPASS) / name for name in gui_names)
        # Also check the directory containing the exe
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(exe_dir / name for name in gui_names)
        # Also check _internal (PyInstaller 6.x stores bundled files here)
        internal_dir = exe_dir / "_internal"
        if internal_dir.exists():
            candidates.extend(internal_dir / name for name in gui_names)

    # 2. Project root (development)
    project_root = Path(__file__).resolve().parent.parent.parent
    candidates.extend(project_root / name for name in gui_names)

    # 3. Same directory as src/
    src_root = Path(__file__).resolve().parent.parent
    candidates.extend(src_root / name for name in gui_names)

    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"找不到 GUI 入口文件，已尝试:\n" +
        "\n".join(str(p) for p in candidates)
    )


def run_gui(config=None):
    """Load and run the GUI application."""
    gui_path = _find_gui()

    # Inject the gui file's directory into sys.path so it can import jx3_click_monitor
    gui_dir = str(gui_path.parent)
    if gui_dir not in sys.path:
        sys.path.insert(0, gui_dir)

    # Load the module dynamically
    import importlib.util
    spec = importlib.util.spec_from_file_location("jx3_gui", gui_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # The original module has a main() function that runs the app
    return module.main()
