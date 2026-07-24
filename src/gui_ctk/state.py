# -*- coding: utf-8 -*-
"""小鹦鹉记账 - 应用状态机

使用枚举 + 状态转移表管理 App 的 UI 状态，
替代原有字符串 if/elif 链，防止非法状态转移。

用法：
    from src.gui_ctk.state import AppState, StateMachine

    sm = StateMachine()
    sm.on_transition(lambda old, new: update_ui(new))
    sm.transition(AppState.RECORDING)
"""
from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Callable, Optional

logger = logging.getLogger("jx3_monitor.state")


class AppState(Enum):
    """应用 UI 状态枚举。"""
    IDLE = auto()           # 就绪（初始状态）
    RECORDING = auto()      # 正在监控记录中
    WRITING = auto()        # 等待小退写盘
    READY = auto()          # 结算已就绪，等待入账

    # ── 字符串兼容层（向后兼容旧代码的 set_new_state("idle") 调用）──
    @classmethod
    def from_str(cls, s: str) -> "AppState":
        _MAP = {
            "idle":      cls.IDLE,
            "recording": cls.RECORDING,
            "writing":   cls.WRITING,
            "ready":     cls.READY,
            # 历史别名
            "writing":   cls.WRITING,
        }
        result = _MAP.get(s.lower())
        if result is None:
            logger.warning("未知状态字符串: %r，回退到 IDLE", s)
            return cls.IDLE
        return result

    def to_str(self) -> str:
        return self.name.lower()


# 合法的状态转移表
VALID_TRANSITIONS: dict[AppState, frozenset[AppState]] = {
    AppState.IDLE:      frozenset({AppState.RECORDING}),
    AppState.RECORDING: frozenset({AppState.WRITING, AppState.IDLE}),
    AppState.WRITING:   frozenset({AppState.READY, AppState.IDLE}),
    AppState.READY:     frozenset({AppState.IDLE}),
}

TransitionCallback = Callable[[AppState, AppState], None]


class StateMachine:
    """轻量级状态机，支持转移回调和非法转移警告。"""

    def __init__(self, initial: AppState = AppState.IDLE) -> None:
        self._state = initial
        self._listeners: list[TransitionCallback] = []

    # ── 属性 ──

    @property
    def state(self) -> AppState:
        return self._state

    @property
    def is_idle(self) -> bool:
        return self._state == AppState.IDLE

    @property
    def is_recording(self) -> bool:
        return self._state == AppState.RECORDING

    @property
    def is_writing(self) -> bool:
        return self._state == AppState.WRITING

    @property
    def is_ready(self) -> bool:
        return self._state == AppState.READY

    # ── 监听器 ──

    def on_transition(self, callback: TransitionCallback) -> None:
        """注册状态转移回调。回调参数：(old_state, new_state)。"""
        self._listeners.append(callback)

    def remove_listener(self, callback: TransitionCallback) -> None:
        self._listeners.remove(callback)

    # ── 转移 ──

    def transition(self, new_state: AppState) -> bool:
        """尝试转移到 new_state，返回是否成功。

        非法转移时记录 WARNING 日志并返回 False（不抛出异常，防止崩溃）。
        """
        if new_state == self._state:
            return True  # 幂等：无需转移

        allowed = VALID_TRANSITIONS.get(self._state, frozenset())
        if new_state not in allowed:
            logger.warning(
                "非法状态转移被拦截: %s → %s（允许：%s）",
                self._state.name,
                new_state.name,
                [s.name for s in allowed],
            )
            return False

        old_state = self._state
        self._state = new_state
        logger.debug("状态转移: %s → %s", old_state.name, new_state.name)

        for listener in list(self._listeners):
            try:
                listener(old_state, new_state)
            except Exception:
                logger.exception("状态转移回调异常")

        return True

    def transition_str(self, state_str: str) -> bool:
        """通过字符串名称转移（向后兼容接口）。"""
        return self.transition(AppState.from_str(state_str))

    def force(self, new_state: AppState) -> None:
        """强制设置状态（跳过合法性检查，仅用于初始化/重置）。"""
        old_state = self._state
        self._state = new_state
        logger.debug("强制状态设置: %s → %s", old_state.name, new_state.name)
        for listener in list(self._listeners):
            try:
                listener(old_state, new_state)
            except Exception:
                logger.exception("强制状态转移回调异常")

    def __repr__(self) -> str:
        return f"StateMachine(state={self._state.name})"
