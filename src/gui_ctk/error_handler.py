# -*- coding: utf-8 -*-
"""小鹦鹉记账 - 统一 UI 错误处理装饰器

用法：
    from src.gui_ctk.error_handler import handle_ui_error

    @handle_ui_error("导出失败")
    def export_data(self) -> None:
        ...

设计原则：
- 按异常类型给用户友好的中文提示
- 所有异常都写入结构化日志（含完整 traceback）
- 不影响控制流（默认不 reraise）
"""
from __future__ import annotations

import functools
import logging
from tkinter import messagebox
from typing import Callable, TypeVar

_T = TypeVar("_T")

logger = logging.getLogger("jx3_monitor.ui_error")


def handle_ui_error(
    title: str = "操作失败",
    reraise: bool = False,
    show_detail: bool = True,
) -> Callable:
    """UI 操作错误处理装饰器（仅用于绑定到 self 的方法）。

    Args:
        title:       messagebox 标题
        reraise:     是否在弹窗后重新抛出异常（调试用）
        show_detail: 是否在弹窗中显示异常详情（生产环境建议 True）
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                return fn(self, *args, **kwargs)
            except FileNotFoundError as e:
                msg = f"文件或目录不存在：\n{e.filename}"
                logger.warning("[%s] FileNotFoundError: %s", fn.__qualname__, e)
                messagebox.showwarning(title, msg)
            except PermissionError as e:
                msg = f"权限不足，无法访问：\n{e.filename}"
                logger.error("[%s] PermissionError: %s", fn.__qualname__, e)
                messagebox.showerror(title, msg)
            except IsADirectoryError as e:
                msg = f"目标是一个目录，不是文件：\n{e.filename}"
                logger.error("[%s] IsADirectoryError: %s", fn.__qualname__, e)
                messagebox.showerror(title, msg)
            except OSError as e:
                msg = f"文件系统错误：{e.strerror}"
                if e.filename:
                    msg += f"\n{e.filename}"
                logger.error("[%s] OSError: %s", fn.__qualname__, e)
                messagebox.showerror(title, msg)
            except ValueError as e:
                msg = f"数据格式错误：{e}"
                logger.warning("[%s] ValueError: %s", fn.__qualname__, e)
                messagebox.showwarning(title, msg)
            except Exception as e:
                logger.exception("[%s] 未处理异常", fn.__qualname__)
                if show_detail:
                    msg = f"发生意外错误：{type(e).__name__}: {e}\n\n详情已记录到日志文件。"
                else:
                    msg = "发生意外错误，详情已记录到日志文件。"
                messagebox.showerror(title, msg)
                if reraise:
                    raise
        return wrapper
    return decorator


def handle_thread_error(title: str = "后台任务失败") -> Callable:
    """后台线程错误处理装饰器（用于 threading.Thread 的 target 函数）。

    发生异常时通过 app.queue 发送错误消息到主线程（而非直接弹窗）。
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                return fn(self, *args, **kwargs)
            except Exception as e:
                logger.exception("[thread:%s] 未处理异常", fn.__qualname__)
                # 通过 queue 将错误推送到主线程
                if hasattr(self, "queue"):
                    self.queue.put(("error", {"title": title, "message": str(e)}))
        return wrapper
    return decorator
