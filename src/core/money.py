# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Money conversion helpers.

JX3 currency: 1金 = 100银 = 10000铜.
"""
from __future__ import annotations


def money_parts_to_copper(gold: int = 0, silver: int = 0, copper: int = 0) -> int:
    return int(gold) * 10000 + int(silver) * 100 + int(copper)


def copper_to_gold(copper: int) -> float:
    return int(copper) / 10000


def fmt_money(value: object) -> str:
    """将茗伊 userdata 的 {nGold, nSilver, nCopper} 字典格式化为 '金银铜' 字符串。"""
    if not isinstance(value, dict):
        return ""
    try:
        gold = int(float(value.get("nGold") or 0))
        silver = int(float(value.get("nSilver") or 0))
        copper = int(float(value.get("nCopper") or 0))
    except Exception:
        return ""
    return f"{gold}金{silver}银{copper}铜"
