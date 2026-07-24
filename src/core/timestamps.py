# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Timestamp helpers."""
from __future__ import annotations

import re
import time
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

APP_VERSION = "1.0.0"


def now_ts() -> float:
    return time.time()


def ts_label(ts: Optional[float] = None) -> str:
    if ts is None:
        ts = now_ts()
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def session_time_id(ts: Optional[float] = None) -> str:
    """Human-readable session folder name based on the start time."""
    if ts is None:
        ts = now_ts()
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d_%H-%M-%S")


def unique_session_dir(out_dir: Path, base_id: str) -> tuple[str, Path]:
    """Return a non-existing session id/path under out_dir."""
    session_id = base_id
    session_dir = out_dir / session_id
    n = 2
    while session_dir.exists():
        session_id = f"{base_id}_{n:02d}"
        session_dir = out_dir / session_id
        n += 1
    return session_id, session_dir


def stable_hash(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def parse_local_datetime_ts(text: str) -> float:
    """Parse various datetime string formats to Unix timestamp."""
    text = (text or "").replace("\r", "").replace("\n", "").strip()
    if not text:
        raise ValueError("时间不能为空")
    m = re.search(r"\b(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<hm>\d{1,2}:\d{2})(?::(?P<s>\d{2}))?\s+GMT[+-]\d+\b", text)
    if m:
        text = f"{m.group('date')} {m.group('hm')}:{m.group('s') or '00'}"
    if re.fullmatch(r"\d{14}", text):
        return datetime.strptime(text, "%Y%m%d%H%M%S").timestamp()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            pass
    raise ValueError("时间格式应为 2026-06-12 21:58 或 2026-06-12 21:58:00")
