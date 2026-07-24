# -*- coding: utf-8 -*-
"""JX3 Click Monitor - SQLite chat log scanner.

Reads JX3 local chat SQLite logs without interfering with the game.
"""
from __future__ import annotations

import glob
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.utils import (
    DEFAULT_CHATLOG_GLOB,
    now_ts,
    resolve_zhcn_hd_path,
)


_CHATLOG_CACHE: Dict[str, Dict[str, Any]] = {}


def get_active_mydata_dirs(
    root: Path,
    max_active_roles: int = 3,
    active_window_hours: float = 24.0,
) -> Optional[List[Path]]:
    """Find the top `max_active_roles` most recently active my#data character directories."""
    mydata = root / "interface" / "my#data"
    if not mydata.exists() or not mydata.is_dir():
        return None

    dirs = [d for d in mydata.iterdir() if d.is_dir()]
    if not dirs:
        return None

    def _dir_latest_mtime(d: Path) -> float:
        candidates: List[Path] = [d / "info.jx3dat"]
        chat_dir = d / "userdata" / "chat_log"
        if chat_dir.exists():
            candidates.extend(chat_dir.glob("chatlog_*.v2.db"))
        return max((p.stat().st_mtime for p in candidates if p.exists()), default=0.0)

    dir_mtimes = [(d, _dir_latest_mtime(d)) for d in dirs]
    dir_mtimes = [item for item in dir_mtimes if item[1] > 0]
    if not dir_mtimes:
        return None

    dir_mtimes.sort(key=lambda item: item[1], reverse=True)

    now = time.time()
    cutoff = now - (active_window_hours * 3600.0)

    recent_dirs = [d for d, mtime in dir_mtimes if mtime >= cutoff]
    if recent_dirs:
        selected = recent_dirs[:max_active_roles]
    else:
        selected = [d for d, _ in dir_mtimes[:max_active_roles]]

    return selected


def find_chatlog_dbs(
    jx3_path: Path,
    force_full_scan: bool = False,
    max_active_roles: int = 3,
    active_window_hours: float = 24.0,
) -> List[Path]:
    root = resolve_zhcn_hd_path(jx3_path)
    root_str = str(root)
    now = time.time()
    
    cache = _CHATLOG_CACHE.get(root_str)
    if not cache:
        cache = {"last_full_scan": 0.0, "chat_log_dirs": {}, "dbs": set()}
        _CHATLOG_CACHE[root_str] = cache
        
    need_full_scan = force_full_scan or (now - cache["last_full_scan"] > 60.0)
    
    if need_full_scan:
        all_dbs = set()
        all_dirs = set()

        if max_active_roles > 0:
            active_dirs = get_active_mydata_dirs(
                root,
                max_active_roles=max_active_roles,
                active_window_hours=active_window_hours,
            )
        else:
            active_dirs = None

        if active_dirs:
            for active_dir in active_dirs:
                chat_log_dir = active_dir / "userdata" / "chat_log"
                if chat_log_dir.exists():
                    for p in chat_log_dir.glob("chatlog_*.v2.db"):
                        if p.is_file():
                            all_dbs.add(p)
                            all_dirs.add(p.parent)
        else:
            pattern = str(root / DEFAULT_CHATLOG_GLOB)
            for p_str in glob.glob(pattern, recursive=True):
                p = Path(p_str)
                if p.is_file():
                    all_dbs.add(p)
                    all_dirs.add(p.parent)
                
        cache["dbs"] = all_dbs
        for d in all_dirs:
            try:
                cache["chat_log_dirs"][d] = d.stat().st_mtime
            except OSError:
                pass
        cache["last_full_scan"] = now
    else:
        for d, old_mtime in list(cache["chat_log_dirs"].items()):
            try:
                current_mtime = d.stat().st_mtime
                if current_mtime != old_mtime:
                    cache["chat_log_dirs"][d] = current_mtime
                    new_dbs_in_dir = set()
                    for f in d.glob("chatlog_*.v2.db"):
                        if f.is_file():
                            new_dbs_in_dir.add(f)
                    
                    cache["dbs"] = {db for db in cache["dbs"] if db.parent != d}
                    cache["dbs"].update(new_dbs_in_dir)
            except OSError:
                del cache["chat_log_dirs"][d]
                cache["dbs"] = {db for db in cache["dbs"] if db.parent != d}
                
    return sorted(cache["dbs"])


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5.0)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=5000")
    except sqlite3.Error:
        pass
    return con


def table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return []
    return [r[1] for r in rows]


def query_chatlog_rows(
    db_path: Path,
    since_rowid: int = 0,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
    limit: int = 10000,
) -> Tuple[List[Dict[str, Any]], int, List[str], Optional[str]]:
    rows_out: List[Dict[str, Any]] = []
    max_rowid = since_rowid
    columns: List[str] = []
    last_error: Optional[str] = None
    for attempt in range(3):
        con: Optional[sqlite3.Connection] = None
        try:
            con = connect_readonly(db_path)
            columns = table_columns(con, "ChatLog")
            if not columns:
                return [], max_rowid, columns, "ChatLog table not found or has no columns"
            where = ["rowid > ?"]
            params: List[Any] = [since_rowid]
            if "time" in columns and start_ts is not None:
                where.append("time >= ?")
                params.append(int(start_ts))
            if "time" in columns and end_ts is not None:
                where.append("time <= ?")
                params.append(int(end_ts))
            sql = f"SELECT rowid,* FROM ChatLog WHERE {' AND '.join(where)} ORDER BY rowid ASC LIMIT ?"
            params.append(limit)
            for r in con.execute(sql, params):
                rowid = int(r["rowid"])
                max_rowid = max(max_rowid, rowid)
                raw = {k: r[k] for k in r.keys() if k != "rowid"}
                event = {
                    "time": raw.get("time"),
                    "rowid": rowid,
                    "type": raw.get("type"),
                    "talker": raw.get("talker"),
                    "text": raw.get("text"),
                    "msg": raw.get("msg"),
                    "db": str(db_path),
                    "table": "ChatLog",
                    "raw_row": raw,
                    "columns": columns,
                    "scan_ts": now_ts(),
                }
                rows_out.append(event)
            return rows_out, max_rowid, columns, None
        except sqlite3.Error as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                time.sleep(0.2 * (attempt + 1))
                rows_out = []
                max_rowid = since_rowid
                continue
            return rows_out, max_rowid, columns, last_error
        finally:
            if con is not None:
                con.close()
    return rows_out, max_rowid, columns, last_error
