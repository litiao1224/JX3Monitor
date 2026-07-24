# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Text normalization and gold amount parsing."""
from __future__ import annotations


def normalize_text(text: str | None) -> str:
    return (text or "").replace("\r", "").replace("\n", "").strip()


def parse_gold_amount_text(text: str) -> int:
    """Parse JX3 gold amount text, supporting 金砖 + 金."""
    import re

    text = normalize_text(text)
    total = 0
    m = re.search(r"(?P<brick>\d+)金砖", text)
    if m:
        total += int(m.group("brick")) * 10000
    tail = re.sub(r"\d+金砖", "", text)
    m = re.search(r"(?P<gold>\d+)金", tail)
    if m:
        total += int(m.group("gold"))
    if total:
        return total
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else 0


def get_item_icon_emoji(item_name: str | None) -> str:
    """Return a category icon emoji for JX3 auction/item records."""
    name = normalize_text(item_name)
    if not name:
        return "📦"
    if any(k in name for k in ("玄晶", "陨海晶", "化玉", "归墟", "铁马冰河", "大铁")):
        return "💎"
    if any(k in name for k in ("切糕", "牌子", "衣", "冠", "鞋", "腰", "护手", "裤", "戒指", "佩", "项链", "甲", "袍", "服", "履")):
        return "🛡️"
    if any(k in name for k in ("剑", "枪", "刀", "杖", "笔", "琴", "扇", "暗器", "双兵", "弓", "武器", "斩")):
        return "🗡️"
    if any(k in name for k in ("五彩石", "彩石", "五行石", "精炼石", "石")):
        return "🔮"
    if any(k in name for k in ("散", "丹", "酒", "宴", "桌", "小吃", "药", "玄黄散")):
        return "🧪"
    if any(k in name for k in ("马", "鞍", "挂件", "奇趣", "披风", "礼盒", "发", "外装", "坐骑")):
        return "🐴"
    if any(k in name for k in ("秘籍", "残页", "断篇", "书")):
        return "📜"
    return "📦"
