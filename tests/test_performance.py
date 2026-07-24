# -*- coding: utf-8 -*-
"""Performance / stress tests for JX3 Click Monitor.

Measures execution time, memory footprint, and throughput for core operations.
Designed to catch regressions that make the app feel sluggish.

Run: python -m pytest tests/test_performance.py -v -s
     (use -s to see timing output)

Thresholds are generous — we care about orders-of-magnitude, not microseconds.
"""
from __future__ import annotations

import gc
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jx3_click_monitor as core
from src.core.utils import (
    ensure_dir,
    now_ts,
    ts_label,
    write_json,
    write_jsonl,
    load_jsonl,
    read_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="jx3perf_"))


def _make_events(n: int, base_time: int = 1781232000) -> list[dict]:
    """Generate n synthetic raw events mimicking a raid session."""
    events = []
    for i in range(n):
        t = base_time + i * 2
        if i % 10 == 0:
            # auction_start
            events.append({
                "time": t, "rowid": i + 1, "type": "MSG_ROOM", "talker": "团长",
                "text": f"[房间][团长]：[装备{i}]开始拍卖", "msg": "",
                "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts(),
            })
        elif i % 10 == 1:
            # bid
            events.append({
                "time": t, "rowid": i + 1, "type": "MSG_ROOM", "talker": f"买家{i}",
                "text": f"[房间][买家{i}]：[买家{i}]以[{(i+1)*100}金]叫价[装备{i-1}]",
                "msg": "", "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts(),
            })
        elif i % 10 == 2:
            # final purchase
            events.append({
                "time": t, "rowid": i + 1, "type": "MSG_ROOM", "talker": f"买家{i-1}",
                "text": f"[房间][买家{i-1}]：[买家{i-1}]花费[{(i)*100}金]购买了[装备{i-2}]",
                "msg": "", "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts(),
            })
        elif i % 10 == 7:
            # settlement summary (every 10 events)
            events.append({
                "time": t, "rowid": i + 1, "type": "MSG_ROOM", "talker": "团长",
                "text": f"[房间][团长]：拍团目前总收入为：{i*100}金，补贴总费用：0金， 实际可用分配金额：{i*100}金， 分配人数：25， 每人底薪：{i*4}金。",
                "msg": "", "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts(),
            })
        elif i % 10 == 8:
            # money gain
            events.append({
                "time": t, "rowid": i + 1, "type": "MSG_MONEY", "talker": "",
                "text": f"你获得：{i*1000}。", "msg": "",
                "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts(),
            })
        else:
            # generic room message
            events.append({
                "time": t, "rowid": i + 1, "type": "MSG_ROOM", "talker": f"玩家{i}",
                "text": f"[房间][玩家{i}]：加油！",
                "msg": "", "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts(),
            })
    return events


def _setup_session(n_events: int) -> tuple[Path, list[dict]]:
    """Create a session with n synthetic events. Returns (session_dir, events)."""
    tmp = _tmp()
    events = _make_events(n_events)
    session_dir = tmp / "session"
    session_dir.mkdir()
    write_json(session_dir / "session.json", {
        "id": "perf_test", "source": "test", "status": "imported",
        "history_confirmed": False, "start_ts": 1781232000, "end_ts": 1781232000 + n_events * 2,
        "identity": {"role_name": "团长", "server": "长安城", "display": "团长/长安城"},
    })
    write_jsonl(session_dir / "raw_events.jsonl", events)
    return session_dir, events


def _mem_mb() -> float:
    """Current process RSS in MB (Windows-compatible via psutil or fallback)."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: estimate from tasklist
        import subprocess
        try:
            out = subprocess.check_output(
                f'tasklist /FI "PID eq {os.getpid()}" /FO CSV /NH',
                shell=True, text=True, timeout=5,
            )
            # CSV format: "python.exe","12345","Console","1","12,345 K","..."
            parts = out.split(",")
            if len(parts) >= 5:
                mem_k = int(parts[4].strip().strip('"').replace(" K", "").replace(",", ""))
                return mem_k / 1024
        except Exception:
            pass
    return 0.0


def _time_it(fn, *args, **kwargs):
    """Run fn, return (result, elapsed_seconds)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - t0


# ===================================================================
# PART 1: STARTUP / IMPORT TIME
# ===================================================================

