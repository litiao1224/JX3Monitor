# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Background monitor worker thread."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import jx3_click_monitor as core


class MonitorWorker(threading.Thread):
    def __init__(
        self,
        app: Any,
        session_dir: Path,
        interval: float,
        member_count: int | None,
        personal_subsidy: float | None,
    ):
        super().__init__(daemon=True)
        self.app = app
        self.session_dir = session_dir
        self.interval = interval
        self.member_count = member_count
        self.personal_subsidy = personal_subsidy
        self.stop_event = threading.Event()
        self.cancel_wait_event = threading.Event()
        self.zero_poll_count = 0
        self.finalize_on_stop = True
        self.finish_reason = "settlement"

    def stop(self, finalize: bool = True, reason: str = "settlement") -> None:
        if reason == "cancel_wait":
            self.finish_reason = reason
            self.cancel_wait_event.set()
            return
        self.finalize_on_stop = finalize
        self.finish_reason = reason
        self.stop_event.set()

    def run(self) -> None:
        self.app.post_log(f"开始监控：{self.session_dir}")
        while not self.stop_event.is_set():
            try:
                # Just send a heartbeat/tick to update the status bar without polling the databases
                self.app.post_monitor_progress({"is_recording_tick": True})
            except Exception as exc:  # noqa: BLE001 - GUI should not die silently.
                self.app.post_log(f"监控出错：{exc}")
            self.stop_event.wait(self.interval)
        if not self.finalize_on_stop:
            try:
                meta = core.read_json(self.session_dir / "session_meta.json", {})
                meta["status"] = "abandoned"
                meta["abandoned_at"] = core.now_ts()
                meta["abandoned_label"] = core.ts_label()
                core.write_json(self.session_dir / "session_meta.json", meta)
            except Exception:
                pass
            self.app.post_log("本次记录已放弃，未生成结算，未写入收入统计。")
            self.app.post_recording_reset()
            return
        try:
            attempt = 0
            summary: dict = {}
            while True:
                if self.cancel_wait_event.is_set() or self.finish_reason == "cancel_wait":
                    self.app.post_log("已取消等待聊天数据库写盘，本次不会自动入账。后续可在历史记录中导入本次 Session。")
                    self.app.post_recording_reset()
                    return
                attempt += 1
                summary = core.stop_session(self.session_dir)
                if int(summary.get("total_events") or 0) > 0:
                    break
                self.app.post_writeback_waiting(attempt, self.session_dir)
                if self.cancel_wait_event.wait(3.0):
                    continue
            report = core.extract_settlement(
                self.session_dir,
                member_count=self.member_count,
                self_name="你",
                personal_subsidy_gold=self.personal_subsidy,
                current_jx3_path=Path(self.app.jx3_var.get()),
            )
            self.app.post_status(summary, report)
            self.app.post_log("工资完成结算：本次记录已采集并解析，正在打开结算确认窗口。")
            self.app.post_settlement_ready(self.session_dir, report)
        except Exception as exc:  # noqa: BLE001
            self.app.post_log(f"停止时出错：{exc}")
        finally:
            self.app.post_recording_reset()
