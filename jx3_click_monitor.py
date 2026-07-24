#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JX3 click/team monitor MVP.

Clean-room implementation: read JX3 local chat SQLite logs, create sessions,
incrementally collect ChatLog rows, and write JSONL/summary outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.core.utils import (
    APP_VERSION,
    DEFAULT_CHATLOG_GLOB,
    now_ts,
    ts_label,
    session_time_id,
    unique_session_dir,
    parse_local_datetime_ts,
    ensure_dir,
    read_json,
    write_json,
    append_jsonl,
    count_jsonl,
    write_jsonl,
    load_jsonl,
    normalize_text,
    stable_hash,
    money_parts_to_copper,
    copper_to_gold,
    parse_gold_amount_text,
    wildcard_to_regex,
    item_matches_rule,
    resolve_zhcn_hd_path,
    load_income_memory,
    save_income_memory,
)
from src.core.scanner import (
    find_chatlog_dbs,
    connect_readonly,
    table_columns,
    query_chatlog_rows,
)
from src.core.settlement import (
    analyze_session,
    build_settlement_report,
    extract_settlement,
)
from src.core.business_events import (
    parse_business_event,
    parse_money_amount,
)
from src.core.identity_inference import (
    current_identity_from_jx3_path,
    identity_from_path,
    parse_info_jx3dat,
)
EXPORTED_TEXT_PREFIX_RE = re.compile(r"^\[(?P<date>\d{4}/\d{1,2}/\d{1,2})\]\[(?P<time>\d{1,2}:\d{2}:\d{2})\](?P<body>.*)$", re.S)





def raw_event_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    text = normalize_text(row.get("text"))
    msg = normalize_text(row.get("msg"))
    identity = text or msg
    identity_hash = hashlib.sha1(identity.encode("utf-8", errors="replace")).hexdigest()[:16]
    if row.get("time") is not None and identity:
        return ("chat", int(row.get("time") or 0), str(row.get("type") or ""), identity_hash)
    return ("row", row.get("db"), row.get("rowid"), str(row.get("type") or ""), identity_hash)


