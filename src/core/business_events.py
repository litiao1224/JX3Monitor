# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Business event parsing.

Transforms raw chat events into structured business events
(auction_start, bid, final_purchase, settlement_summary, etc.).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.core.patterns import (
    AUCTION_START_RE,
    BID_RE,
    FINAL_PURCHASE_RE,
    ITEM_GAIN_RE,
    MONEY_GAIN_DETAIL_RE,
    MONEY_GAIN_RE,
    MONEY_PART_RE,
    RECORDED_SALE_RE,
    SETTLEMENT_SUMMARY_RE,
    TEAM_APPEND_INCOME_RE,
    TEAM_MSG_RE,
)
from src.core.reconciliation import settlement_snapshot_from_match
from src.core.json_io import load_jsonl
from src.core.money import copper_to_gold, money_parts_to_copper
from src.core.text_utils import normalize_text, parse_gold_amount_text


def rich_text_plain(msg: Optional[str]) -> str:
    """Join JX3 rich-text <text text="..."> nodes into readable text."""
    if not msg or "<text" not in msg:
        return ""
    import html
    import re as _re

    RICH_TEXT_TAG_RE = _re.compile(r"<text(?P<attrs>[^>]*?)(?:>(?P<body>.*?)</text>|/>)", _re.S)
    RICH_TEXT_ATTR_RE = _re.compile(r'text\s*=\s*"(?P<value>(?:\\.|[^"])*)"', _re.S)

    parts: List[str] = []
    for tag in RICH_TEXT_TAG_RE.finditer(msg):
        attrs = tag.group("attrs") or ""
        body = tag.group("body") or ""
        m = RICH_TEXT_ATTR_RE.search(attrs)
        if not m and body:
            m = RICH_TEXT_ATTR_RE.search(body)
        if m:
            val = m.group("value")
            val = html.unescape(val)
            val = val.replace('\\"', '"').replace("\\n", "\n").replace("\\r", "\r").replace("\\\n", "\n")
            parts.append(val)
        elif body:
            parts.append(html.unescape(body))
    return "".join(parts)


