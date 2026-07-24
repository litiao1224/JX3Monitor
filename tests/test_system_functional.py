# -*- coding: utf-8 -*-
"""System / functional tests for JX3 Click Monitor.

Simulates real user workflows end-to-end:
  1. Main flow: create session → poll → analyze → settlement → export
  2. Exception flow: missing files, corrupt data, permission errors, empty input
  3. Compatibility: DPI scaling, unicode paths, edge-case data volumes

Run: python -m pytest tests/test_system_functional.py -v
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

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
    money_parts_to_copper,
    copper_to_gold,
    parse_gold_amount_text,
    normalize_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="jx3sys_"))


def _make_fake_chatlog(db_path: Path, rows: list | None = None, base_time: int | None = None) -> Path:
    """Create a minimal ChatLog SQLite DB for testing."""
    if base_time is None:
        base_time = int(time.time()) + 5
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE ChatLog (hash INTEGER, type TEXT, time INTEGER, talker TEXT, text TEXT, msg TEXT)")
    if rows is None:
        rows = [
            (1, "MSG_ROOM", base_time + 2, "团长·长安城", "[房间][团长·长安城]：[装备A]开始拍卖", ""),
            (2, "MSG_ROOM", base_time + 4, "老板·唯我独尊", "[房间][老板·唯我独尊]：[老板·唯我独尊]以[2000金]叫价[装备A]", ""),
            (3, "MSG_ROOM", base_time + 8, "老板·唯我独尊", "[房间][老板·唯我独尊]：[老板·唯我独尊]花费[2000金]购买了[装备A]", ""),
            (4, "MSG_ROOM", base_time + 12, "团长·长安城", "[房间][团长·长安城]：[装备B]开始拍卖", ""),
            (5, "MSG_ROOM", base_time + 14, "老板二·梦江南", "[房间][老板二·梦江南]：[老板二·梦江南]以[3000金]叫价[装备B]", ""),
            (6, "MSG_ROOM", base_time + 18, "老板二·梦江南", "[房间][老板二·梦江南]：[老板二·梦江南]花费[3000金]购买了[装备B]", ""),
            (7, "MSG_ROOM", base_time + 24, "团长·长安城", "[房间][团长·长安城]：拍团目前总收入为：5000金，补贴总费用：0金， 实际可用分配金额：5000金， 分配人数：5， 每人底薪：1000金。", ""),
            (8, "MSG_MONEY", base_time + 28, "", "你获得：100000。", ""),
        ]
    con.executemany("INSERT INTO ChatLog(hash, type, time, talker, text, msg) VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    return db_path


def _make_fake_jx3_tree(base: Path, account: str = "test_account", uid: str = "12345") -> Path:
    """Create a minimal JX3 zhcn_hd directory tree."""
    zhcn = base / "bin" / "zhcn_hd"
    mydata = zhcn / "interface" / "my#data" / f"{uid}@zhcn_hd"
    chat_dir = mydata / "userdata" / "chat_log"
    chat_dir.mkdir(parents=True, exist_ok=True)
    # info.jx3dat — parse_info_jx3dat reads with GBK, so write GBK
    (mydata / "info.jx3dat").write_bytes(
        'return {name="测试角色", server="长安城", region="电信", id="99999"}'.encode("gbk")
    )
    return zhcn


def _make_fake_raw_events(out_dir: Path, events: list[dict]) -> Path:
    """Write raw_events.jsonl with given events."""
    p = out_dir / "raw_events.jsonl"
    write_jsonl(p, events)
    return p


def _make_fake_session(out_dir: Path, raw_events: list[dict] | None = None, meta: dict | None = None) -> Path:
    """Create a minimal session dir with session.json + raw_events.jsonl."""
    ensure_dir(out_dir)
    session_data = {
        "id": "test_session",
        "source": "test",
        "status": "imported",
        "history_confirmed": False,
        "start_ts": 1781232000,
        "end_ts": 1781232060,
        "identity": {"role_name": "测试角色", "server": "长安城", "display": "测试角色/长安城"},
    }
    if meta:
        session_data.update(meta)
    write_json(out_dir / "session.json", session_data)
    if raw_events is not None:
        _make_fake_raw_events(out_dir, raw_events)
    return out_dir


# ===================================================================
# PART 1: MAIN FLOW TESTS — End-to-End User Workflows
# ===================================================================

class TestMainFlowSessionLifecycle:
    """Full lifecycle: create → poll → stop → analyze → settlement → export."""

    def test_create_session_produces_valid_structure(self):
        tmp = _make_tmp_dir()
        try:
            jx3 = tmp / "jx3"
            jx3.mkdir()
            out = tmp / "output"
            out.mkdir()
            session_dir = core.create_session(jx3, out, team_tag="test", watch_mode="gui")
            # Session dir exists
            assert session_dir.exists()
            assert session_dir.is_dir()
            # Required files
            assert (session_dir / "session_meta.json").exists()
            assert (session_dir / "state.json").exists()
            assert (session_dir / "active_session.json").exists()
            # Meta content
            meta = read_json(session_dir / "session_meta.json", {})
            assert meta["schema"] == 1
            assert meta["status"] == "active"
            assert meta["team_tag"] == "test"
            assert meta["watch_mode"] == "gui"
            assert meta["history_source"] == "新的记录"
            assert "identity" in meta
            # Active session also written to out_dir root
            active_root = read_json(out / "active_session.json", {})
            assert active_root["session_id"] == meta["session_id"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_full_pipeline_raw_to_settlement(self):
        """Core user flow: raw events → analyze → settlement report."""
        tmp = _make_tmp_dir()
        try:
            base_time = 1781232000
            events = [
                {"time": base_time + 2, "rowid": 1, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：[装备A]开始拍卖", "msg": "", "db": "test.db", "table": "ChatLog",
                 "columns": ["hash", "type", "time", "talker", "text", "msg"], "scan_ts": now_ts()},
                {"time": base_time + 4, "rowid": 2, "type": "MSG_ROOM", "talker": "买家A",
                 "text": "[房间][买家A]：[买家A]以[2000金]叫价[装备A]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": ["hash", "type", "time", "talker", "text", "msg"], "scan_ts": now_ts()},
                {"time": base_time + 8, "rowid": 3, "type": "MSG_ROOM", "talker": "买家A",
                 "text": "[房间][买家A]：[买家A]花费[2000金]购买了[装备A]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": ["hash", "type", "time", "talker", "text", "msg"], "scan_ts": now_ts()},
                {"time": base_time + 12, "rowid": 4, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：拍团目前总收入为：2000金，补贴总费用：0金， 实际可用分配金额：2000金， 分配人数：5， 每人底薪：400金。",
                 "msg": "", "db": "test.db", "table": "ChatLog",
                 "columns": ["hash", "type", "time", "talker", "text", "msg"], "scan_ts": now_ts()},
                {"time": base_time + 16, "rowid": 5, "type": "MSG_MONEY", "talker": "",
                 "text": "你获得：100000。", "msg": "", "db": "test.db", "table": "ChatLog",
                 "columns": ["hash", "type", "time", "talker", "text", "msg"], "scan_ts": now_ts()},
            ]
            session_dir = _make_fake_session(tmp / "session", raw_events=events)
            # Step 1: analyze
            summary = core.analyze_session(session_dir)
            assert summary["business_event_count"] > 0
            assert "bid" in summary["kind_counts"] or "final_purchase" in summary["kind_counts"]
            # Step 2: settlement
            report = core.extract_settlement(session_dir, self_name="团长")
            assert "purchases" in report
            assert "buyer_totals" in report
            assert report["member_count"] == 5
            assert report["average_wage_gold"] == 400.0
            # Step 3: report files
            assert (session_dir / "settlement_report.json").exists()
            assert (session_dir / "auction_summary.json").exists()
            assert (session_dir / "business_events.jsonl").exists()
            # Step 4: markdown report
            md = core.render_settlement_markdown(report)
            assert "金团结算报告" in md
            assert "装备A" in md
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_csv_export_produces_all_files(self):
        """User clicks '导出 CSV' → 4 CSV files appear."""
        tmp = _make_tmp_dir()
        try:
            base_time = 1781232000
            events = [
                {"time": base_time + 2, "rowid": 1, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：[装备X]开始拍卖", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": base_time + 4, "rowid": 2, "type": "MSG_ROOM", "talker": "买家Y",
                 "text": "[房间][买家Y]：[买家Y]以[5000金]叫价[装备X]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": base_time + 6, "rowid": 3, "type": "MSG_ROOM", "talker": "买家Y",
                 "text": "[房间][买家Y]：[买家Y]花费[5000金]购买了[装备X]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": base_time + 8, "rowid": 4, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：拍团目前总收入为：5000金，补贴总费用：0金， 实际可用分配金额：5000金， 分配人数：10， 每人底薪：500金。",
                 "msg": "", "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
            ]
            session_dir = _make_fake_session(tmp / "session", raw_events=events)
            report = core.extract_settlement(session_dir)
            export_dir = tmp / "csv_export"
            paths = core.export_settlement_csv(report, export_dir)
            assert "summary_csv" in paths
            assert "purchases_csv" in paths
            assert "buyers_csv" in paths
            assert "zero_price_records_csv" in paths
            for key, path_str in paths.items():
                p = Path(path_str)
                assert p.exists(), f"{key} not created at {p}"
                content = p.read_text(encoding="utf-8-sig")
                assert len(content) > 10, f"{key} is suspiciously empty"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_markdown_report_contains_all_sections(self):
        """Generated markdown report has all expected sections."""
        tmp = _make_tmp_dir()
        try:
            base_time = 1781232000
            events = [
                {"time": base_time + 2, "rowid": 1, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：[武器]开始拍卖", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": base_time + 4, "rowid": 2, "type": "MSG_ROOM", "talker": "买家",
                 "text": "[房间][买家]：[买家]以[1000金]叫价[武器]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": base_time + 6, "rowid": 3, "type": "MSG_ROOM", "talker": "买家",
                 "text": "[房间][买家]：[买家]花费[1000金]购买了[武器]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": base_time + 8, "rowid": 4, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：拍团目前总收入为：1000金，补贴总费用：0金， 实际可用分配金额：1000金， 分配人数：5， 每人底薪：200金。",
                 "msg": "", "db": "test.db", "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
            ]
            session_dir = _make_fake_session(tmp / "session", raw_events=events)
            report = core.extract_settlement(session_dir)
            md = core.render_settlement_markdown(report)
            # Key sections
            assert "金团结算报告" in md
            assert "副本名称" in md
            assert "拍团总收入" in md
            assert "补贴总费用" in md
            assert "实际可分配" in md
            assert "分配人数" in md
            assert "每人底薪" in md
            assert "付费成交" in md
            assert "武器" in md
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_analyze_session_writes_business_events(self):
        """analyze_session produces business_events.jsonl and auction_summary.json."""
        tmp = _make_tmp_dir()
        try:
            events = [
                {"time": 1781232000, "rowid": 1, "type": "MSG_ROOM", "talker": "团长",
                 "text": "[房间][团长]：[装备]开始拍卖", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
                {"time": 1781232002, "rowid": 2, "type": "MSG_ROOM", "talker": "买家",
                 "text": "[房间][买家]：[买家]以[100金]叫价[装备]", "msg": "", "db": "test.db",
                 "table": "ChatLog", "columns": [], "scan_ts": now_ts()},
            ]
            session_dir = _make_fake_session(tmp / "session", raw_events=events)
            summary = core.analyze_session(session_dir)
            # Files produced
            assert (session_dir / "business_events.jsonl").exists()
            assert (session_dir / "auction_summary.json").exists()
            # Content
            biz_events = list(load_jsonl(session_dir / "business_events.jsonl"))
            assert len(biz_events) >= 2
            kinds = [e.get("kind") for e in biz_events]
            assert "auction_start" in kinds
            assert "bid" in kinds
            # Auction summary
            auction_summary = read_json(session_dir / "auction_summary.json", {})
            assert auction_summary["auction_item_count"] >= 1
            assert auction_summary["bid_count"] >= 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMainFlowIncomeMemory:
    """Income memory CRUD — the '收支记录' feature."""

    def test_upsert_and_search_income_memory(self):
        tmp = _make_tmp_dir()
        try:
            path = tmp / "income_memory.json"
            report = {
                "identity": {"role_name": "团长", "server": "长安城"},
                "instance_name": "英雄木桩",
                "instance_confidence": "medium",
                "self_actual_income_gold": 1000.0,
                "self_estimated_wage_gold": 800.0,
                "total_auction_gold": 5000,
                "member_count": 5,
                "average_wage_gold": 1000.0,
                "session_start_label": "2026-06-20 21:00:00",
                "session_start_ts": 1781232000.0,
                "session_stop_label": "2026-06-20 22:00:00",
                "purchases": [{"buyer": "买家A", "item": "装备X", "amount_gold": 2000, "target": "买家A"}],
                "black_role": "",
            }
            session_dir = tmp / "session1"
            session_dir.mkdir()
            # Upsert
            record = core.upsert_income_memory(path, report, session_dir)
            assert record["role"] == "团长"
            assert record["server"] == "长安城"
            assert record["instance"] == "英雄木桩"
            assert record["income_gold"] == 1000.0
            # expense: only counts purchases where buyer matches self role; buyer is "买家A", not "团长"
            assert record["expense_gold"] == 0.0
            assert record["net_gold"] == 1000.0
            assert record["seq"] == 1
            # Search
            results = core.search_income_memory(path, "团长")
            assert len(results) == 1
            assert results[0]["role"] == "团长"
            # Search no match
            results2 = core.search_income_memory(path, "不存在的角色")
            assert len(results2) == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_update_income_memory_record(self):
        tmp = _make_tmp_dir()
        try:
            path = tmp / "income_memory.json"
            report = {
                "identity": {"role_name": "A", "server": "S"},
                "self_actual_income_gold": 500.0,
                "session_start_label": "2026-06-20 21:00:00",
                "session_start_ts": 1781232000.0,
                "purchases": [],
            }
            session_dir = tmp / "s1"
            session_dir.mkdir()
            record = core.upsert_income_memory(path, report, session_dir)
            seq = record["seq"]
            # Update
            updated = core.update_income_memory_record(path, seq, {"note": "已确认"})
            assert updated["note"] == "已确认"
            assert updated["manual"] is True
            # Update income
            updated2 = core.update_income_memory_record(path, seq, {"income_gold": 1500.0})
            assert updated2["income_gold"] == 1500.0
            assert updated2["net_gold"] == 1500.0 - updated2["expense_gold"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_delete_income_memory_record(self):
        tmp = _make_tmp_dir()
        try:
            path = tmp / "income_memory.json"
            report = {
                "identity": {"role_name": "X", "server": "Y"},
                "self_actual_income_gold": 100.0,
                "session_start_label": "2026-06-20 21:00:00",
                "session_start_ts": 1781232000.0,
                "purchases": [],
            }
            session_dir = tmp / "s1"
            session_dir.mkdir()
            record = core.upsert_income_memory(path, report, session_dir)
            seq = record["seq"]
            # Delete
            ok = core.delete_income_memory_record(path, seq)
            assert ok is True
            # Verify gone
            results = core.search_income_memory(path, "X")
            assert len(results) == 0
            # Delete non-existent returns False
            ok2 = core.delete_income_memory_record(path, 99999)
            assert ok2 is False
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_upsert_custom_income_memory(self):
        """User manually creates an income record from the dialog."""
        tmp = _make_tmp_dir()
        try:
            path = tmp / "income_memory.json"
            rec = {
                "session_dir": "",
                "role": "手动角色",
                "server": "手动服",
                "instance": "手动副本",
                "income_gold": 2000.0,
                "expense_gold": 0.0,
                "note": "手动录入",
            }
            out = core.upsert_income_memory_custom(path, rec)
            assert out["role"] == "手动角色"
            assert out["manual"] is True
            assert out["income_gold"] == 2000.0
            assert out["net_gold"] == 2000.0
            assert out["seq"] == 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMainFlowHTMLImport:
    """Import JX3 exported ChatLog HTML → session → settlement."""

    def _make_fake_html(self, out_path: Path, messages: list[dict]) -> Path:
        """Create a minimal JX3 exported ChatLog HTML."""
        html = f"""<!DOCTYPE html>
