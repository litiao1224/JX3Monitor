# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Logging setup.

Provides a consistent logging configuration across the application.
升级：TimedRotatingFileHandler（每日滚动7天）+ 控制台仅WARNING+ + 未捕获异常自动记录。
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
import traceback
from pathlib import Path
from typing import Optional

LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "jx3_monitor.log"
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_logger: Optional[logging.Logger] = None


def setup_logger(
    name: str = "jx3_monitor",
    log_dir: Optional[Path] = None,
    level: int = DEFAULT_LOG_LEVEL,
    console: bool = True,
) -> logging.Logger:
    """Configure and return the application logger.

    - 文件处理器：每天午夜滚动，保留 7 天，DEBUG+ 全量记录
    - 控制台处理器：仅输出 WARNING+，减少终端噪音
    - 自动注册 sys.excepthook，将未捕获异常写入日志
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # 根 logger 设为 DEBUG，由 handler 各自过滤
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── 控制台处理器：WARNING+ ──
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.WARNING)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    # ── 文件处理器：每日滚动，保留 7 天，DEBUG+ ──
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.TimedRotatingFileHandler(
            log_dir / LOG_FILE_NAME,
            when="midnight",
            backupCount=7,
            encoding="utf-8",
            delay=True,  # 有日志时才创建文件
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    _logger = logger

    # ── 注册未捕获异常处理器 ──
    _install_excepthook(logger)

    return logger


def _install_excepthook(logger: logging.Logger) -> None:
    """将未捕获异常（非 KeyboardInterrupt）写入日志。"""
    _orig_excepthook = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            _orig_excepthook(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "未捕获异常：",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = _excepthook


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get the application logger or create a child logger."""
    if _logger is None:
        return setup_logger()
    if name:
        return _logger.getChild(name)
    return _logger


def reset_logger() -> None:
    """重置日志（仅用于测试）。"""
    global _logger
    if _logger is not None:
        _logger.handlers.clear()
        _logger = None
