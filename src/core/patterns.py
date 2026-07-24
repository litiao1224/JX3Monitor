# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Business event parsing constants and patterns.

All regex patterns, lookup tables, and label mappings used by the
settlement engine.  Kept in a dedicated module to avoid bloating
``settlement.py`` with 300+ lines of constants.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List


# ── Rich-text helpers ──────────────────────────────────────────

RICH_TEXT_TAG_RE = re.compile(
    r"<text(?P<attrs>[^>]*?)(?:>(?P<body>.*?)</text>|/>)", re.S
)
RICH_TEXT_ATTR_RE = re.compile(
    r'text\s*=\s*"(?P<value>(?:\\.|[^"])*)"', re.S
)

# ── Exported text patterns ─────────────────────────────────────

HTML_EXPORT_TITLE_RE = re.compile(
    r"(?P<role>[^@<>\r\n]+)\s*@\s*(?P<server>[^<\r\n]+?)\s+Exported at\s+(?P<exported_at>\d{14})"
)

# ── Auction / bidding patterns ─────────────────────────────────

AUCTION_START_RE = re.compile(
    r"\[(?P<channel>[^\]]+)\]\[(?P<sender>[^\]]+)\]\s*[：:]\s*\[(?P<item>[^\]]+)\]\s*开始拍卖"
)
BID_RE = re.compile(
    r"\[(?P<channel>[^\]]+)\]\[(?P<sender>[^\]]+)\]\s*[：:]\s*\[(?P<bidder>[^\]]+)\]\s*以\[(?P<amount_text>[^\]]+)\]\s*叫价\[(?P<item>[^\]]+)\]"
)
FINAL_PURCHASE_RE = re.compile(
    r"\[(?P<buyer>[^\]]+)\]\s*花费\[(?P<amount_text>[^\]]+)\]\s*(?:帮\[(?P<target>[^\]]+)\])?\s*购买了\[(?P<item>[^\]]+)\]"
)
RECORDED_SALE_RE = re.compile(
    r"\[(?P<seller>[^\]]+)\]\s*将\[(?P<item>[^\]]+)\]\s*以\[(?P<amount_text>[^\]]+)\]\s*记录给了\[(?P<buyer>[^\]]+)\]"
)

# ── Settlement snapshot pattern ────────────────────────────────

SETTLEMENT_SUMMARY_RE = re.compile(
    r"拍团\s*目前\s*总\s*收入(?:为)?\s*[：:]\s*(?P<total>\d+)\s*金\s*[，,]\s*补贴\s*(?:总\s*)?费用\s*[：:]\s*(?P<subsidy>\d+)\s*金\s*[，,]\s*实际\s*可\s*(?:用\s*)?分配\s*(?:金额|资金)?\s*[：:]\s*(?P<distributable>\d+)\s*金\s*[，,]\s*分配\s*人数\s*[：:]\s*(?P<members>\d+)\s*(?:人)?\s*[，,]\s*每人\s*底薪\s*[：:]\s*(?P<wage>\d+)\s*金"
)

TEAM_APPEND_INCOME_RE = re.compile(
    r"\[(?P<player>[^\]]+)\]\s*于\s*(?P<instance>.*?)\s*向团队里追加了\[(?P<amount_text>[^\]]+)\]\s*，?请前往\s*(?P=instance)\s*打开拍团记录界面查看"
)

# ── Item / money gain patterns ─────────────────────────────────

ITEM_GAIN_RE = re.compile(
    r"^(?:(?P<player>.+?)获得[：:]\s*|你获得[：:]\s*)\[(?P<item>[^\]]+)\](?:\s*[×xX*]\s*(?P<count>\d+))?"
)
MONEY_GAIN_RE = re.compile(r"^你获得：(?P<amount>\d+)")
MONEY_GAIN_DETAIL_RE = re.compile(r"^你获得：(?P<gold>\d+)金(?P<silver>\d+)银(?P<copper>\d+)铜")
MONEY_PART_RE = re.compile(
    r'text="(?P<num>\d+)"[^<>]*name="(?P<name>Text_GoldB|Text_Gold|Text_Silver|Text_Copper)"'
)

# ── Team message pattern ───────────────────────────────────────

TEAM_MSG_RE = re.compile(r"^\[团队\]\[(?P<speaker>[^\]]+)\]：(?P<message>.*)$")

# ── Instance / dungeon detection ───────────────────────────────