<html><head><title>ChatLog Export</title></head>
<body>
<script>
window.MESSAGES = {json.dumps(messages, ensure_ascii=False)};
</script>
</body></html>"""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="gbk")
        return out_path

    def test_import_html_creates_session(self):
        tmp = _make_tmp_dir()
        try:
            html_path = tmp / "export" / "测试角色@长安城@20260620210000.html"
            messages = [
                {"time": 1781232000, "talker": "团长", "text": "[2026/6/20][21:00:00][房间][团长]：[装备]开始拍卖", "parts": []},
                {"time": 1781232002, "talker": "买家", "text": "[2026/6/20][21:00:02][房间][买家]：[买家]以[100金]叫价[装备]", "parts": []},
                {"time": 1781232004, "talker": "买家", "text": "[2026/6/20][21:00:04][房间][买家]：[买家]花费[100金]购买了[装备]", "parts": []},
            ]
            self._make_fake_html(html_path, messages)
            out_dir = tmp / "output"
            out_dir.mkdir()
            session_dir = core.import_chatlog_html_session(html_path, out_dir)
            assert session_dir.exists()
            assert (session_dir / "raw_events.jsonl").exists()
            assert (session_dir / "business_events.jsonl").exists()
            assert (session_dir / "settlement_report.json").exists()
            assert (session_dir / "settlement_report.md").exists()
            # Verify events parsed
            raw = list(load_jsonl(session_dir / "raw_events.jsonl"))
            assert len(raw) == 3
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_import_html_empty_messages_fails(self):
        """HTML with no window.MESSAGES should raise ValueError."""
        tmp = _make_tmp_dir()
        try:
            html_path = tmp / "bad.html"
            html_path.write_text("<html><body>no messages here</body></html>", encoding="utf-8")
            out_dir = tmp / "output"
            out_dir.mkdir()
            with pytest.raises(ValueError, match="window.MESSAGES"):
                core.import_chatlog_html_session(html_path, out_dir)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMainFlowIdentityInference:
    """Identity inference from session files and JX3 paths."""

    def test_identity_from_path_with_mydata_dir(self):
        """Identity inferred from <uid>@zhcn_hd path."""
        tmp = _make_tmp_dir()
        try:
            zhcn = _make_fake_jx3_tree(tmp, uid="99999")
            mydata = zhcn / "interface" / "my#data" / "99999@zhcn_hd"
            ident = core.identity_from_path(mydata / "info.jx3dat")
            assert ident["role_name"] == "测试角色"
            assert ident["server"] == "长安城"
            assert ident["uid"] == "99999"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_identity_from_path_no_mydata(self):
        """When no my#data dir exists, returns minimal identity."""
        tmp = _make_tmp_dir()
        try:
            ident = core.identity_from_path(tmp / "random" / "path")
            assert ident["role_name"] is None
            assert ident["server"] is None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_apply_identity_override(self):
        ident = {"role_name": "旧角色", "server": "旧服", "display": "旧"}
        overridden = core.apply_identity_override(ident, role_name_override="新角色")
        assert overridden["role_name"] == "新角色"
        assert overridden["role_name_source"] == "manual_override"
        assert "新角色" in overridden["display"]

    def test_apply_identity_override_empty(self):
        """Empty override keeps original."""
        ident = {"role_name": "原角色", "server": "服", "display": "原"}
        result = core.apply_identity_override(ident, role_name_override="")
        assert result["role_name"] == "原角色"


