# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Core module.

Provides session management, chat log scanning, event parsing,
settlement computation, role identity, and report generation.

Import from specific submodules directly for best results.
This __init__.py re-exports the most commonly-used symbols.
"""
from __future__ import annotations

# Session management
from src.core.session import (
    SessionConfig,
    SessionMeta,
    SessionState,
    create_session,
    list_sessions,
    load_session_meta,
    load_session_state,
    save_session_meta,
    save_session_state,
    delete_session,
)

# Scanner
from src.core.scanner import (
    find_chatlog_dbs,
    query_chatlog_rows,
    connect_readonly,
)

# Parser
from src.core.parser import (
    EventType,
    parse_chat_text,
    parse_events,
    batch_parse,
)

# Settlement engine (the main orchestrator)
from src.core.settlement import (
    extract_settlement,
    analyze_session,
    build_settlement_report,
)

# Identity store
from src.core.identity import (
    RoleIdentity,
    IdentityStore,
    detect_class_from_text,
    detect_spec_from_text,
)

# Report generation
from src.core.report import (
    format_gold,
    build_text_report,
    build_json_report,
    save_text_report,
    save_json_report,
    export_reports,
)

# Version constant
from src.core.timestamps import APP_VERSION

__all__ = [
    "APP_VERSION",
    "SessionConfig",
    "SessionMeta",
    "SessionState",
    "create_session",
    "list_sessions",
    "load_session_meta",
    "load_session_state",
    "save_session_meta",
    "save_session_state",
    "delete_session",
    "find_chatlog_dbs",
    "query_chatlog_rows",
    "connect_readonly",
    "EventType",
    "parse_chat_text",
    "parse_events",
    "batch_parse",
    "extract_settlement",
    "analyze_session",
    "build_settlement_report",
    "RoleIdentity",
    "IdentityStore",
    "detect_class_from_text",
    "detect_spec_from_text",
    "format_gold",
    "build_text_report",
    "build_json_report",
    "save_text_report",
    "save_json_report",
    "export_reports",
]
