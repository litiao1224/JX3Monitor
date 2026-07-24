# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Event parsing.

Transforms raw chat log rows into structured game events:
trade clicks, item distributions, gold changes, whispers, etc.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.core.utils import money_parts_to_copper, normalize_text

# Pre-compiled patterns for JX3 chat events
TRADE_CLICK_RE = re.compile(
    r"(?P<role>[^@]+?)@\[点击确认交易\]",
    re.IGNORECASE
)
GIVE_GOLD_RE = re.compile(
    r"交易给\s*(?P<target>[^\s]+)\s*(?P<gold>\d+)金",
    re.IGNORECASE
)
RECEIVE_GOLD_RE = re.compile(
    r"从\s*(?P<source>[^\s]+)\s*获得\s*(?P<gold>\d+)金",
    re.IGNORECASE
)
ITEM_DISTRIBUTE_RE = re.compile(
    r"分配\s*\[?(?P<item>[^\]]+)\]?\s*给\s*(?P<target>[^\s]+)",
    re.IGNORECASE
)
SELF_ITEM_RE = re.compile(
    r"获得物品\s*\[?(?P<item>[^\]]+)\]?",
    re.IGNORECASE
)
WHISPER_RE = re.compile(
    r"你密聊\s*(?P<target>[^\s:：]+)[:：]\s*(?P<msg>.+)",
    re.IGNORECASE
)
RECEIVE_WHISPER_RE = re.compile(
    r"(?P<source>[^\s]+)\s*密聊你[:：]\s*(?P<msg>.+)",
    re.IGNORECASE
)
SYSTEM_NOTICE_RE = re.compile(
    r"\[系统\]\s*(?P<msg>.+)",
    re.IGNORECASE
)
TEAM_JOIN_RE = re.compile(
    r"(?P<role>[^@]+)\s*加入了队伍",
    re.IGNORECASE
)
TEAM_LEAVE_RE = re.compile(
    r"(?P<role>[^@]+)\s*离开了队伍",
    re.IGNORECASE
)


class EventType:
    TRADE_CONFIRM = "trade_confirm"
    GIVE_GOLD = "give_gold"
    RECEIVE_GOLD = "receive_gold"
    ITEM_DISTRIBUTE = "item_distribute"
    SELF_ITEM = "self_item"
    WHISPER_SEND = "whisper_send"
    WHISPER_RECV = "whisper_recv"
    SYSTEM_NOTICE = "system_notice"
    TEAM_JOIN = "team_join"
    TEAM_LEAVE = "team_leave"
    UNKNOWN = "unknown"


def parse_chat_text(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a single chat log text line into a structured event."""
    text = normalize_text(text)
    if not text:
        return None

    for pattern, event_type, handler in _PARSE_RULES:
        m = pattern.search(text)
        if m:
            return handler(event_type, m, text)
    return {
        "type": EventType.UNKNOWN,
        "text": text,
    }


def _make_handler(event_type: str, groups: Dict[str, Any], full_text: str) -> Dict[str, Any]:
    return {"type": event_type, **{k: v for k, v in groups.items() if v is not None}, "text": full_text}


_PARSE_RULES: List[Tuple[re.Pattern, str, Any]] = [
    (TRADE_CLICK_RE, EventType.TRADE_CONFIRM,
     lambda et, m, txt: _make_handler(et, {"role": m.group("role")}, txt)),
    (GIVE_GOLD_RE, EventType.GIVE_GOLD,
     lambda et, m, txt: {**_make_handler(et, {"target": m.group("target"), "gold": int(m.group("gold"))}, txt),
                         "gold_copper": money_parts_to_copper(gold=int(m.group("gold")))}),
    (RECEIVE_GOLD_RE, EventType.RECEIVE_GOLD,
     lambda et, m, txt: {**_make_handler(et, {"source": m.group("source"), "gold": int(m.group("gold"))}, txt),
                         "gold_copper": money_parts_to_copper(gold=int(m.group("gold")))}),
    (ITEM_DISTRIBUTE_RE, EventType.ITEM_DISTRIBUTE,
     lambda et, m, txt: _make_handler(et, {"item": m.group("item"), "target": m.group("target")}, txt)),
    (SELF_ITEM_RE, EventType.SELF_ITEM,
     lambda et, m, txt: _make_handler(et, {"item": m.group("item")}, txt)),
    (WHISPER_RE, EventType.WHISPER_SEND,
     lambda et, m, txt: _make_handler(et, {"target": m.group("target"), "message": m.group("msg")}, txt)),
    (RECEIVE_WHISPER_RE, EventType.WHISPER_RECV,
     lambda et, m, txt: _make_handler(et, {"source": m.group("source"), "message": m.group("msg")}, txt)),
    (SYSTEM_NOTICE_RE, EventType.SYSTEM_NOTICE,
     lambda et, m, txt: _make_handler(et, {"message": m.group("msg")}, txt)),
    (TEAM_JOIN_RE, EventType.TEAM_JOIN,
     lambda et, m, txt: _make_handler(et, {"role": m.group("role")}, txt)),
    (TEAM_LEAVE_RE, EventType.TEAM_LEAVE,
     lambda et, m, txt: _make_handler(et, {"role": m.group("role")}, txt)),
]


def parse_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse a batch of raw chat log rows into events."""
    events = []
    for row in rows:
        text = row.get("text") or row.get("msg") or ""
        parsed = parse_chat_text(text)
        if parsed is None:
            continue
        event = {
            **parsed,
            "time": row.get("time"),
            "rowid": row.get("rowid"),
            "db": row.get("db", ""),
            "raw_text": text,
        }
        events.append(event)
    return events


def batch_parse(raw_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Parse raw rows; return (events, skipped_count)."""
    events = []
    skipped = 0
    for row in raw_rows:
        text = row.get("text") or row.get("msg") or ""
        parsed = parse_chat_text(text)
        if parsed is None:
            skipped += 1
            continue
        event = {
            **parsed,
            "time": row.get("time"),
            "rowid": row.get("rowid"),
            "db": row.get("db", ""),
            "raw_text": text,
        }
        events.append(event)
    return events, skipped