def append_unique_raw_events(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    seen = {raw_event_key(row) for row in (load_jsonl(path) or [])}
    unique_rows = []
    for row in rows:
        key = raw_event_key(row)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return append_jsonl(path, unique_rows)



def report_income_memory_record(report: Dict[str, Any], session_dir: Path) -> Dict[str, Any]:
    ident = report.get("identity") or {}
    role_name = ident.get("role_name") or ""
    server = ident.get("server") or ""

    def is_self_role_name(value: str) -> bool:
        value = normalize_text(value).strip("[]")
        if not role_name or not value:
            return False
        candidates = {role_name}
        if server:
            candidates.add(f"{role_name}·{server}")
            candidates.add(f"{role_name}@{server}")
        # Cross-server names can be role@origin·server; direct containment is
        # only accepted around the exact role prefix to avoid random substring hits.
        return value in candidates or value.startswith(f"{role_name}·") or value.startswith(f"{role_name}@")

    spend = 0
    spend_items = []
    for p in report.get("purchases", []) or []:
        buyer = p.get("buyer") or ""
        target = p.get("target") or ""
        # 支出：自己角色作为买家/获得人时的消费。若识别不到角色，不自动计支出。
        if is_self_role_name(buyer) or is_self_role_name(target):
            amount = float(p.get("amount_gold") or 0)
            spend += amount
            spend_items.append({"item": p.get("item"), "amount_gold": amount, "buyer": buyer, "target": target})
    income = report.get("self_actual_income_gold")
    if income is None:
        income = report.get("self_estimated_wage_gold") or 0
    session_start_label = report.get("session_start_label") or ts_label()
    session_start_ts = report.get("session_start_ts")
    if session_start_ts is None:
        try:
            session_start_ts = parse_local_datetime_ts(str(session_start_label))
        except Exception:
            session_start_ts = now_ts()
    return {
        "session_dir": str(session_dir),
        "recorded_at": session_start_label,
        "recorded_ts": session_start_ts,
        "session_start": session_start_label,
        "session_end": report.get("session_stop_label"),
        "account": ident.get("login_account") or "",
        "role": role_name,
        "server": server,
        "instance": report.get("instance_name") or "未识别",
        "instance_confidence": report.get("instance_confidence") or "unknown",
        "income_gold": float(income or 0),
        "expense_gold": round(spend, 2),
        "net_gold": round(float(income or 0) - spend, 2),
        "expense_items": spend_items,
        "black_role": report.get("black_role") or "",
        "total_auction_gold": report.get("total_auction_gold"),
        "member_count": report.get("member_count"),
        "average_wage_gold": report.get("average_wage_gold"),
        "note": "",
    }


def upsert_income_memory(path: Path, report: Dict[str, Any], session_dir: Path) -> Dict[str, Any]:
    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.migrate_json_to_db_if_needed(path.with_suffix(".json"))
        base = report_income_memory_record(report, session_dir)
        return sqlite_db.upsert_record(path, base)
    data = load_income_memory(path)
    records = data["records"]
    base = report_income_memory_record(report, session_dir)
    existing = next((r for r in records if r.get("session_dir") == str(session_dir)), None)
    if existing:
        keep = {"seq": existing.get("seq"), "created_at": existing.get("created_at") or existing.get("recorded_at"), "manual": existing.get("manual", False)}
        note = existing.get("note") or ""
        existing.clear()
        existing.update(base)
        existing.update(keep)
        existing["note"] = note
        existing["updated_at"] = ts_label()
        out = existing
    else:
        base["seq"] = int(data.get("next_seq") or 1)
        base["created_at"] = base["recorded_at"]
        base["updated_at"] = base["recorded_at"]
        base["manual"] = False
        records.append(base)
        out = base
    save_income_memory(path, data)
    return out


def upsert_income_memory_custom(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert an income-memory record edited by the user before posting."""
    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.migrate_json_to_db_if_needed(path.with_suffix(".json"))
        rec = dict(record)
        for k in ["income_gold", "expense_gold", "net_gold"]:
            rec[k] = float(rec.get(k) or 0)
        if "net_gold" not in rec or rec.get("net_gold") in (None, ""):
            rec["net_gold"] = round(float(rec.get("income_gold") or 0) - float(rec.get("expense_gold") or 0), 2)
        rec["manual"] = True
        return sqlite_db.upsert_record(path, rec)
    data = load_income_memory(path)
    records = data["records"]
    rec = dict(record)
    session_dir = str(rec.get("session_dir") or "")
    now_label = ts_label()
    for k in ["income_gold", "expense_gold", "net_gold"]:
        rec[k] = float(rec.get(k) or 0)
    if "net_gold" not in record or record.get("net_gold") in (None, ""):
        rec["net_gold"] = round(float(rec.get("income_gold") or 0) - float(rec.get("expense_gold") or 0), 2)
    existing = next((r for r in records if session_dir and r.get("session_dir") == session_dir), None)
    if existing:
        keep = {"seq": existing.get("seq"), "created_at": existing.get("created_at") or existing.get("recorded_at")}
        existing.clear()
        existing.update(rec)
        existing.update(keep)
        existing["updated_at"] = now_label
        existing["manual"] = True
        out = existing
    else:
        rec["seq"] = int(data.get("next_seq") or 1)
        rec["recorded_at"] = rec.get("recorded_at") or now_label
        rec["recorded_ts"] = rec.get("recorded_ts") or now_ts()
        rec["created_at"] = rec["recorded_at"]
        rec["updated_at"] = rec["recorded_at"]
        rec["manual"] = True
        records.append(rec)
        out = rec
    save_income_memory(path, data)
    return out


def update_income_memory_record(path: Path, seq: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.migrate_json_to_db_if_needed(path.with_suffix(".json"))
        rec = sqlite_db.get_record_by_seq(path, seq)
        if not rec:
            raise ValueError(f"收入记忆记录不存在：{seq}")
        editable = {"recorded_at", "session_start", "session_end", "account", "role", "server", "instance", "income_gold", "expense_gold", "net_gold", "note", "expense_items", "black_role"}
        for k, v in patch.items():
            if k in editable:
                if k in {"income_gold", "expense_gold", "net_gold"}:
                    v = float(v or 0)
                rec[k] = v
        rec["manual"] = True
        rec["updated_at"] = ts_label()
        if "net_gold" not in patch and ("income_gold" in patch or "expense_gold" in patch):
            rec["net_gold"] = round(float(rec.get("income_gold") or 0) - float(rec.get("expense_gold") or 0), 2)
        return sqlite_db.upsert_record(path, rec)
    data = load_income_memory(path)
    rec = next((r for r in data["records"] if int(r.get("seq") or 0) == int(seq)), None)
    if not rec:
        raise ValueError(f"收入记忆记录不存在：{seq}")
    editable = {"recorded_at", "session_start", "session_end", "account", "role", "server", "instance", "income_gold", "expense_gold", "net_gold", "note", "expense_items", "black_role"}
    for k, v in patch.items():
        if k in editable:
            if k in {"income_gold", "expense_gold", "net_gold"}:
                v = float(v or 0)
            rec[k] = v
    rec["manual"] = True
    rec["updated_at"] = ts_label()
    if "net_gold" not in patch and ("income_gold" in patch or "expense_gold" in patch):
        rec["net_gold"] = round(float(rec.get("income_gold") or 0) - float(rec.get("expense_gold") or 0), 2)
    save_income_memory(path, data)
    return rec


def delete_income_memory_record(path: Path, seq: int) -> bool:
    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.migrate_json_to_db_if_needed(path.with_suffix(".json"))
        return sqlite_db.delete_record(path, seq)
    data = load_income_memory(path)
    before = len(data["records"])
    data["records"] = [r for r in data["records"] if int(r.get("seq") or 0) != int(seq)]
    save_income_memory(path, data)
    return len(data["records"]) != before


def search_income_memory(path: Path, query: str = "") -> List[Dict[str, Any]]:
    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.migrate_json_to_db_if_needed(path.with_suffix(".json"))
        return sqlite_db.search_records(path, query)
    data = load_income_memory(path)
    q = normalize_text(query).lower()
    records = data.get("records") or []
    if q:
        keys = ["recorded_at", "session_start", "session_end", "account", "role", "server", "instance", "note", "session_dir"]
        records = [r for r in records if any(q in normalize_text(r.get(k)).lower() for k in keys)]
    return sorted(records, key=lambda r: (str(r.get("recorded_at") or ""), int(r.get("seq") or 0)), reverse=True)


def ensure_path_parents_exist(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def export_all_data(out_zip: Path, config_path: Path, income_memory_path: Path) -> None:
    import zipfile
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        if config_path.exists():
            z.write(config_path, config_path.name)
        if income_memory_path.exists():
            z.write(income_memory_path, income_memory_path.name)
        # Also backup JSON if DB exists and vice versa
        alt_db = income_memory_path.with_suffix(".db")
        alt_json = income_memory_path.with_suffix(".json")
        if alt_db.exists():
            z.write(alt_db, alt_db.name)
        if alt_json.exists():
            z.write(alt_json, alt_json.name)


def import_all_data(in_zip: Path, config_path: Path, income_memory_path: Path) -> None:
    import zipfile
    import shutil
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(in_zip, 'r') as z:
            z.extractall(tmp_dir)
            
        # Restore files
        for f in tmp_dir.iterdir():
            if f.name == config_path.name:
                shutil.copy2(f, config_path)
            elif f.name == income_memory_path.name:
                shutil.copy2(f, income_memory_path)
            elif f.name == income_memory_path.with_suffix(".db").name:
                shutil.copy2(f, income_memory_path.with_suffix(".db"))
            elif f.name == income_memory_path.with_suffix(".json").name:
                shutil.copy2(f, income_memory_path.with_suffix(".json"))


def session_meta_path(session_dir: Path) -> Path:
    if (session_dir / "session_meta.json").exists():
        return session_dir / "session_meta.json"
    return session_dir / "session.json"


def load_session_info(session_dir: Path, default: Any = None) -> Any:
    meta = read_json(session_dir / "session_meta.json", None)
    if meta is not None:
        return meta
    session = read_json(session_dir / "session.json", None)
    if session is not None:
        return session
    return default


def save_session_info(session_dir: Path, data: Dict[str, Any]) -> None:
    write_json(session_meta_path(session_dir), data)


# ── Identity helpers (delegated to src.core.identity_inference) ──
# These were previously defined inline; now imported from the
# dedicated module to avoid duplication.
from src.core.identity_inference import (  # noqa: F401
    apply_identity_override,
    current_identity_from_jx3_path,
    extract_login_account_from_userdata_db,
    find_zhcn_hd_root,
    identity_from_mydata_dir,
    identity_from_path,
    infer_identity_from_session_files,
    mydata_dir_latest_mtime,
    parse_info_jx3dat,
)


def session_segments(session_dir: Path, gap_minutes: float = 45) -> List[Dict[str, Any]]:
    """Split one raw session timeline into candidate raid/run segments."""
    rows = [e for e in (load_jsonl(session_dir / "raw_events.jsonl") or []) if e.get("time") is not None]
    rows.sort(key=lambda e: (e.get("time") or 0, str(e.get("db") or ""), e.get("rowid") or 0))
    if not rows:
        return []
    gap_seconds = max(60, float(gap_minutes) * 60)
    segments: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = []
    for e in rows:
        if current and (float(e.get("time") or 0) - float(current[-1].get("time") or 0)) > gap_seconds:
            segments.append(segment_summary(current, len(segments) + 1))
            current = []
        current.append(e)
    if current:
        segments.append(segment_summary(current, len(segments) + 1))
    return segments


def segment_summary(rows: List[Dict[str, Any]], idx: int) -> Dict[str, Any]:
    start = int(min(e.get("time") or 0 for e in rows))
    end = int(max(e.get("time") or 0 for e in rows))
    counts = Counter(e.get("type") or "" for e in rows)
    business = [parse_business_event(e) for e in rows]
    business = [e for e in business if e]
    kinds = Counter(e.get("kind") or "" for e in business)
    snapshots = []
    purchases = 0
    purchase_gold = 0
    append_income_gold = 0
    for e in business:
        if e.get("kind") == "final_purchase" and int(e.get("amount_gold") or 0) > 0:
            purchases += 1
            purchase_gold += int(e.get("amount_gold") or 0)
        if e.get("kind") == "team_append_income" and int(e.get("amount_gold") or 0) > 0:
            append_income_gold += int(e.get("amount_gold") or 0)
        snap = e.get("settlement_snapshot") if e.get("kind") == "final_purchase" else None
        if snap:
            snapshots.append(snap)
        if e.get("kind") == "settlement_summary":
            snapshots.append(e)
    latest_snap = snapshots[-1] if snapshots else None
    return {
        "index": idx,
        "start_ts": start,
        "end_ts": end,
        "start_label": ts_label(start),
        "end_label": ts_label(end),
        "duration_minutes": round((end - start) / 60, 1),
        "event_count": len(rows),
        "type_counts": dict(counts),
        "business_kind_counts": dict(kinds),
        "paid_final_purchase_count": purchases,
        "paid_final_purchase_gold": purchase_gold,
        "team_append_income_gold": append_income_gold,
        "settlement_total_gold": latest_snap.get("total_income_gold") if latest_snap else None,
        "settlement_base_wage_gold": latest_snap.get("base_wage_gold") if latest_snap else None,
    }


def split_session_by_time(session_dir: Path, out_parent: Optional[Path], start_ts: float, end_ts: float, name: Optional[str] = None) -> Path:
    """Create a new session containing raw events within [start_ts, end_ts]."""
    src_session = load_session_info(session_dir, {})
    rows = [e for e in (load_jsonl(session_dir / "raw_events.jsonl") or []) if e.get("time") is not None and float(start_ts) <= float(e.get("time") or 0) <= float(end_ts)]
    if not rows:
        raise ValueError("选中的时间段没有 raw_events 记录")
    out_parent = out_parent or session_dir.parent
    folder_name = name or f"split_{int(start_ts)}_{int(end_ts)}"
    out_dir = out_parent / folder_name
    ensure_dir(out_dir)
    new_session = {
        **src_session,
        "id": folder_name,
        "source_session_dir": str(session_dir),
        "split_start_ts": float(start_ts),
        "split_end_ts": float(end_ts),
        "created_at": now_ts(),
        "created_label": ts_label(),
        "stopped_at": now_ts(),
        "stopped_label": ts_label(),
        "status": "split",
        "history_confirmed": False,
        "total_events": len(rows),
        "note": "Split from an existing mixed session by selected time range.",
    }
    if "identity" not in new_session:
        new_session["identity"] = None
    write_json(out_dir / "session.json", new_session)
    write_jsonl(out_dir / "raw_events.jsonl", rows)
    analyze_session(out_dir)
    extract_settlement(out_dir)
    (out_dir / "settlement_report.md").write_text(render_settlement_markdown(read_json(out_dir / "settlement_report.json", {})), encoding="utf-8")
    return out_dir


def exported_text_body(text: str) -> str:
    text = normalize_text(text)
    m = EXPORTED_TEXT_PREFIX_RE.match(text)
    return normalize_text(m.group("body")) if m else text


def infer_type_from_exported_text(body: str) -> str:
    if body.startswith("[房间]"):
        return "MSG_ROOM"
    if body.startswith("[团队]"):
        return "MSG_TEAM"
    if body.startswith("[密聊]") or body.startswith("[悄悄话]"):
        return "MSG_WHISPER"
    if body.startswith("你获得："):
        if any(x in body for x in ["金", "银", "铜"]) and "点" not in body:
            return "MSG_MONEY"
        if "[" in body and "]" in body:
            return "MSG_ITEM"
    if "获得：" in body and "[" in body and "]" in body:
        return "MSG_ITEM"
    return "MSG_EXPORTED"


def load_exported_chatlog_messages(html_path: Path) -> List[Dict[str, Any]]:
    data = html_path.read_bytes()
    # JX3 exported chat HTML declares GBK.  UTF-8 fallback keeps this robust.
    for enc in ("gbk", "utf-8"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("gbk", errors="replace")
    marker = "window.MESSAGES = "
    idx = text.rfind(marker)
    if idx < 0:
        raise ValueError("没有找到 window.MESSAGES，暂不支持这种 HTML 格式")
    start = idx + len(marker)
    decoder = json.JSONDecoder()
    messages, _ = decoder.raw_decode(text[start:])
    if not isinstance(messages, list):
        raise ValueError("window.MESSAGES 不是列表")
    return messages


def import_chatlog_html_session(html_path: Path, out_dir: Path) -> Path:
    """Import JX3 exported ChatLog HTML into a normal session directory."""
    messages = load_exported_chatlog_messages(html_path)
    rows: List[Dict[str, Any]] = []
    for i, msg in enumerate(messages, start=1):
        full_text = normalize_text(str(msg.get("text") or ""))
        body = exported_text_body(full_text)
        ts = msg.get("time")
        event = {
            "time": ts,
            "rowid": i,
            "type": infer_type_from_exported_text(body),
            "talker": msg.get("talker"),
            "text": body,
            "msg": json.dumps(msg.get("parts") or [], ensure_ascii=False),
            "db": str(html_path),
            "table": "ExportedChatLogHTML",
            "raw_row": msg,
            "columns": ["time", "talker", "text", "parts"],
            "scan_ts": now_ts(),
        }
        rows.append(event)
    session_id = f"html_{html_path.stem}_{int(now_ts())}"
    # Avoid awkward path length / special chars if file name is long.
    session_id = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", session_id)[:120]
    session_dir = out_dir / session_id
    ensure_dir(session_dir)
    session = {
        "id": session_id,
        "source": "exported_chatlog_html",
        "html_path": str(html_path),
        "created_at": now_ts(),
        "created_label": ts_label(),
        "status": "imported",
        "history_confirmed": False,
        "total_events": len(rows),
        "start_ts": min((r.get("time") or 0 for r in rows), default=None),
        "end_ts": max((r.get("time") or 0 for r in rows), default=None),
        "identity": identity_from_path(html_path),
    }
    write_json(session_dir / "session.json", session)
    write_jsonl(session_dir / "raw_events.jsonl", rows)
    analyze_session(session_dir)
    extract_settlement(session_dir)
    (session_dir / "settlement_report.md").write_text(render_settlement_markdown(read_json(session_dir / "settlement_report.json", {})), encoding="utf-8")
    return session_dir





def summarize_events(jsonl_path: Path) -> Dict[str, Any]:
    counts = Counter()
    total = 0
    min_time: Optional[int] = None
    max_time: Optional[int] = None
    sample_texts: List[Dict[str, Any]] = []
    for e in load_jsonl(jsonl_path) or []:
        total += 1
        typ = e.get("type") or ""
        counts[typ] += 1
        t = e.get("time")
        if isinstance(t, int):
            min_time = t if min_time is None else min(min_time, t)
            max_time = t if max_time is None else max(max_time, t)
        if len(sample_texts) < 20 and e.get("text"):
            sample_texts.append({"time": t, "type": typ, "talker": e.get("talker"), "text": e.get("text")})
    return {
        "total_events": total,
        "type_counts": dict(counts.most_common()),
        "min_time": min_time,
        "min_label": ts_label(min_time) if min_time else None,
        "max_time": max_time,
        "max_label": ts_label(max_time) if max_time else None,
        "sample_texts": sample_texts,
        "updated_at": now_ts(),
        "updated_label": ts_label(),
    }


def create_session(jx3_path: Path, out_dir: Path, team_tag: str = "", watch_mode: str = "normal") -> Path:
    start = now_ts()
    session_id, session_dir = unique_session_dir(out_dir, session_time_id(start))
    ensure_dir(session_dir)
    meta = {
        "schema": 1,
        "session_id": session_id,
        "jx3_path": str(jx3_path),
        "start_ts": start,
        "start_label": ts_label(start),
        "created_at": start,
        "created_label": ts_label(start),
        "team_tag": team_tag,
        "watch_mode": watch_mode,
        "status": "active",
        "history_confirmed": False,
        "history_source": "新的记录" if watch_mode == "gui" else "手动导入",
        "identity": identity_from_path(jx3_path),
    }
    active = {
        "schema": 1,
        "status": "active",
        "session_id": session_id,
        "session_dir": str(session_dir),
        "start_ts": start,
        "start_label": ts_label(start),
        "team_tag": team_tag,
        "watch_mode": watch_mode,
        "updated_at": start,
        "updated_label": ts_label(start),
    }
    write_json(session_dir / "session_meta.json", meta)
    write_json(session_dir / "state.json", {"dbs": {}, "last_poll_ts": None})
    write_json(session_dir / "active_session.json", active)
    write_json(out_dir / "active_session.json", active)
    return session_dir


def poll_session(session_dir: Path, end_ts: Optional[float] = None, limit_per_db: int = 10000, analyze: bool = True) -> Dict[str, Any]:
    meta = load_session_info(session_dir, None)
    if not meta:
        raise SystemExit(f"session_meta.json/session.json not found: {session_dir}")
    if not meta.get("jx3_path"):
        summary = summarize_events(session_dir / "raw_events.jsonl")
        if analyze:
            business_summary = analyze_session(session_dir)
            summary["business"] = {
                "business_event_count": business_summary.get("business_event_count"),
                "kind_counts": business_summary.get("kind_counts"),
                "auction_item_count": business_summary.get("auction_item_count"),
                "bid_count": business_summary.get("bid_count"),
            }
        summary["scanned_db_count"] = 0
        summary["scan_error_count"] = 0
        summary["scan_errors"] = []
        write_json(session_dir / "summary.json", summary)
        return summary
    state = read_json(session_dir / "state.json", {"dbs": {}, "last_poll_ts": None})
    jx3_path = Path(meta["jx3_path"])
    start_ts = float(meta["start_ts"])
    db_paths = find_chatlog_dbs(jx3_path)
    total_added = 0
    scanned = []
    scan_errors = []
    for db in db_paths:
        key = str(db)
        db_state = state.setdefault("dbs", {}).setdefault(key, {})
        try:
            stat = db.stat()
            db_mtime = stat.st_mtime
            db_size = stat.st_size
        except OSError:
            continue
            
        last_mtime = db_state.get("last_mtime")
        last_size = db_state.get("last_size")
        since_rowid = int(db_state.get("last_rowid", 0))
        
        if db_mtime == last_mtime and db_size == last_size:
            scanned.append({"db": key, "added": 0, "last_rowid": since_rowid, "error": db_state.get("last_error")})
            continue

        rows, max_rowid, columns, error = query_chatlog_rows(db, since_rowid=since_rowid, start_ts=start_ts, end_ts=end_ts, limit=limit_per_db)
        added = append_unique_raw_events(session_dir / "raw_events.jsonl", rows)
        total_added += added
        if max_rowid > since_rowid:
            db_state["last_rowid"] = max_rowid
        db_state["last_seen_columns"] = columns
        db_state["last_scan_ts"] = now_ts()
        db_state["last_added"] = added
        db_state["last_mtime"] = db_mtime
        db_state["last_size"] = db_size
        
        if error:
            db_state["last_error"] = error
            scan_errors.append({"db": key, "error": error})
        else:
            db_state.pop("last_error", None)
        scanned.append({"db": key, "added": added, "last_rowid": db_state.get("last_rowid", since_rowid), "error": error})
    state["last_poll_ts"] = now_ts()
    state["last_poll_label"] = ts_label()
    write_json(session_dir / "state.json", state)
    summary = summarize_events(session_dir / "raw_events.jsonl")
    summary["last_poll_added"] = total_added
    summary["scanned_db_count"] = len(db_paths)
    summary["scanned"] = scanned
    summary["scan_error_count"] = len(scan_errors)
    summary["scan_errors"] = scan_errors[:20]
    if analyze:
        business_summary = analyze_session(session_dir)
        summary["business"] = {
            "business_event_count": business_summary.get("business_event_count"),
            "kind_counts": business_summary.get("kind_counts"),
            "auction_item_count": business_summary.get("auction_item_count"),
            "bid_count": business_summary.get("bid_count"),
        }
    write_json(session_dir / "summary.json", summary)
    return summary


def stop_session(session_dir: Path) -> Dict[str, Any]:
    stop = now_ts()
    meta = load_session_info(session_dir, {})
    meta["status"] = "stopped"
    meta["stop_ts"] = stop
    meta["stop_label"] = ts_label(stop)
    save_session_info(session_dir, meta)
    time.sleep(1.5)
    summary = poll_session(session_dir, end_ts=stop + 300)
    active = read_json(session_dir / "active_session.json", {})
    active.update({"status": "stopped", "updated_at": stop, "updated_label": ts_label(stop)})
    write_json(session_dir / "active_session.json", active)
    return summary


def offline_scan(jx3_path: Path, out_dir: Path, start_ts: float, end_ts: Optional[float]) -> Dict[str, Any]:
    session_dir = create_session(jx3_path, out_dir, team_tag="offline", watch_mode="offline")
    meta = load_session_info(session_dir, {})
    meta["start_ts"] = start_ts
    meta["start_label"] = ts_label(start_ts)
    meta["offline_end_ts"] = end_ts
    meta["offline_end_label"] = ts_label(end_ts) if end_ts else None
    save_session_info(session_dir, meta)
    summary = poll_session(session_dir, end_ts=end_ts)
    meta["status"] = "offline_done"
    save_session_info(session_dir, meta)
    summary["session_dir"] = str(session_dir)
    write_json(session_dir / "summary.json", summary)
    return summary


def cmd_start(args: argparse.Namespace) -> None:
    session_dir = create_session(Path(args.jx3_path), Path(args.out_dir), args.team_tag, args.watch_mode)
    print(json.dumps({"ok": True, "session_dir": str(session_dir)}, ensure_ascii=False, indent=2))


def cmd_poll(args: argparse.Namespace) -> None:
    summary = poll_session(Path(args.session_dir), limit_per_db=args.limit_per_db)
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2))


def cmd_stop(args: argparse.Namespace) -> None:
    summary = stop_session(Path(args.session_dir))
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2))


def cmd_offline_scan(args: argparse.Namespace) -> None:
    summary = offline_scan(Path(args.jx3_path), Path(args.out_dir), float(args.start_ts), float(args.end_ts) if args.end_ts else None)
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2))


def cmd_analyze(args: argparse.Namespace) -> None:
    summary = analyze_session(Path(args.session_dir))
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2))


def cmd_settlement(args: argparse.Namespace) -> None:
    report = extract_settlement(Path(args.session_dir), member_count=args.member_count, self_name=args.self_name, personal_subsidy_gold=args.personal_subsidy)
    print(json.dumps({"ok": True, "report": report}, ensure_ascii=False, indent=2))


def render_settlement_markdown(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("# 金团结算报告")
    lines.append("")
    lines.append(f"- 副本名称：{report.get('instance_name') or '未识别'}（{report.get('instance_confidence') or 'unknown'}）")
    if (report.get("instance_info") or {}).get("source"):
        lines.append(f"- 副本识别来源：{(report.get('instance_info') or {}).get('source')}")
    lines.append(f"- 开始时间：{report.get('session_start_label') or ''}")
    lines.append(f"- 结束时间：{report.get('session_stop_label') or ''}")
    lines.append(f"- 拍团总收入：{report.get('total_auction_gold')} 金")
    lines.append(f"- 补贴总费用：{report.get('subsidy_gold')} 金")
    lines.append(f"- 实际可分配：{report.get('distributable_gold')} 金")
    lines.append(f"- 分配人数：{report.get('member_count')} 人")
    lines.append(f"- 每人底薪：{report.get('average_wage_gold')} 金")
    lines.append(f"- 已解析付费成交：{report.get('purchase_count')} 条，合计 {report.get('paid_purchase_total_gold', report.get('calculated_purchase_total_gold'))} 金")
    if report.get("team_append_income_count"):
        lines.append(f"- 团队追加收入：{report.get('team_append_income_count')} 条，合计 {report.get('team_append_income_total_gold')} 金")
    lines.append(f"- 与工资条总收入差额：{report.get('purchase_total_vs_settlement_diff_gold')} 金（{report.get('purchase_total_vs_settlement_status_label') or report.get('purchase_total_vs_settlement_status')}）")
    lines.append(f"- 差额说明：{report.get('purchase_total_vs_settlement_note')}")
    lines.append(f"- 成交来源：{report.get('purchase_source')}；业务事件：{report.get('business_kind_counts')}")
    chk = report.get("wage_receipt_check") or {}
    if chk:
        lines.append(f"- 本机收入：实际 {chk.get('actual_income_gold')} 金，底薪 {chk.get('base_wage_gold')} 金，个人补贴 {chk.get('detected_personal_subsidy_gold')} 金，状态 {chk.get('status')}")
        if chk.get('chosen_receipt'):
            lines.append(f"- 工资到账时间：{chk.get('chosen_receipt', {}).get('label')}")
    lines.append("")
    lines.append("## 付费成交")
    for b in report.get("buyer_totals", []):
        lines.append(f"- {b.get('buyer')}：{b.get('total_gold')} 金")
        for item in b.get("items", []):
            src = item.get("reconciliation_source_label") or item.get("reconciliation_source") or ""
            lines.append(f"  - {item.get('item')}：{item.get('amount_gold')} 金（{src}）")
    if report.get("zero_price_record_count"):
        lines.append("")
        lines.append(f"## 0 金拾取/分配记录（不计入总金）：{report.get('zero_price_record_count')} 条")
        for item in report.get("zero_price_records", [])[:80]:
            lines.append(f"- {item.get('buyer')}：{item.get('item')}")
    return "\n".join(lines) + "\n"


def export_settlement_csv(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    ensure_dir(out_dir)
    purchases_csv = out_dir / "settlement_purchases.csv"
    buyers_csv = out_dir / "settlement_buyers.csv"
    zero_csv = out_dir / "settlement_zero_price_records.csv"
    summary_csv = out_dir / "settlement_summary.csv"

    with purchases_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["buyer", "target", "item", "amount_gold", "time", "label", "reconciliation_source", "reconciliation_source_label", "source_text"])
        w.writeheader()
        for p in report.get("purchases", []):
            w.writerow({k: p.get(k) for k in w.fieldnames})

    with buyers_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["buyer", "total_gold", "item_count", "items"])
        w.writeheader()
        for b in report.get("buyer_totals", []):
            items = "；".join(f"{i.get('item')}({i.get('amount_gold')}金)" for i in b.get("items", []))
            w.writerow({"buyer": b.get("buyer"), "total_gold": b.get("total_gold"), "item_count": len(b.get("items", [])), "items": items})

    with zero_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["buyer", "target", "item", "amount_gold", "time", "label", "reconciliation_source", "reconciliation_source_label", "source_text"])
        w.writeheader()
        for p in report.get("zero_price_records", []):
            w.writerow({k: p.get(k) for k in w.fieldnames})

    summary_fields = [
        "instance_name", "instance_confidence", "session_start_label", "session_stop_label",
        "total_auction_gold", "subsidy_gold", "distributable_gold", "member_count", "average_wage_gold",
        "purchase_count", "calculated_purchase_total_gold", "purchase_total_vs_settlement_diff_gold",
        "purchase_total_vs_settlement_status", "purchase_total_vs_settlement_status_label", "purchase_total_vs_settlement_note", "purchase_source", "business_event_count", "business_kind_counts",
        "zero_price_record_count", "self_raw_money_gain_gold", "detected_personal_subsidy_gold", "self_actual_income_gold", "self_estimated_total_gain_gold",
    ]
    with summary_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_fields)
        w.writeheader()
        w.writerow({k: report.get(k) for k in summary_fields})

    return {
        "summary_csv": str(summary_csv),
        "purchases_csv": str(purchases_csv),
        "buyers_csv": str(buyers_csv),
        "zero_price_records_csv": str(zero_csv),
    }


def cmd_report(args: argparse.Namespace) -> None:
    report = extract_settlement(Path(args.session_dir), member_count=args.member_count, self_name=args.self_name, personal_subsidy_gold=args.personal_subsidy)
    out = Path(args.out) if args.out else Path(args.session_dir) / "settlement_report.md"
    ensure_dir(out.parent)
    out.write_text(render_settlement_markdown(report), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out)}, ensure_ascii=False, indent=2))


def cmd_export_csv(args: argparse.Namespace) -> None:
    report = extract_settlement(Path(args.session_dir), member_count=args.member_count, self_name=args.self_name, personal_subsidy_gold=args.personal_subsidy)
    out_dir = Path(args.out_dir) if args.out_dir else Path(args.session_dir)
    paths = export_settlement_csv(report, out_dir)
    print(json.dumps({"ok": True, "files": paths}, ensure_ascii=False, indent=2))


def cmd_app(args: argparse.Namespace) -> None:
    import jx3_click_monitor_gui_ctk

    raise SystemExit(jx3_click_monitor_gui_ctk.main())


def cmd_watch(args: argparse.Namespace) -> None:
    if args.session_dir:
        session_dir = Path(args.session_dir)
    else:
        if not args.jx3_path or not args.out_dir:
            raise SystemExit("watch 新建 session 时需要 --jx3-path 和 --out-dir；或用 --session-dir 复用已有 session")
        session_dir = create_session(Path(args.jx3_path), Path(args.out_dir), args.team_tag, "watch")
        print(json.dumps({"ok": True, "event": "started", "session_dir": str(session_dir)}, ensure_ascii=False), flush=True)
    try:
        while True:
            summary = poll_session(session_dir, limit_per_db=args.limit_per_db)
            report = extract_settlement(session_dir, member_count=args.member_count, self_name=args.self_name, personal_subsidy_gold=args.personal_subsidy)
            print(json.dumps({
                "ok": True,
                "event": "poll",
                "session_dir": str(session_dir),
                "last_poll_added": summary.get("last_poll_added"),
                "total_events": summary.get("total_events"),
                "purchase_count": report.get("purchase_count"),
                "total_auction_gold": report.get("total_auction_gold"),
                "distributable_gold": report.get("distributable_gold"),
                "average_wage_gold": report.get("average_wage_gold"),
            }, ensure_ascii=False), flush=True)
            time.sleep(max(0.5, float(args.interval)))
    except KeyboardInterrupt:
        summary = stop_session(session_dir)
        report = extract_settlement(session_dir, member_count=args.member_count, self_name=args.self_name, personal_subsidy_gold=args.personal_subsidy)
        print(json.dumps({"ok": True, "event": "stopped", "summary": summary, "report": report}, ensure_ascii=False, indent=2), flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JX3 click/team monitor MVP")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("--jx3-path", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--team-tag", default="")
    s.add_argument("--watch-mode", default="normal")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("poll")
    s.add_argument("--session-dir", required=True)
    s.add_argument("--limit-per-db", type=int, default=10000)
    s.set_defaults(func=cmd_poll)

    s = sub.add_parser("stop")
    s.add_argument("--session-dir", required=True)
    s.set_defaults(func=cmd_stop)

    s = sub.add_parser("offline-scan")
    s.add_argument("--jx3-path", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--start-ts", required=True, type=float)
    s.add_argument("--end-ts", type=float, default=None)
    s.set_defaults(func=cmd_offline_scan)

    s = sub.add_parser("analyze")
    s.add_argument("--session-dir", required=True)
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("settlement")
    s.add_argument("--session-dir", required=True)
    s.add_argument("--member-count", type=int, default=None, help="实际分工资人数；不填则从记录中估算")
    s.add_argument("--self-name", default="你", help="本机角色名/显示名，默认使用聊天日志里的'你'")
    s.add_argument("--personal-subsidy", type=float, default=None, help="你的个人补贴/补助金额；不填则尝试从工资到账-底薪推断")
    s.set_defaults(func=cmd_settlement)

    s = sub.add_parser("report")
    s.add_argument("--session-dir", required=True)
    s.add_argument("--member-count", type=int, default=None)
    s.add_argument("--self-name", default="你")
    s.add_argument("--personal-subsidy", type=float, default=None)
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("export-csv")
    s.add_argument("--session-dir", required=True)
    s.add_argument("--member-count", type=int, default=None)
    s.add_argument("--self-name", default="你")
    s.add_argument("--personal-subsidy", type=float, default=None)
    s.add_argument("--out-dir", default=None)
    s.set_defaults(func=cmd_export_csv)

    s = sub.add_parser("app")
    s.set_defaults(func=cmd_app)

    s = sub.add_parser("watch")
    s.add_argument("--session-dir", default=None, help="复用已有 session；不填则新建")
    s.add_argument("--jx3-path", default=None, help="新建 session 时必填")
    s.add_argument("--out-dir", default=None, help="新建 session 时必填")
    s.add_argument("--team-tag", default="")
    s.add_argument("--interval", type=float, default=2.0)
    s.add_argument("--limit-per-db", type=int, default=10000)
    s.add_argument("--member-count", type=int, default=None)
    s.add_argument("--self-name", default="你")
    s.add_argument("--personal-subsidy", type=float, default=None)
    s.set_defaults(func=cmd_watch)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
