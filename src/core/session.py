# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Session management.

Handles session lifecycle: creation, persistence, loading, and metadata.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.utils import (
    ensure_dir,
    read_json,
    write_json,
    ts_label,
    session_time_id,
    unique_session_dir,
)

SESSION_META_NAME = "session_meta.json"
SESSION_STATE_NAME = "session_state.json"


@dataclass
class SessionConfig:
    """User-configurable session parameters."""
    role_name: str = ""
    server: str = ""
    dungeon_name: str = ""
    jx3_path: str = ""
    out_dir: str = ""
    scan_interval_ms: int = 1000
    auto_settle: bool = True
    split_role: bool = True
    split_item: bool = True
    plugin_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionMeta:
    """Session metadata persisted to disk."""
    session_id: str = ""
    session_dir: str = ""
    start_time: float = 0.0
    config: SessionConfig = field(default_factory=SessionConfig)
    created_at: str = ""
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(d.get("config"), SessionConfig):
            d["config"] = asdict(self.config)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMeta":
        cfg_data = data.get("config", {})
        cfg = SessionConfig(**{k: v for k, v in cfg_data.items() if k in SessionConfig.__dataclass_fields__})
        return cls(
            session_id=data.get("session_id", ""),
            session_dir=data.get("session_dir", ""),
            start_time=data.get("start_time", 0.0),
            config=cfg,
            created_at=data.get("created_at", ""),
            version=data.get("version", 1),
        )


@dataclass
class SessionState:
    """Runtime tracking state persisted for crash recovery."""
    max_rowid: int = 0
    last_scan_time: float = 0.0
    events_processed: int = 0
    last_event_time: float = 0.0
    is_running: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        return cls(
            max_rowid=data.get("max_rowid", 0),
            last_scan_time=data.get("last_scan_time", 0.0),
            events_processed=data.get("events_processed", 0),
            last_event_time=data.get("last_event_time", 0.0),
            is_running=data.get("is_running", False),
        )


def create_session(
    out_root: Path,
    config: Optional[SessionConfig] = None,
    start_time: Optional[float] = None,
) -> SessionMeta:
    """Create a new session directory and return its metadata."""
    if config is None:
        config = SessionConfig()
    if start_time is None:
        start_time = time.time()

    base_id = session_time_id(start_time)
    session_id, session_dir = unique_session_dir(out_root, base_id)
    ensure_dir(session_dir)
    ensure_dir(session_dir / "raw")
    ensure_dir(session_dir / "parsed")
    ensure_dir(session_dir / "reports")

    meta = SessionMeta(
        session_id=session_id,
        session_dir=str(session_dir),
        start_time=start_time,
        config=config,
        created_at=ts_label(start_time),
    )
    save_session_meta(meta)
    save_session_state(session_dir, SessionState())
    return meta


def save_session_meta(meta: SessionMeta) -> None:
    path = Path(meta.session_dir) / SESSION_META_NAME
    write_json(path, meta.to_dict())


def load_session_meta(session_dir: Path) -> Optional[SessionMeta]:
    path = session_dir / SESSION_META_NAME
    data = read_json(path, None)
    if data is None:
        return None
    return SessionMeta.from_dict(data)


def save_session_state(session_dir: Path, state: SessionState) -> None:
    path = session_dir / SESSION_STATE_NAME
    write_json(path, state.to_dict())


def load_session_state(session_dir: Path) -> SessionState:
    path = session_dir / SESSION_STATE_NAME
    data = read_json(path, None)
    if data is None:
        return SessionState()
    return SessionState.from_dict(data)


def list_sessions(out_root: Path) -> List[SessionMeta]:
    """Scan output directory for existing sessions, sorted newest first."""
    sessions = []
    root = Path(out_root)
    if not root.exists():
        return []
    for entry in sorted(root.iterdir(), reverse=True):
        if entry.is_dir() and (entry / SESSION_META_NAME).exists():
            meta = load_session_meta(entry)
            if meta:
                sessions.append(meta)
    return sessions


def delete_session(session_dir: Path) -> bool:
    """Remove a session directory and all its data."""
    import shutil
    path = Path(session_dir)
    if not path.exists():
        return False
    try:
        shutil.rmtree(path)
        return True
    except Exception:
        return False