DEFAULT_KNOWN_INSTANCE_NAMES: List[str] = [
    "阆风悬城", "会战弓月城", "元心殿", "缚罪之渊",
    "闻风悬城", "冷龙峰", "九老洞", "一之窟", "河阳之战", "河阳", "范阳夜变", "范阳",
    "达摩洞", "敖龙岛", "辉天堑", "太一玄宫", "武狱黑牢", "永王行宫",
    "千雷殿", "锻刀厅", "狼神殿", "上阳宫", "风雷刀谷", "白帝江关",
    "荻花圣殿", "烛龙殿", "血战天策", "秦皇陵", "大明宫", "稻香秘事",
]

KNOWN_INSTANCE_NAMES: List[str] = list(DEFAULT_KNOWN_INSTANCE_NAMES)

INSTANCE_TEXT_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"(?:进入|来到|抵达|离开)(?:了)?(?P<name>[^，。\s\[\]]{2,16})(?:秘境|副本|团队秘境)?"),
    re.compile(r"(?P<name>[^，。\s\[\]]{2,16})(?:秘境|副本|团队秘境)"),
    re.compile(r"(?:当前|所在)(?:地图|场景|副本|秘境)[:：\s]*(?P<name>[^，。\s\[\]]{2,16})"),
]

INSTANCE_NAME_STOPWORDS = {"本服", "跨服", "本服秘境", "跨服秘境", "秘境", "副本", "团队秘境"}

# ── Dungeon detection rules ────────────────────────────────────

DEFAULT_DUNGEON_DETECT_RULES: List[Dict[str, object]] = [
    {"dungeon": "25人英雄闻风悬城", "items": ["秘境宝箱·英雄闻风悬城", "秘境宝藏·英雄闻风悬城", "秘境宝藏碎片·英雄闻风悬城"]},
    {"dungeon": "25人普通闻风悬城", "items": ["秘境宝箱·普通闻风悬城", "秘境宝藏·普通闻风悬城", "秘境宝藏碎片·普通闻风悬城"]},
    {"dungeon": "25人英雄·会战弓月城", "items": ["秘境宝藏碎片·英雄会战弓月城", "牧川*·**"]},
    {"dungeon": "25人英雄·阆风悬城", "items": ["秘境宝藏碎片·英雄阆风悬城", "玄阙*·**"]},
    {"dungeon": "25人普通·阆风悬城", "items": ["秘境宝藏·普通阆风悬城", "牧川*·**"]},
    {"dungeon": "25人挑战·缚罪之渊", "items": ["山海·白虹·**（**）"]},
    {"dungeon": "25人挑战·元心殿", "items": ["暗影·白虹·**（**）"]},
]

DUNGEON_DETECT_RULES: List[Dict[str, object]] = list(DEFAULT_DUNGEON_DETECT_RULES)

def load_dungeon_rules():
    global KNOWN_INSTANCE_NAMES, DUNGEON_DETECT_RULES
    try:
        # Resolve the root directory of the project (assuming src/core/patterns.py)
        root_dir = Path(__file__).resolve().parent.parent.parent
        rules_path = root_dir / "dungeon_rules.json"
        
        if rules_path.exists():
            with open(rules_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "known_instance_names" in data:
                    KNOWN_INSTANCE_NAMES = data["known_instance_names"]
                if "dungeon_detect_rules" in data:
                    DUNGEON_DETECT_RULES = data["dungeon_detect_rules"]
        else:
            # Auto-generate the default JSON template
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "known_instance_names": DEFAULT_KNOWN_INSTANCE_NAMES,
                    "dungeon_detect_rules": DEFAULT_DUNGEON_DETECT_RULES
                }, f, ensure_ascii=False, indent=4)
    except Exception:
        # Fallback silently to defaults if anything fails
        pass

# Initialize from JSON (or create it) when this module loads
load_dungeon_rules()

# ── Reconciliation source labels ───────────────────────────────

RECONCILIATION_SOURCE_LABELS: Dict[str, str] = {
    "explicit_final_purchase": "明确成交/购买记录",
    "explicit_zero_purchase": "0金拾取/分配记录",
    "auction_fallback": "叫价兜底",
    "auction_fallback_missing_or_zero_final": "叫价补价",
}

PURCHASE_GAP_STATUS_LABELS: Dict[str, str] = {
    "match": "一致",
    "settlement_gt_sales": "工资条高于明确成交",
    "sales_gt_settlement": "明确成交高于工资条",
    "unknown": "未知",
}