# ===================================================================
# PART 2: EXCEPTION FLOW TESTS — Error Handling & Edge Cases
# ===================================================================

class TestExceptionFlowMissingFiles:
    """What happens when expected files are missing."""

    def test_poll_session_no_meta(self):
        """poll_session on dir without session_meta.json/session.json → SystemExit."""
        tmp = _make_tmp_dir()
        try:
            empty_dir = tmp / "empty_session"
            empty_dir.mkdir()
            with pytest.raises(SystemExit, match="session_meta.json"):
                core.poll_session(empty_dir)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_analyze_session_no_raw_events(self):
        """analyze_session with no raw_events.jsonl → empty result, no crash."""
        tmp = _make_tmp_dir()
        try:
            session_dir = _make_fake_session(tmp / "session")
            # No raw_events.jsonl
            summary = core.analyze_session(session_dir)
            assert summary["business_event_count"] == 0
            assert summary["kind_counts"] == {}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_extract_settlement_empty_session(self):
        """settlement on empty session → report with zero values, no crash."""
        tmp = _make_tmp_dir()
        try:
            session_dir = _make_fake_session(tmp / "session")
            report = core.extract_settlement(session_dir)
            assert report["purchase_count"] == 0
            assert report["member_count"] is None or report["member_count"] == 0
            assert report["total_auction_gold"] == 0
            assert report["purchases"] == []
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_export_csv_empty_report(self):
        """CSV export on empty report → files exist but minimal."""
        tmp = _make_tmp_dir()
        try:
            report = {
                "purchases": [], "buyer_totals": [], "zero_price_records": [],
                "instance_name": None, "instance_confidence": "unknown",
                "session_start_label": None, "session_stop_label": None,
                "total_auction_gold": 0, "subsidy_gold": 0, "distributable_gold": 0,
                "member_count": None, "average_wage_gold": None,
                "purchase_count": 0, "calculated_purchase_total_gold": 0,
                "purchase_total_vs_settlement_diff_gold": 0,
                "purchase_total_vs_settlement_status": "ok",
                "purchase_total_vs_settlement_status_label": "一致",
                "purchase_total_vs_settlement_note": "",
                "purchase_source": "none", "business_event_count": 0,
                "business_kind_counts": {},
                "zero_price_record_count": 0, "self_raw_money_gain_gold": 0,
                "detected_personal_subsidy_gold": None, "self_actual_income_gold": 0,
                "self_estimated_total_gain_gold": 0,
            }
            paths = core.export_settlement_csv(report, tmp / "csv")
            for path_str in paths.values():
                assert Path(path_str).exists()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_session_info_missing(self):
        """load_session_info returns default when both files missing."""
        tmp = _make_tmp_dir()
        try:
            d = tmp / "no_session"
            d.mkdir()
            result = core.load_session_info(d, default={"fallback": True})
            assert result == {"fallback": True}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_exported_chatlog_bad_json(self):
        """HTML with window.MESSAGES = [invalid → raises."""
        tmp = _make_tmp_dir()
        try:
            html_path = tmp / "bad_json.html"
            html_path.write_text(
                '<html><script>window.MESSAGES = {broken json!!!};</script></html>',
                encoding="utf-8",
            )
            with pytest.raises(Exception):
                core.load_exported_chatlog_messages(html_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestExceptionFlowCorruptData:
    """Handling of corrupt or malformed data."""

    def test_parse_money_amount_empty_msg(self):
        """parse_money_amount with empty msg/text returns zeros."""
        result = core.parse_money_amount({"msg": "", "text": ""})
        assert result["gold"] == 0
        assert result["silver"] == 0
        assert result["copper"] == 0

    def test_parse_money_amount_valid_text(self):
        """parse_money_amount correctly parses '你获得：100000。' (100000 copper = 10 gold, but raw gold field stores 100000)."""
        result = core.parse_money_amount({"msg": "", "text": "你获得：100000。"})
        # MONEY_GAIN_RE matches amount=100000; this is raw copper count stored in gold field
        assert result["gold"] == 100000

    def test_parse_business_event_none_text(self):
        """parse_business_event with None text → returns None."""
        result = core.parse_business_event({
            "text": None, "type": "MSG_ROOM", "time": 1781232000, "rowid": 1,
            "msg": "", "db": "test.db",
        })
        assert result is None

    def test_parse_business_event_unknown_type(self):
        """parse_business_event with unknown type and unmatched text → None."""
        result = core.parse_business_event({
            "text": "some random message", "type": "MSG_UNKNOWN", "time": 1781232000,
            "rowid": 1, "msg": "", "db": "test.db",
        })
        assert result is None

    def test_raw_event_key_determinism(self):
        """Same event always produces same key."""
        e1 = {"time": 1781232000, "rowid": 1, "type": "MSG_ROOM", "text": "hello", "msg": ""}
        e2 = {"time": 1781232000, "rowid": 1, "type": "MSG_ROOM", "text": "hello", "msg": ""}
        assert core.raw_event_key(e1) == core.raw_event_key(e2)

    def test_append_unique_raw_events_deduplication(self):
        """Duplicate events are not appended."""
        tmp = _make_tmp_dir()
        try:
            path = tmp / "events.jsonl"
            events = [
                {"time": 1781232000, "rowid": 1, "type": "MSG_ROOM", "text": "dup", "msg": "", "db": "a.db"},
                {"time": 1781232000, "rowid": 1, "type": "MSG_ROOM", "text": "dup", "msg": "", "db": "a.db"},
                {"time": 1781232001, "rowid": 2, "type": "MSG_ROOM", "text": "unique", "msg": "", "db": "a.db"},
            ]
            n = core.append_unique_raw_events(path, events)
            assert n == 2  # 1 dup removed
            loaded = list(load_jsonl(path))
            assert len(loaded) == 2
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_split_session_empty_range_raises(self):
        """split_session with no events in range → ValueError."""
        tmp = _make_tmp_dir()
        try:
            events = [
                {"time": 100, "rowid": 1, "type": "MSG_ROOM", "text": "a", "msg": "", "db": "x.db",
                 "table": "ChatLog", "columns": [], "scan_ts": 0},
            ]
            session_dir = _make_fake_session(tmp / "session", raw_events=events)
            with pytest.raises(ValueError, match="没有 raw_events 记录"):
                core.split_session_by_time(session_dir, None, 999, 1000)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestExceptionFlowPermissionAndIO:
    """IO error handling: read-only dirs, missing parents, etc."""

    def test_write_json_creates_parent_dirs(self):
        """write_json auto-creates nested parent directories."""
        tmp = _make_tmp_dir()
        try:
            deep_path = tmp / "a" / "b" / "c" / "data.json"
            core.write_json(deep_path, {"hello": "world"})
            assert deep_path.exists()
            assert read_json(deep_path, None) == {"hello": "world"}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_read_json_missing_file_returns_default(self):
        """read_json on non-existent file returns default."""
        result = core.read_json(Path("/nonexistent/path.json"), {"default": True})
        assert result == {"default": True}

    def test_ensure_dir_idempotent(self):
        """ensure_dir on existing dir does not raise."""
        tmp = _make_tmp_dir()
        try:
            d = tmp / "test_dir"
            d.mkdir()
            core.ensure_dir(d)  # should not raise
            assert d.exists()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unique_session_dir_avoids_collision(self):
        """unique_session_dir increments suffix when name exists."""
        tmp = _make_tmp_dir()
        try:
            # Create first session
            sid1, dir1 = core.unique_session_dir(tmp, "2026-06-20_21-00-00")
            dir1.mkdir()
            # Next call should produce _02 suffix
            sid2, dir2 = core.unique_session_dir(tmp, "2026-06-20_21-00-00")
            assert sid2 != sid1
            assert "_02" in sid2
            assert dir2 != dir1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 3: COMPATIBILITY & EDGE CASE TESTS
# ===================================================================

class TestCompatibilityDPI:
    """DPI / HighDPI scaling compatibility."""

    def test_ctk_image_import(self):
        """CTkImage can be imported (Pillow installed)."""
        import customtkinter as ctk
        assert hasattr(ctk, "CTkImage")

    def test_ctk_image_creation_with_pil(self):
        """CTkImage can be created with a PIL Image."""
        from PIL import Image
        import customtkinter as ctk
        img = Image.new("RGB", (16, 16), color="red")
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(16, 16))
        assert ctk_img is not None

    def test_ctk_scaling_settings_exist(self):
        """CustomTkinter has the scaling configuration methods."""
        import customtkinter as ctk
        assert hasattr(ctk, "set_widget_scaling")
        assert hasattr(ctk, "set_window_scaling")


