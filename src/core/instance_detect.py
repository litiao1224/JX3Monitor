# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Instance / dungeon detection.

Infers which dungeon/instance a session belongs to from chat text
and item names.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.patterns import (
    DUNGEON_DETECT_RULES,
    INSTANCE_NAME_STOPWORDS,
    INSTANCE_TEXT_PATTERNS,
    KNOWN_INSTANCE_NAMES,
)
from src.core.json_io import load_jsonl
from src.core.text_utils import normalize_text
from src.core.paths import item_matches_rule


def infer_dungeon_from_items(items: List[str]) -> Optional[Dict[str, Any]]:
    """Infer dungeon from a list of item names using dynamic regex and wildcard rules."""
    cleaned = [normalize_text(x).strip("[]") for x in items if normalize_text(x).strip("[]")]
    if not cleaned:
        return None

    # Strategy 1: Dynamic regex extraction from Treasure Token (铁证)
    treasure_regex = re.compile(r"秘境(?:宝箱|宝藏)?(?:碎片)?·([^\s\[\]]+)")
    for item in cleaned:
        m = treasure_regex.search(item)
        if m:
            extracted_name = m.group(1).strip()
            matched_dungeon = extracted_name
            core_name = re.sub(r"^(?:25人|10人|二十五人|十人)?(?:英雄|普通|挑战|全难度)?", "", extracted_name)
            
            # Try to map to a standardized name in the static dictionary
            if core_name:
                for rule in DUNGEON_DETECT_RULES:
                    rule_name = str(rule.get("dungeon", ""))
                    if core_name in rule_name:
                        # Ensure difficulty matches before mapping
                        is_heroic = "英雄" in extracted_name and "英雄" in rule_name
                        is_normal = "普通" in extracted_name and "普通" in rule_name
                        is_challenge = "挑战" in extracted_name and "挑战" in rule_name
                        if is_heroic or is_normal or is_challenge:
                            matched_dungeon = rule_name
                            break
            
            return {
                "name": matched_dungeon,
                "confidence": "confirmed",
                "source": "dynamic_treasure_regex",
                "matched_items": [item],
                "matched_count": 1,
            }

    # Strategy 2: Static dictionary wildcard rules (兜底)
    scores: List[Dict[str, Any]] = []
    for rule in DUNGEON_DETECT_RULES:
        hits = []
        for item in cleaned:
            if any(item_matches_rule(item, pat) for pat in rule.get("items", [])):
                hits.append(item)
        if hits:
            scores.append({
                "name": rule["dungeon"],
                "confidence": "guessed",
                "source": "dungeon_detect_item_rules",
                "matched_items": sorted(set(hits))[:20],
                "matched_count": len(hits),
            })
    if not scores:
        return None

    def rank(row: Dict[str, Any]) -> tuple:
        exact = 1 if any("秘境宝藏" in x for x in row.get("matched_items") or []) else 0
        return (exact, int(row.get("matched_count") or 0), str(row.get("name") or ""))

    return sorted(scores, key=rank)[-1]


def detect_instance_name_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Detect instance/dungeon name from a single chat text line."""
    text = normalize_text(text)
    if not text:
        return None
    for name in KNOWN_INSTANCE_NAMES:
        if name in text:
            return {"name": name, "confidence": "confirmed", "source": "known_name_in_text", "source_text": text[:240]}
    for pat in INSTANCE_TEXT_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        name = normalize_text(m.group("name"))
        name = re.sub(r"^(?:25人|10人|二十五人|十人)?(?:英雄|普通|挑战|全难度)?", "", name)
        bad_fragments = ["拍团", "总收入", "补贴", "叫价", "购买", "房主请注意", "本服", "跨服", "我已", "已进入"]
        if 2 <= len(name) <= 16 and name not in INSTANCE_NAME_STOPWORDS and not any(x in name for x in bad_fragments):
            return {"name": name, "confidence": "confirmed", "source": "instance_text_pattern", "source_text": text[:240]}
    return None


def detect_instance_name(session_dir: Path) -> Dict[str, Any]:
    """Detect the instance/dungeon for a session using multiple strategies."""
    raw_events = list(load_jsonl(session_dir / "raw_events.jsonl") or [])

    # Collect items from business events (parsed, has 'kind' field)
    business_events = list(load_jsonl(session_dir / "business_events.jsonl") or [])
    items: List[str] = []
    for e in business_events:
        kind = e.get("kind") or ""
        if kind in {"auction_start", "final_purchase", "item_gain", "bid"} and e.get("item"):
            items.append(str(e.get("item") or ""))

    # Also extract items from raw_events MSG_ITEM type (fallback for when
    # business_events.jsonl hasn't been generated yet or is empty)
    if not items:
        import re as _re
        _item_re = _re.compile(r'\[([^\]]+)\]')
        for e in raw_events:
            typ = e.get("type") or ""
            if typ == "MSG_ITEM":
                text = normalize_text(e.get("text") or "")
                for m in _item_re.finditer(text):
                    items.append(m.group(1))

    # Strategy 1: dungeon detect rules
    rule_hit = infer_dungeon_from_items(items)
    if rule_hit:
        return rule_hit

    # Strategy 2: text patterns on raw events
    for e in raw_events:
        text = normalize_text(e.get("text") or "")
        rich = normalize_text(e.get("msg") or "")
        for candidate in (rich, text):
            if candidate:
                hit = detect_instance_name_from_text(candidate)
                if hit:
                    return hit

    # Strategy 3: item/business text fallback
    for e in raw_events:
        text = " ".join(str(e.get(k) or "") for k in ["item", "text", "source_text"])
        for name in KNOWN_INSTANCE_NAMES:
            if name in text:
                return {"name": name, "confidence": "guessed", "source": "item_or_business_text", "source_text": text[:240]}

    return {"name": "未识别", "confidence": "unknown", "source": "none"}


# ── 副本秘境 map_id → 可读名称（通用工具，供 GUI 层调用） ─────────────

# 内置 map_id 提示（仅作 jx3box_map 未能覆盖时的 fallback）
_DUNGEON_NAME_HINTS: Dict[int, str] = {
    1670: "25人英雄闻风悬城",
    1671: "25人普通闻风悬城",
    1706: "25人英雄·会战弓月城",
    1733: "25人英雄·阆风悬城",
    1734: "25人普通·阆风悬城",
    1735: "25人挑战·缚罪之渊",
    1752: "25人挑战·元心殿",
}


def dungeon_display_name(map_id: int) -> str:
    """将秘境 map_id 转为可读副本名称（先查 jx3box_map，再查内置提示）。"""
    try:
        from src.core import jx3box_map
        name = jx3box_map.get_dungeon_name(map_id)
        if name:
            return name
    except Exception:
        pass
    return _DUNGEON_NAME_HINTS.get(map_id, f"秘境#{map_id}")