def event_text_candidates(e: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return prioritized (source, text) pairs for a raw event."""
    candidates: List[Tuple[str, str]] = []
    raw = normalize_text(e.get("text"))
    rich = normalize_text(rich_text_plain(e.get("msg")))
    for source, value in (("msg_rich_text", rich), ("text", raw)):
        if value and value not in [v for _, v in candidates]:
            candidates.append((source, value))
    if not candidates:
        candidates.append(("empty", ""))
    return candidates


def dedupe_events_by_time_channel_text(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate chat records that appear in multiple chatlog DBs."""
    import hashlib

    seen = set()
    out: List[Dict[str, Any]] = []
    for e in events:
        t = e.get("time")
        typ = e.get("source_type") or e.get("type") or e.get("kind") or ""
        text = normalize_text(e.get("text"))
        msg = normalize_text(e.get("msg"))
        identity = text or msg
        identity_hash = hashlib.sha1(identity.encode("utf-8", errors="replace")).hexdigest()[:16]
        if t is not None and identity:
            key = (int(t), str(typ), identity_hash)
        else:
            key = ("row", e.get("db"), e.get("rowid"), str(typ), identity_hash)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def parse_money_amount(e: Dict[str, Any]) -> Dict[str, int]:
    """Parse money gain event into gold/silver/copper breakdown."""
    msg = e.get("msg") or ""
    parts = {"gold_brick": 0, "gold": 0, "silver": 0, "copper": 0}
    name_map = {"Text_GoldB": "gold_brick", "Text_Gold": "gold", "Text_Silver": "silver", "Text_Copper": "copper"}
    for m in MONEY_PART_RE.finditer(msg):
        parts[name_map[m.group("name")]] = int(m.group("num"))
    if any(parts.values()):
        return {"gold": parts["gold_brick"] * 10000 + parts["gold"], "silver": parts["silver"], "copper": parts["copper"]}
    text = normalize_text(e.get("text"))
    md = MONEY_GAIN_DETAIL_RE.search(text)
    if md:
        return {"gold": int(md.group("gold")), "silver": int(md.group("silver")), "copper": int(md.group("copper"))}
    m = MONEY_GAIN_RE.search(text)
    if m:
        parts["gold"] = int(m.group("amount"))
    return parts


def parse_business_event(e: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a raw chat event into a structured business event."""
    text = normalize_text(e.get("text"))
    typ = e.get("type") or ""
    base = {
        "time": e.get("time"),
        "label": None,
        "source_type": typ,
        "rowid": e.get("rowid"),
        "db": e.get("db"),
        "text": text,
    }

    text_source, text = event_text_candidates(e)[0]
    base["text"] = text
    base["text_source"] = text_source

    # Auction start
    m = AUCTION_START_RE.search(text)
    if m:
        return {**base, "kind": "auction_start", "sender": m.group("sender"), "item": m.group("item")}

    # Bid
    m = BID_RE.search(text)
    if m:
        return {
            **base,
            "kind": "bid",
            "sender": m.group("sender"),
            "bidder": m.group("bidder"),
            "item": m.group("item"),
            "amount_text": m.group("amount_text"),
            "amount_gold": parse_gold_amount_text(m.group("amount_text")),
        }

    # Final purchase (may also contain settlement snapshot)
    m = FINAL_PURCHASE_RE.search(text)
    if m:
        amount_gold = parse_gold_amount_text(m.group("amount_text"))
        out = {
            **base,
            "kind": "final_purchase",
            "buyer": m.group("buyer"),
            "target": m.group("target"),
            "item": m.group("item"),
            "amount_text": m.group("amount_text"),
            "amount_gold": amount_gold,
        }
        sm = SETTLEMENT_SUMMARY_RE.search(text)
        if sm:
            snap = settlement_snapshot_from_match(sm)
            if snap:
                out["settlement_snapshot"] = snap
            else:
                out["invalid_settlement_snapshot_text"] = text
        return out

    # Settlement summary (standalone)
    sm = SETTLEMENT_SUMMARY_RE.search(text)
    if sm:
        snap = settlement_snapshot_from_match(sm)
        if not snap:
            return {**base, "kind": "invalid_settlement_summary", "text": text}
        return {**base, "kind": "settlement_summary", **snap}

    # Team append income
    am = TEAM_APPEND_INCOME_RE.search(text)
    if am:
        return {
            **base,
            "kind": "team_append_income",
            "player": am.group("player"),
            "instance": normalize_text(am.group("instance")),
            "amount_text": am.group("amount_text"),
            "amount_gold": parse_gold_amount_text(am.group("amount_text")),
        }

    # Item gain
    if typ == "MSG_ITEM":
        m = ITEM_GAIN_RE.search(text)
        if m:
            return {
                **base,
                "kind": "item_gain",
                "player": m.group("player") or "你",
                "item": m.group("item"),
                "count": int(m.group("count") or "1"),
            }

    # Money gain
    if typ == "MSG_MONEY":
        parts = parse_money_amount(e)
        if any(parts.values()):
            return {
                **base,
                "kind": "money_gain",
                "gold": parts["gold"],
                "silver": parts["silver"],
                "copper": parts["copper"],
                "amount_copper": parts["gold"] * 10000 + parts["silver"] * 100 + parts["copper"],
                "amount_gold": copper_to_gold(parts["gold"] * 10000 + parts["silver"] * 100 + parts["copper"]),
            }

    # Team message (may contain bid candidates)
    if typ == "MSG_TEAM":
        m = TEAM_MSG_RE.search(text)
        if m:
            msg = m.group("message")
            price = __import__("re").search(r"(?P<amount>\d{2,7})\s*(?:金|砖|w|W|万)?", msg)
            out = {**base, "kind": "team_message", "speaker": m.group("speaker"), "message": msg}
            cooldown_like = any(k in msg for k in ["调息", "倒计时", "秒", "冷却"])
            bid_like = any(k in msg for k in ["拍", "出", "叫", "要了", "我要", "P", "p", "金", "万", "砖"])
            if price and bid_like and not cooldown_like:
                out["bid_candidate"] = True
                out["candidate_amount"] = int(price.group("amount"))
            return out

    return None