class TestCompatibilityUnicodePaths:
    """Unicode / CJK characters in file paths."""

    def test_session_with_unicode_jx3_path(self):
        """create_session works with CJK characters in path."""
        tmp = _make_tmp_dir()
        try:
            jx3 = tmp / "剑网3路径" / "测试"
            jx3.mkdir(parents=True)
            out = tmp / "输出目录"
            out.mkdir(parents=True)
            session_dir = core.create_session(jx3, out, team_tag="unicode测试")
            assert session_dir.exists()
            meta = read_json(session_dir / "session_meta.json", {})
            assert "剑网3路径" in meta["jx3_path"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_html_import_with_cjk_filename(self):
        """Import HTML with CJK filename."""
        tmp = _make_tmp_dir()
        try:
            html_path = tmp / "长角色名@电信长安城@20260620210000.html"
            messages = [
                {"time": 1781232000, "talker": "团长", "text": "[2026/6/20][21:00:00][房间][团长]：[装备]开始拍卖", "parts": []},
            ]
            html = f"""<!DOCTYPE html>
<html><head></head><body>
<script>window.MESSAGES = {json.dumps(messages, ensure_ascii=False)};</script>
</body></html>"""
            html_path.write_text(html, encoding="gbk")
            out_dir = tmp / "output"
            out_dir.mkdir()
            session_dir = core.import_chatlog_html_session(html_path, out_dir)
            assert session_dir.exists()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCompatibilityEdgeCases:
    """Edge cases: empty data, extreme values, race conditions."""

    def test_segment_summary_single_event(self):
        """segment_summary with exactly 1 event."""
        events = [{"time": 1781232000, "type": "MSG_ROOM", "text": "hello", "msg": "", "rowid": 1, "db": "x.db"}]
        result = core.segment_summary(events, 1)
        assert result["event_count"] == 1
        assert result["duration_minutes"] == 0.0
        assert result["start_ts"] == 1781232000
        assert result["end_ts"] == 1781232000

    def test_segment_summary_many_events(self):
        """segment_summary handles large event lists."""
        events = [
            {"time": 1781232000 + i, "type": "MSG_ROOM", "text": f"event {i}", "msg": "", "rowid": i, "db": "x.db"}
            for i in range(1000)
        ]
        result = core.segment_summary(events, 1)
        assert result["event_count"] == 1000
        assert result["duration_minutes"] == round(999 / 60, 1)

    def test_session_segments_gap_splitting(self):
        """session_segments splits at 45-minute gaps."""
        tmp = _make_tmp_dir()
        try:
            base = 1781232000
            events = [
                # First segment
                {"time": base, "rowid": 1, "type": "MSG_ROOM", "text": "a", "msg": "", "db": "x.db",
                 "table": "ChatLog", "columns": [], "scan_ts": 0},
                {"time": base + 60, "rowid": 2, "type": "MSG_ROOM", "text": "b", "msg": "", "db": "x.db",
                 "table": "ChatLog", "columns": [], "scan_ts": 0},
                # Gap > 45 min (2700s)
                {"time": base + 3600, "rowid": 3, "type": "MSG_ROOM", "text": "c", "msg": "", "db": "x.db",
                 "table": "ChatLog", "columns": [], "scan_ts": 0},
                {"time": base + 3660, "rowid": 4, "type": "MSG_ROOM", "text": "d", "msg": "", "db": "x.db",
                 "table": "ChatLog", "columns": [], "scan_ts": 0},
            ]
            session_dir = _make_fake_session(tmp / "session", raw_events=events)
            segments = core.session_segments(session_dir, gap_minutes=45)
            assert len(segments) == 2
            assert segments[0]["event_count"] == 2
            assert segments[1]["event_count"] == 2
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_exported_text_body_with_prefix(self):
        """exported_text_body strips date/time prefix."""
        text = "[2026/6/20][21:00:00][房间][团长]：[装备]开始拍卖"
        body = core.exported_text_body(text)
        assert "[房间]" in body
        assert "2026/6/20" not in body

    def test_exported_text_body_no_prefix(self):
        """exported_text_body returns original if no prefix."""
        text = "[房间][团长]：[装备]开始拍卖"
        body = core.exported_text_body(text)
        assert body == text

    def test_infer_type_from_exported_text_money(self):
        """infer_type_from_exported_text identifies MSG_MONEY (requires 金/银/铜 keyword)."""
        # "你获得：100000。" lacks 金/银/铜 keyword → MSG_EXPORTED
        assert core.infer_type_from_exported_text("你获得：100000。") == "MSG_EXPORTED"
        # "你获得：10金。" has 金 keyword → MSG_MONEY
        assert core.infer_type_from_exported_text("你获得：10金。") == "MSG_MONEY"

    def test_infer_type_from_exported_text_room(self):
        """infer_type_from_exported_text identifies MSG_ROOM."""
        assert core.infer_type_from_exported_text("[房间][团长]：something") == "MSG_ROOM"

    def test_infer_type_from_exported_text_team(self):
        """infer_type_from_exported_text identifies MSG_TEAM."""
        assert core.infer_type_from_exported_text("[团队][团长]：something") == "MSG_TEAM"

    def test_infer_type_from_exported_text_whisper(self):
        """infer_type_from_exported_text identifies MSG_WHISPER."""
        assert core.infer_type_from_exported_text("[密聊][某人]：hello") == "MSG_WHISPER"

    def test_normalize_item_search_name(self):
        """normalize_item_search_name strips bullets and whitespace."""
        from src.services.jx3box_client import normalize_item_search_name
        assert normalize_item_search_name("\u00b7装备\u00b7") == "装备"
        assert normalize_item_search_name("  test  ") == "test"
        assert normalize_item_search_name("") == ""
        assert normalize_item_search_name(None) == ""

    def test_normalize_jx3box_attr_name(self):
        """normalize_jx3box_attr_name normalizes attribute names."""
        from src.services.jx3box_client import normalize_jx3box_attr_name
        assert normalize_jx3box_attr_name("  会心  ") == "会心"
        assert normalize_jx3box_attr_name("") == ""

    def test_money_parts_to_copper_conversion(self):
        """money_parts_to_copper correctly converts."""
        assert money_parts_to_copper(1, 0, 0) == 10000
        assert money_parts_to_copper(0, 1, 0) == 100
        assert money_parts_to_copper(0, 0, 1) == 1
        assert money_parts_to_copper(1, 50, 30) == 15030

    def test_copper_to_gold_conversion(self):
        """copper_to_gold correctly converts."""
        assert copper_to_gold(10000) == 1.0
        assert copper_to_gold(15000) == 1.5
        assert copper_to_gold(0) == 0.0

    def test_parse_gold_amount_text_variants(self):
        """parse_gold_amount_text handles JX3 gold formats: 金砖, 金, plain digits."""
        assert parse_gold_amount_text("1000金") == 1000
        assert parse_gold_amount_text("2金砖5000金") == 25000
        assert parse_gold_amount_text("5000") == 5000
        # 万/砖 without 金 are not JX3-native formats; plain digit fallback
        assert parse_gold_amount_text("1万") == 1
        assert parse_gold_amount_text("1砖") == 1

    def test_parse_final_purchase_with_gold_brick_amount(self):
        """Final purchase messages with gold-brick amounts parse to gold units."""
        sample = (
            "[\u845b\u86cb\u00b7\u98de\u9f99\u5728\u5929]"
            "\u82b1\u8d39[1\u91d1\u78167000\u91d1]"
            "\u8d2d\u4e70\u4e86[\u4e8e\u9617\u7389\u90fd\u00b7\u4f24\u00b7\u978b]"
        )

        event = core.parse_business_event({"time": 1, "type": "MSG_TEAM", "rowid": 1, "text": sample, "msg": ""})

        assert event is not None
        assert event["kind"] == "final_purchase"
        assert event["buyer"] == "\u845b\u86cb\u00b7\u98de\u9f99\u5728\u5929"
        assert event["item"] == "\u4e8e\u9617\u7389\u90fd\u00b7\u4f24\u00b7\u978b"
        assert event["amount_gold"] == 17000

    def test_render_settlement_markdown_none_values(self):
        """render_settlement_markdown handles None fields gracefully."""
        report = {
            "instance_name": None, "instance_confidence": "unknown",
            "session_start_label": None, "session_stop_label": None,
            "total_auction_gold": None, "subsidy_gold": None,
            "distributable_gold": None, "member_count": None,
            "average_wage_gold": None, "purchase_count": 0,
            "paid_purchase_total_gold": None, "calculated_purchase_total_gold": None,
            "purchase_total_vs_settlement_diff_gold": None,
            "purchase_total_vs_settlement_status_label": None,
            "purchase_total_vs_settlement_note": "",
            "purchase_source": "none", "business_kind_counts": {},
        }
        md = core.render_settlement_markdown(report)
        assert "金团结算报告" in md
        assert "未识别" in md


class TestCompatibilityCommandLine:
    """CLI argument parsing and command routing."""

    def test_build_parser_all_commands(self):
        """Parser recognizes all documented commands."""
        parser = core.build_parser()
        for cmd in ["start", "poll", "stop", "offline-scan", "analyze", "settlement",
                     "report", "export-csv", "app", "watch"]:
            args = parser.parse_args([cmd] + _required_args_for(cmd))
            assert args.cmd == cmd

    def test_settlement_defaults(self):
        """settlement command has correct defaults."""
        parser = core.build_parser()
        args = parser.parse_args(["settlement", "--session-dir", "/tmp/test"])
        assert args.member_count is None
        assert args.self_name == "你"
        assert args.personal_subsidy is None


def _required_args_for(cmd: str) -> list[str]:
    """Return minimal required args for each command."""
    if cmd == "start":
        return ["--jx3-path", "/tmp/jx3", "--out-dir", "/tmp/out"]
    elif cmd == "poll":
        return ["--session-dir", "/tmp/session"]
    elif cmd == "stop":
        return ["--session-dir", "/tmp/session"]
    elif cmd == "offline-scan":
        return ["--jx3-path", "/tmp/jx3", "--out-dir", "/tmp/out", "--start-ts", "1781232000"]
    elif cmd == "analyze":
        return ["--session-dir", "/tmp/session"]
    elif cmd == "settlement":
        return ["--session-dir", "/tmp/session"]
    elif cmd == "report":
        return ["--session-dir", "/tmp/session"]
    elif cmd == "export-csv":
        return ["--session-dir", "/tmp/session"]
    elif cmd == "app":
        return []
    elif cmd == "watch":
        return ["--jx3-path", "/tmp/jx3", "--out-dir", "/tmp/out"]
    return []


class TestSqliteDbNoLocking:
    """Verify SQLite DB operations run clean without 'database is locked' errors."""

    def test_save_income_memory_sqlite_no_deadlock(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="jx3sqllock_"))
        db_path = tmp_dir / "income_memory.db"
        try:
            import src.core.sqlite_db as sqlite_db
            from src.core.income_memory import save_income_memory, load_income_memory

            records = [
                {"seq": i, "role": f"角色{i}", "server": "双梦", "income_gold": 100 * i}
                for i in range(1, 10)
            ]
            save_income_memory(db_path, {"records": records})
            loaded = load_income_memory(db_path)
            assert len(loaded["records"]) == 9

            # Replace all records (delete & bulk insert)
            save_income_memory(db_path, {"records": records[:5]})
            loaded2 = load_income_memory(db_path)
            assert len(loaded2["records"]) == 5
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
