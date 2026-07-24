from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "monitor" / "worker.py"


def monitor_worker_source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_settlement_wait_loop_uses_dedicated_cancel_event() -> None:
    worker = monitor_worker_source()

    assert "self.cancel_wait_event = threading.Event()" in worker
    assert "self.cancel_wait_event.set()" in worker
    assert "self.cancel_wait_event.wait(3.0)" in worker
    assert "self.stop_event.wait(3.0)" not in worker


def test_settlement_wait_cancel_does_not_mark_abandoned() -> None:
    worker = monitor_worker_source()

    assert "reason == \"cancel_wait\"" in worker
    assert "finalize_on_stop = finalize" in worker