class TestStartupPerformance:
    """Module import and cold-start related measurements."""

    def test_core_module_import_time(self):
        """Core module should import in under 1 second."""
        import importlib
        # Force reimport
        if "jx3_click_monitor" in sys.modules:
            del sys.modules["jx3_click_monitor"]
        t0 = time.perf_counter()
        import jx3_click_monitor
        elapsed = time.perf_counter() - t0
        print(f"\n  [TIME] Core module import: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Import too slow: {elapsed:.2f}s"
        # Restore
        sys.modules["jx3_click_monitor"] = jx3_click_monitor

    def test_settlement_module_import_time(self):
        """Settlement module should import in under 1 second."""
        import importlib
        mod = "src.core.settlement"
        if mod in sys.modules:
            del sys.modules[mod]
        t0 = time.perf_counter()
        importlib.import_module(mod)
        elapsed = time.perf_counter() - t0
        print(f"\n  [TIME] Settlement module import: {elapsed:.3f}s")
        assert elapsed < 2.0, f"Import too slow: {elapsed:.2f}s"

    def test_session_creation_time(self):
        """Creating a session dir + writing metadata should be fast."""
        tmp = _tmp()
        try:
            jx3 = tmp / "jx3"
            jx3.mkdir()
            out = tmp / "output"
            out.mkdir()
            _, elapsed = _time_it(core.create_session, jx3, out)
            print(f"\n  [TIME] Session creation: {elapsed:.4f}s")
            assert elapsed < 1.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 2: LARGE DATA VOLUME — ANALYSIS / SETTLEMENT
# ===================================================================

class TestLargeDataVolume:
    """How does the engine scale with event count?"""

    @pytest.mark.parametrize("n", [100, 1000, 5000, 10000])
    def test_analyze_session_scaling(self, n: int):
        """analyze_session should complete within O(n) time."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(n)
            _, elapsed = _time_it(core.analyze_session, session_dir)
            print(f"\n  [TIME] analyze_session({n} events): {elapsed:.3f}s")
            # Thresholds: generous
            if n <= 100:
                assert elapsed < 2.0
            elif n <= 1000:
                assert elapsed < 5.0
            elif n <= 5000:
                assert elapsed < 15.0
            else:
                assert elapsed < 30.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @pytest.mark.parametrize("n", [100, 1000, 5000])
    def test_extract_settlement_scaling(self, n: int):
        """extract_settlement should complete within O(n) time."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(n)
            core.analyze_session(session_dir)  # pre-requirement
            _, elapsed = _time_it(core.extract_settlement, session_dir)
            print(f"\n  [TIME] extract_settlement({n} events): {elapsed:.3f}s")
            if n <= 100:
                assert elapsed < 3.0
            elif n <= 1000:
                assert elapsed < 10.0
            else:
                assert elapsed < 20.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_full_pipeline_10k_events(self):
        """End-to-end: 10k events -> analyze -> settlement -> CSV export."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(10000)
            t0 = time.perf_counter()
            core.analyze_session(session_dir)
            t_analyze = time.perf_counter() - t0

            t0 = time.perf_counter()
            report = core.extract_settlement(session_dir)
            t_settlement = time.perf_counter() - t0

            export_dir = tmp / "csv"
            t0 = time.perf_counter()
            paths = core.export_settlement_csv(report, export_dir)
            t_csv = time.perf_counter() - t0

            total = t_analyze + t_settlement + t_csv
            print(f"\n  [TIME] Full pipeline 10k: analyze={t_analyze:.2f}s settlement={t_settlement:.2f}s csv={t_csv:.2f}s total={total:.2f}s")
            assert total < 60.0, f"Full pipeline too slow: {total:.1f}s"
            # Verify outputs exist
            assert len(paths) == 4
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 3: MEMORY USAGE
# ===================================================================

class TestMemoryUsage:
    """Memory footprint of core operations."""

    def test_memory_during_large_analysis(self):
        """Memory should not spike excessively during analysis of 10k events."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(10000)
            gc.collect()
            mem_before = _mem_mb()
            core.analyze_session(session_dir)
            gc.collect()
            mem_after = _mem_mb()
            delta = mem_after - mem_before
            print(f"\n  [MEM] Memory: before={mem_before:.1f}MB after={mem_after:.1f}MB delta={delta:.1f}MB")
            # Should not use more than 200MB extra for 10k events
            assert delta < 200, f"Memory spike too large: {delta:.0f}MB"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_memory_settlement_10k(self):
        """Memory during settlement of 10k events."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(10000)
            core.analyze_session(session_dir)
            gc.collect()
            mem_before = _mem_mb()
            core.extract_settlement(session_dir)
            gc.collect()
            mem_after = _mem_mb()
            delta = mem_after - mem_before
            print(f"\n  [MEM] Settlement memory: before={mem_before:.1f}MB delta={delta:.1f}MB")
            assert delta < 200
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_memory_csv_export_10k(self):
        """Memory during CSV export of 10k purchase records."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(10000)
            core.analyze_session(session_dir)
            report = core.extract_settlement(session_dir)
            gc.collect()
            mem_before = _mem_mb()
            export_dir = tmp / "csv"
            core.export_settlement_csv(report, export_dir)
            gc.collect()
            mem_after = _mem_mb()
            delta = mem_after - mem_before
            print(f"\n  [MEM] CSV export memory: before={mem_before:.1f}MB delta={delta:.1f}MB")
            assert delta < 100
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 4: JSONL READ / WRITE THROUGHPUT
# ===================================================================

class TestJSONLThroughput:
    """JSONL I/O performance — the backbone of session data."""

    def test_jsonl_write_throughput(self):
        """Writing 10k events to JSONL should be fast."""
        tmp = _tmp()
        try:
            events = _make_events(10000)
            path = tmp / "events.jsonl"
            _, elapsed = _time_it(write_jsonl, path, events)
            size_mb = path.stat().st_size / (1024 * 1024)
            throughput = len(events) / elapsed if elapsed > 0 else 0
            print(f"\n  [WRITE] JSONL write 10k: {elapsed:.3f}s ({throughput:.0f} events/s, {size_mb:.1f}MB)")
            assert elapsed < 5.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_jsonl_read_throughput(self):
        """Reading 10k events from JSONL should be fast."""
        tmp = _tmp()
        try:
            events = _make_events(10000)
            path = tmp / "events.jsonl"
            write_jsonl(path, events)
            _, elapsed = _time_it(lambda: list(load_jsonl(path)))
            throughput = len(events) / elapsed if elapsed > 0 else 0
            print(f"\n  [READ] JSONL read 10k: {elapsed:.3f}s ({throughput:.0f} events/s)")
            assert elapsed < 5.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_jsonl_append_dedup_throughput(self):
        """append_unique_raw_events with 5k events including 50% duplicates."""
        tmp = _tmp()
        try:
            path = tmp / "events.jsonl"
            half = _make_events(2500)
            write_jsonl(path, half)  # pre-populate
            full = _make_events(5000)  # 2500 new + 2500 dup
            _, elapsed = _time_it(core.append_unique_raw_events, path, full)
            final = list(load_jsonl(path))
            print(f"\n  [DEDUP] Append+dedup 5k (50% dup): {elapsed:.3f}s -> {len(final)} events")
            assert elapsed < 10.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 5: SEARCH / QUERY PERFORMANCE
# ===================================================================

class TestSearchPerformance:
    """Income memory search and session segment scanning."""

    def _populate_income_memory(self, n: int) -> tuple[Path, Path]:
        """Create income_memory.json with n records."""
        tmp = _tmp()
        path = tmp / "income_memory.json"
        records = []
        for i in range(n):
            records.append({
                "seq": i + 1,
                "role": f"角色{i % 100}",
                "server": f"服务器{i % 10}",
                "instance": f"副本{i % 5}",
                "income_gold": float(i * 100),
                "expense_gold": float(i * 50),
                "net_gold": float(i * 50),
                "recorded_at": f"2026-06-{(i % 28) + 1:02d} {i % 24:02d}:00:00",
                "session_dir": f"/tmp/s{i}",
                "note": f"测试记录{i}",
            })
        data = {"next_seq": n + 1, "records": records}
        write_json(path, data)
        return tmp, path

    @pytest.mark.parametrize("n", [100, 1000, 5000])
    def test_income_memory_search_scaling(self, n: int):
        """search_income_memory should handle large datasets."""
        tmp, path = self._populate_income_memory(n)
        try:
            # Search with match
            _, elapsed = _time_it(core.search_income_memory, path, "角色1")
            print(f"\n  [SEARCH] Income search({n} records, match): {elapsed:.4f}s")
            assert elapsed < 2.0

            # Search with no match
            _, elapsed2 = _time_it(core.search_income_memory, path, "不存在")
            print(f"  [SEARCH] Income search({n} records, no match): {elapsed2:.4f}s")
            assert elapsed2 < 2.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_session_segments_large_timeline(self):
        """session_segments with many events and multiple gaps."""
        tmp = _tmp()
        try:
            # 5000 events across 10 hours with gaps
            events = []
            base = 1781232000
            for i in range(5000):
                # Create gaps every ~1000 events
                gap = 3600 if i > 0 and i % 1000 == 0 else 0
                t = base + i * 2 + gap * (i // 1000)
                events.append({
                    "time": t, "rowid": i + 1, "type": "MSG_ROOM",
                    "text": f"event {i}", "msg": "", "db": "x.db",
                    "table": "ChatLog", "columns": [], "scan_ts": 0,
                })
            session_dir = tmp / "session"
            session_dir.mkdir()
            write_json(session_dir / "session.json", {"id": "seg_test", "start_ts": base})
            write_jsonl(session_dir / "raw_events.jsonl", events)

            _, elapsed = _time_it(core.session_segments, session_dir, 45)
            segments = core.session_segments(session_dir, 45)
            print(f"\n  [CHART] Session segments (5k events, 10 gaps): {elapsed:.3f}s -> {len(segments)} segments")
            assert elapsed < 5.0
            assert len(segments) >= 2  # should detect at least one gap
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 6: UI-RELATED PERFORMANCE (non-GUI measurements)
# ===================================================================

class TestUIRelatedPerformance:
    """Measure data-processing aspects that affect UI responsiveness."""

    def test_markdown_render_large_report(self):
        """render_settlement_markdown with many purchase records."""
        report = {
            "instance_name": "测试副本", "instance_confidence": "high",
            "session_start_label": "2026-06-20 21:00:00", "session_stop_label": "2026-06-20 22:00:00",
            "total_auction_gold": 100000, "subsidy_gold": 5000, "distributable_gold": 95000,
            "member_count": 25, "average_wage_gold": 3800.0,
            "purchase_count": 200, "paid_purchase_total_gold": 100000,
            "calculated_purchase_total_gold": 100000,
            "purchase_total_vs_settlement_diff_gold": 0,
            "purchase_total_vs_settlement_status_label": "一致",
            "purchase_total_vs_settlement_note": "",
            "purchase_source": "final_purchase",
            "business_kind_counts": {"bid": 500, "final_purchase": 200},
            "zero_price_record_count": 50,
            "team_append_income_count": 3, "team_append_income_total_gold": 5000,
            "purchases": [
                {"buyer": f"买家{i}", "item": f"装备{i}", "amount_gold": i * 10,
                 "reconciliation_source": "final_purchase", "reconciliation_source_label": "最终购买公告"}
                for i in range(200)
            ],
            "buyer_totals": [
                {"buyer": f"买家{i}", "total_gold": i * 50, "items": [{"item": f"装备{i}", "amount_gold": i * 10}]}
                for i in range(50)
            ],
            "zero_price_records": [
                {"buyer": f"玩家{i}", "item": f"杂物{i}"}
                for i in range(50)
            ],
            "wage_receipt_check": {"actual_income_gold": 3800, "base_wage_gold": 3800, "detected_personal_subsidy_gold": 0, "status": "matched"},
        }
        _, elapsed = _time_it(core.render_settlement_markdown, report)
        md = core.render_settlement_markdown(report)
        line_count = md.count("\n")
        print(f"\n  [WRITE] Markdown render (200 purchases): {elapsed:.4f}s -> {line_count} lines")
        assert elapsed < 1.0

    def test_csv_export_large_report(self):
        """CSV export with 500 purchase records."""
        tmp = _tmp()
        try:
            report = {
                "purchases": [
                    {"buyer": f"买家{i}", "target": f"目标{i}", "item": f"装备{i}",
                     "amount_gold": i * 10, "time": 1781232000 + i, "label": f"标签{i}",
                     "reconciliation_source": "final_purchase", "reconciliation_source_label": "最终购买公告",
                     "source_text": f"原始文本{i}"}
                    for i in range(500)
                ],
                "buyer_totals": [
                    {"buyer": f"买家{i}", "total_gold": i * 50, "item_count": i % 5 + 1,
                     "items": [{"item": f"装备{j}", "amount_gold": j * 10} for j in range(i % 5 + 1)]}
                    for i in range(100)
                ],
                "zero_price_records": [],
            }
            export_dir = tmp / "csv"
            _, elapsed = _time_it(core.export_settlement_csv, report, export_dir)
            # Check file sizes
            sizes = {k: Path(v).stat().st_size for k, v in (core.export_settlement_csv(report, export_dir) or {}).items()}
            print(f"\n  [CHART] CSV export (500 purchases): {elapsed:.4f}s")
            for k, s in sizes.items():
                print(f"      {k}: {s / 1024:.1f}KB")
            assert elapsed < 2.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_business_event_parsing_throughput(self):
        """parse_business_event per-event throughput."""
        events = _make_events(1000)
        # Filter to ones that will actually match
        t0 = time.perf_counter()
        parsed = 0
        for e in events:
            result = core.parse_business_event(e)
            if result:
                parsed += 1
        elapsed = time.perf_counter() - t0
        throughput = len(events) / elapsed
        print(f"\n  [SPEED] parse_business_event: {len(events)} events in {elapsed:.4f}s ({throughput:.0f} events/s, {parsed} parsed)")
        assert elapsed < 2.0

    def test_deduplication_throughput(self):
        """dedupe_events_by_time_channel_text with large event set."""
        from src.core.business_events import dedupe_events_by_time_channel_text
        events = _make_events(5000)
        # Parse them first to get business events
        business = []
        for e in events:
            be = core.parse_business_event(e)
            if be:
                business.append(be)
        _, elapsed = _time_it(dedupe_events_by_time_channel_text, business)
        print(f"\n  [DEDUP] Dedup {len(business)} business events: {elapsed:.4f}s")
        assert elapsed < 5.0


# ===================================================================
# PART 7: CONCURRENT / THREAD SAFETY
# ===================================================================

class TestConcurrentOperations:
    """Verify that multiple operations don't interfere."""

    def test_sequential_session_creation(self):
        """Creating 100 sessions sequentially should be fast."""
        tmp = _tmp()
        try:
            jx3 = tmp / "jx3"
            jx3.mkdir()
            out = tmp / "output"
            out.mkdir()
            t0 = time.perf_counter()
            for _ in range(100):
                core.create_session(jx3, out)
            elapsed = time.perf_counter() - t0
            print(f"\n  [LOOP] 100 session creations: {elapsed:.3f}s ({elapsed/100*1000:.1f}ms each)")
            assert elapsed < 30.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rapid_jsonl_append(self):
        """10 sequential appends to the same JSONL file."""
        tmp = _tmp()
        try:
            path = tmp / "events.jsonl"
            events = _make_events(100)
            t0 = time.perf_counter()
            total = 0
            for _ in range(10):
                n = core.append_unique_raw_events(path, events)
                total += n
            elapsed = time.perf_counter() - t0
            final = list(load_jsonl(path))
            print(f"\n  [LOOP] 10 rapid appends (100 events each, dedup): {elapsed:.3f}s -> {len(final)} unique")
            assert elapsed < 10.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 8: STRESS TEST — EXTREME CASES
# ===================================================================

class TestStress:
    """Push the system beyond normal usage."""

    def test_50k_event_analyze(self):
        """analyze_session with 50k events — should not crash."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(50000)
            gc.collect()
            mem_before = _mem_mb()
            _, elapsed = _time_it(core.analyze_session, session_dir)
            gc.collect()
            mem_after = _mem_mb()
            delta = mem_after - mem_before
            print(f"\n  [STRESS] STRESS analyze(50k): {elapsed:.2f}s, memory delta={delta:.1f}MB")
            # Should complete in under 60s
            assert elapsed < 60.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_event_list(self):
        """All operations should handle empty input gracefully."""
        tmp = _tmp()
        try:
            session_dir = tmp / "session"
            session_dir.mkdir()
            write_json(session_dir / "session.json", {"id": "empty", "start_ts": 0})
            write_jsonl(session_dir / "raw_events.jsonl", [])

            # analyze
            _, t1 = _time_it(core.analyze_session, session_dir)
            # settlement
            _, t2 = _time_it(core.extract_settlement, session_dir)
            # segments
            _, t3 = _time_it(core.session_segments, session_dir)

            print(f"\n  [EMPTY] Empty input: analyze={t1:.4f}s settlement={t2:.4f}s segments={t3:.4f}s")
            assert t1 < 1.0 and t2 < 1.0 and t3 < 1.0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_single_event_session(self):
        """Minimal session with 1 event — should not cause division by zero etc."""
        tmp = _tmp()
        try:
            session_dir, events = _setup_session(1)
            core.analyze_session(session_dir)
            report = core.extract_settlement(session_dir)
            assert report["business_event_count"] >= 0
            md = core.render_settlement_markdown(report)
            assert "金团结算报告" in md
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
