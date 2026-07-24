# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Core utilities.

Re-exports from split modules for backward compatibility.
New code should import from the specific submodule directly.
"""
from __future__ import annotations

# Path helpers
from src.core.paths import (
    DEFAULT_CHATLOG_GLOB,
    item_matches_rule,
    resolve_zhcn_hd_path,
    wildcard_to_regex,
)

# Timestamp helpers
from src.core.timestamps import (
    APP_VERSION,
    now_ts,
    parse_local_datetime_ts,
    session_time_id,
    stable_hash,
    ts_label,
    unique_session_dir,
)

# JSON I/O
from src.core.json_io import (
    append_jsonl,
    count_jsonl,
    ensure_dir,
    load_jsonl,
    read_json,
    write_json,
    write_jsonl,
)

# Money conversion
from src.core.money import copper_to_gold, money_parts_to_copper

# Text helpers
from src.core.text_utils import normalize_text, parse_gold_amount_text

# Income memory
from src.core.income_memory import load_income_memory, save_income_memory

# Re-export business event helpers that some callers depend on
from src.core.business_events import (
    dedupe_events_by_time_channel_text,
    event_text_candidates,
    parse_business_event,
    parse_money_amount,
    rich_text_plain,
)

# Re-export settlement helpers that CLI depends on
from src.core.settlement import (
    analyze_session,
    build_settlement_report,
    extract_settlement,
)

# Re-export identity helpers
from src.core.identity_inference import (
    apply_identity_override,
    current_identity_from_jx3_path,
    extract_login_account_from_userdata_db,
    find_zhcn_hd_root,
    identity_from_path,
    identity_from_mydata_dir,
    infer_identity_from_session_files,
    mydata_dir_latest_mtime,
    parse_info_jx3dat,
)

# Re-export instance detection
from src.core.instance_detect import detect_instance_name, infer_dungeon_from_items

__all__ = [
    # Paths
    "DEFAULT_CHATLOG_GLOB",
    "resolve_zhcn_hd_path",
    "wildcard_to_regex",
    "item_matches_rule",
    # Timestamps
    "APP_VERSION",
    "now_ts",
    "ts_label",
    "session_time_id",
    "unique_session_dir",
    "stable_hash",
    "parse_local_datetime_ts",
    # JSON I/O
    "ensure_dir",
    "read_json",
    "write_json",
    "append_jsonl",
    "write_jsonl",
    "load_jsonl",
    "count_jsonl",
    "load_income_memory",
    "save_income_memory",
    # Money
    "money_parts_to_copper",
    "copper_to_gold",
    # Text
    "normalize_text",
    "parse_gold_amount_text",
    # Business events
    "rich_text_plain",
    "event_text_candidates",
    "dedupe_events_by_time_channel_text",
    "parse_business_event",
    "parse_money_amount",
    # Settlement
    "analyze_session",
    "extract_settlement",
    "build_settlement_report",
    # Identity
    "parse_info_jx3dat",
    "extract_login_account_from_userdata_db",
    "mydata_dir_latest_mtime",
    "find_zhcn_hd_root",
    "identity_from_mydata_dir",
    "current_identity_from_jx3_path",
    "identity_from_path",
    "apply_identity_override",
    "infer_identity_from_session_files",
    # Instance
    "detect_instance_name",
    "infer_dungeon_from_items",
]
