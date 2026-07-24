# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.core.identity_inference import parse_info_jx3dat, identity_from_mydata_dir, infer_identity_from_session_files
from src.core.json_io import write_json, write_jsonl


def test_parse_info_jx3dat_multikey_utf8() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dat_path = Path(tmp) / "info.jx3dat"
        # Test UTF-8 with BOM and alternative key name role_name
        dat_path.write_bytes('return {role_name="剑网三勇士", szServer="梦江南"}'.encode("utf-8-sig"))
        
        info = parse_info_jx3dat(dat_path)
        assert info.get("role_name") == "剑网三勇士"
        assert info.get("szServer") == "梦江南"

        ident = identity_from_mydata_dir(Path(tmp))
        assert ident["role_name"] == "剑网三勇士"
        assert ident["server"] == "梦江南"


def test_infer_identity_from_session_files_requires_role_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        mydata = sd / "interface" / "my#data" / "12345@zhcn_hd"
        mydata.mkdir(parents=True)
        # Empty info.jx3dat -> no role_name
        (mydata / "info.jx3dat").write_text("", encoding="utf-8")

        chat_db = mydata / "userdata" / "chat_log" / "chatlog_1.v2.db"
        chat_db.parent.mkdir(parents=True)
        chat_db.touch()

        raw_events = [{"db": str(chat_db)}]
        business_events = [{"kind": "final_purchase", "db": str(chat_db)}]
        write_jsonl(sd / "raw_events.jsonl", raw_events)
        write_jsonl(sd / "business_events.jsonl", business_events)

        ident = infer_identity_from_session_files(sd)
        # Because info.jx3dat has no role_name, infer_identity_from_session_files should return None instead of an empty role_name identity
        assert ident is None


def test_ctk_refresh_history_sessions_reads_settlement_report() -> None:
    from jx3_click_monitor_gui_ctk import App

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        sd = out_dir / "20260724_190000_test"
        sd.mkdir(parents=True)

        # Write session_meta.json without identity
        meta = {
            "history_confirmed": True,
            "watch_mode": "manual",
            "created_label": "2026-07-24 19:00:00",
            "identity": {}
        }
        write_json(sd / "session_meta.json", meta)

        # Write settlement_report.json with identity
        report = {
            "session_start_label": "2026-07-24 19:00:00",
            "instance_name": "25人冷龙峰",
            "identity": {
                "role_name": "李复",
                "server": "蝶恋花"
            }
        }
        write_json(sd / "settlement_report.json", report)

        app = MagicMock(spec=App)
        app.out_var = MagicMock()
        app.out_var.get.return_value = str(out_dir)
        app.history_scroll = MagicMock()
        app.history_scroll.winfo_children.return_value = []

        # Invoke refresh_history_sessions on app instance
        App.refresh_history_sessions(app)

        assert hasattr(app, "history_sessions")
        assert len(app.history_sessions) == 1
        item = app.history_sessions[0]
        assert item["role"] == "蝶恋花 - 李复"
        assert item["instance"] == "25人冷龙峰"
