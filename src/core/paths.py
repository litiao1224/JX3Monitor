# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Path resolution and JX3 item wildcards."""
from __future__ import annotations

import os
import re
from pathlib import Path


DEFAULT_CHATLOG_GLOB = os.path.join("interface", "my#data", "**", "userdata", "chat_log", "chatlog_*.v2.db")


def resolve_zhcn_hd_path(path: Path | str) -> Path:
    """Resolve a configured JX3 path to zhcn_hd when possible."""
    p = Path(path or ".").expanduser()
    try:
        p = p.resolve()
    except Exception:
        pass
    if p.is_file():
        p = p.parent
    if p.name.lower() == "zhcn_hd":
        return p
    for parent in p.parents:
        if parent.name.lower() == "zhcn_hd":
            return parent
    for candidate in (p / "bin" / "zhcn_hd", p / "zhcn_hd", p / "Game" / "JX3" / "bin" / "zhcn_hd"):
        if candidate.exists():
            return candidate
    return p


def find_zhcn_hd_dir(jx3_path: str | Path) -> Path:
    """Find the root zhcn_hd directory."""
    from src.config import DEFAULT_JX3_PATH
    return resolve_zhcn_hd_path(Path(jx3_path or DEFAULT_JX3_PATH))


def find_interface_dir(jx3_path: str | Path) -> Path | None:
    """Find the JX3 interface plugin directory from the configured JX3 path."""
    from src.config import DEFAULT_JX3_PATH
    base = Path(jx3_path or DEFAULT_JX3_PATH).expanduser()
    if base.name.lower() == "interface" and base.exists():
        return base
    root = find_zhcn_hd_dir(base)
    for candidate in (root / "interface", root / "Interface", base / "interface", base / "Interface"):
        if candidate.exists():
            return candidate
    return None


def find_plugin_data_dir(jx3_path: str | Path, dirname: str) -> Path | None:
    """Find plugin data directory, e.g. my#data or lm#data, under the JX3 interface folder."""
    from src.config import DEFAULT_JX3_PATH
    base = Path(jx3_path or DEFAULT_JX3_PATH).expanduser()
    target = dirname.lower()
    if base.name.lower() == target and base.exists():
        return base
    interface_dir = find_interface_dir(base)
    candidates: list[Path] = []
    if interface_dir:
        candidates.extend([interface_dir / dirname, interface_dir / dirname.upper()])
    candidates.extend([base / dirname, base / dirname.upper()])
    for p in candidates:
        if p.exists():
            return p
    if interface_dir and interface_dir.exists():
        for p in interface_dir.iterdir():
            if p.is_dir() and p.name.lower() == target:
                return p
    return None


def wildcard_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert JX3 item wildcard rules like 玄阙*·** to a regex."""
    out = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        else:
            out.append(re.escape(ch))
    return re.compile("^" + "".join(out) + "$")


def item_matches_rule(item: str, pattern: str) -> bool:
    """Match a JX3 item name against a wildcard pattern."""
    item = (item or "").replace("\r", "").replace("\n", "").strip()
    pattern = (pattern or "").replace("\r", "").replace("\n", "").strip()
    if not item or not pattern:
        return False
    if "*" in pattern:
        return bool(wildcard_to_regex(pattern).match(item))
    return item == pattern or pattern in item
