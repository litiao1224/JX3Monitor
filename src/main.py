# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Main entry point (GUI first)."""
import sys
import os
import traceback


def main():
    try:
        # Ensure project root is on sys.path for src imports
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from src.config import AppConfig
        from src.logger import setup_logger
        from pathlib import Path

        config = AppConfig()
        log_dir = Path("logs")
        logger = setup_logger(name="jx3_monitor", log_dir=log_dir)
        logger.info("JX3 Click Monitor starting (GUI mode)")
        logger.info(f"Config: jx3_path={config.jx3_path}, out_dir={config.out_dir}")

        from src.core.session import create_session, list_sessions
        from pathlib import Path

        out_dir = Path(config.out_dir) if config.out_dir else Path("sessions")
        if not out_dir.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created output directory: {out_dir}")

        sessions = list_sessions(out_dir)
        logger.info(f"Found {len(sessions)} existing sessions")

        from src.gui.app import run_gui
        run_gui(config)

    except Exception as exc:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        from tkinter import messagebox
        detail = traceback.format_exc()
        messagebox.showerror(
            "启动失败",
            f"小鹦鹉记账 启动时发生错误：\n\n{exc}\n\n{detail}"
        )
        root.destroy()
        sys.exit(1)


if __name__ == "__main__":
    main()
