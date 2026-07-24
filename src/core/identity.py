# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Role identity and mapping.

Maps player names to roles/classes, guild affiliations,
and provides lookup helpers for settlement attribution.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.core.utils import normalize_text, read_json, write_json, ensure_dir

IDENTITY_FILE = "role_identity.json"

# Common JX3 class names for auto-detection
KNOWN_CLASSES: Set[str] = {
    "纯阳", "万花", "七秀", "少林", "天策", "藏剑", "五毒", "唐门", "明教",
    "丐帮", "苍云", "长歌", "霸刀", "蓬莱", "凌雪", "衍天", "药宗", "刀宗",
    "孤云", "灵源",
}

KNOWN_SPECS: Dict[str, List[str]] = {
    "纯阳": ["紫霞", "太虚", "纯阳"],
    "万花": ["离经", "花间", "万花"],
    "七秀": ["冰心", "云裳", "七秀"],
    "少林": ["易筋", "洗髓", "少林"],
    "天策": ["傲血", "铁牢", "天策"],
    "藏剑": ["问水", "山居", "藏剑"],
    "五毒": ["毒经", "补天", "五毒"],
    "唐门": ["惊羽", "天罗", "唐门"],
    "明教": ["焚影", "明尊", "明教"],
    "丐帮": ["笑尘", "丐帮"],
    "苍云": ["分山", "铁骨", "苍云"],
    "长歌": ["莫问", "相知", "长歌"],
    "霸刀": ["北傲", "霸刀"],
    "蓬莱": ["凌海", "蓬莱"],
    "凌雪": ["隐龙", "凌雪"],
    "衍天": ["太玄", "衍天"],
    "药宗": ["无方", "药宗"],
    "刀宗": ["孤锋", "刀宗"],
}


class RoleIdentity:
    """Stores identity info for a single role."""

    def __init__(
        self,
        name: str,
        server: str = "",
        player_class: str = "",
        spec: str = "",
        notes: str = "",
    ):
        self.name = name
        self.server = server
        self.player_class = player_class
        self.spec = spec
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "server": self.server,
            "class": self.player_class,
            "spec": self.spec,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoleIdentity":
        return cls(
            name=data.get("name", ""),
            server=data.get("server", ""),
            player_class=data.get("class", ""),
            spec=data.get("spec", ""),
            notes=data.get("notes", ""),
        )


class IdentityStore:
    """Persistent store for role identity mappings."""

    def __init__(self, path: Path):
        self.path = Path(path) / IDENTITY_FILE
        self.identities: Dict[str, RoleIdentity] = {}
        self._load()

    def _load(self) -> None:
        data = read_json(self.path, None)
        if data and isinstance(data, dict):
            for name, info in data.items():
                self.identities[name] = RoleIdentity.from_dict(info)

    def save(self) -> None:
        data = {name: ident.to_dict() for name, ident in self.identities.items()}
        write_json(self.path, data)

    def get(self, name: str) -> Optional[RoleIdentity]:
        return self.identities.get(normalize_text(name))

    def set(self, identity: RoleIdentity) -> None:
        self.identities[normalize_text(identity.name)] = identity

    def remove(self, name: str) -> bool:
        key = normalize_text(name)
        if key in self.identities:
            del self.identities[key]
            return True
        return False

    def all(self) -> List[RoleIdentity]:
        return list(self.identities.values())

    def lookup(self, name: str) -> RoleIdentity:
        """Return identity or create a blank one for unknown name."""
        ident = self.get(name)
        if ident is None:
            ident = RoleIdentity(name=name)
            self.set(ident)
        return ident

    def merge_from_text(self, text: str) -> int:
        """Parse role entries from plain text (name@class@server format)."""
        count = 0
        for line in text.splitlines():
            line = normalize_text(line)
            if not line:
                continue
            parts = line.split("@")
            if len(parts) >= 2:
                name = parts[0].strip()
                player_class = parts[1].strip() if len(parts) > 1 else ""
                server = parts[2].strip() if len(parts) > 2 else ""
                if name:
                    self.set(RoleIdentity(name=name, player_class=player_class, server=server))
                    count += 1
        return count


def detect_class_from_text(text: str) -> str:
    """Try to detect a JX3 class name from arbitrary text."""
    text = normalize_text(text)
    for cls_name in KNOWN_CLASSES:
        if cls_name in text:
            return cls_name
    return ""


def detect_spec_from_text(text: str, player_class: str = "") -> str:
    """Try to detect a spec name from text given a class."""
    text = normalize_text(text)
    if player_class and player_class in KNOWN_SPECS:
        for spec in KNOWN_SPECS[player_class]:
            if spec in text:
                return spec
    return ""
