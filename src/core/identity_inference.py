# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Identity inference from game data files.

Extracts login account, role name, server, and UID from JX3 local files
(info.jx3dat, userdata.db, chat log DB paths, exported HTML).
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.patterns import HTML_EXPORT_TITLE_RE
from src.core.text_utils import normalize_text
from src.core.json_io import read_json
from src.core.timestamps import ts_label


# ── info.jx3dat parser ─────────────────────────────────────────


def parse_info_jx3dat(path: Path) -> Dict[str, Any]:
    """Parse JX3 info.jx3dat file into a key-value dict."""
    if not path.exists():
        return {}
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("gbk", errors="replace")
    out: Dict[str, Any] = {}
    for k, v in re.findall(r"(\w+)\s*=\s*\"([^\"]*)\"", text):
        out[k] = v
    for k, v in re.findall(r"(\w+)\s*=\s*(\d+)", text):
        if k not in out:
            out[k] = int(v)
    return out


# ── Login account extraction ───────────────────────────────────


def extract_login_account_from_userdata_db(mydata_dir: Path) -> Optional[str]:
    """Extract login account name from userdata.db blob data."""
    db = mydata_dir / "userdata" / "userdata.db"
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(db)
        rows = con.execute(
            "SELECT key,value FROM data WHERE key LIKE '%RoleStat%' OR key LIKE '%RoleStatistics%' LIMIT 20"
        ).fetchall()
    except sqlite3.Error:
        return None
    for _key, blob in rows:
        if not isinstance(blob, (bytes, bytearray)):
            continue
        text = bytes(blob).decode("gbk", errors="ignore")
        for pat in [
            r"accounts[^A-Za-z0-9_.#@-]+([A-Za-z0-9_.#@-]{3,})",
            r"owners[^A-Za-z0-9_.#@-]+([A-Za-z0-9_.#@-]{3,})",
        ]:
            m = re.search(pat, text)
            if m:
                return m.group(1).split("#", 1)[0]
    return None


# ── My#Data directory helpers ──────────────────────────────────


def mydata_dir_latest_mtime(mydata_dir: Path) -> float:
    """Return the latest mtime among key files in a my#data directory."""
    candidates: List[Path] = []
    candidates.append(mydata_dir / "info.jx3dat")
    chat_dir = mydata_dir / "userdata" / "chat_log"
    if chat_dir.exists():
        candidates.extend(chat_dir.glob("chatlog_*.v2.db"))
    export_dir = mydata_dir / "export" / "ChatLog"
    if export_dir.exists():
        candidates.extend(export_dir.glob("*.html"))
    return max((p.stat().st_mtime for p in candidates if p.exists()), default=0.0)


def find_zhcn_hd_root(path: Path) -> Optional[Path]:
    """Walk up the tree to find a zhcn_hd directory."""
    p = path.resolve()
    if p.is_file():
        p = p.parent
    for parent in [p, *p.parents]:
        if parent.name == "zhcn_hd":
            return parent
    return None


# ── Identity from my#data directory ────────────────────────────


def identity_from_mydata_dir(
    mydata_dir: Path, html_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Infer identity from a JX3 my#data directory."""
    info = parse_info_jx3dat(mydata_dir / "info.jx3dat")
    uid_match = re.match(r"(?P<uid>\d+)@zhcn_hd$", mydata_dir.name)
    uid = uid_match.group("uid") if uid_match else None

    html_info: Dict[str, Any] = {}
    if html_path and html_path.exists() and html_path.suffix.lower() in {".html", ".htm"}:
        head = html_path.read_bytes()[:200000].decode("gbk", errors="replace")
        m = HTML_EXPORT_TITLE_RE.search(head)
        if m:
            html_info = m.groupdict()
        if not html_info:
            m2 = re.match(
                r"(?P<role>[^@]+)@(?:(?P<region>[^_@]+)_)?(?P<server>[^@]+)@(?P<exported_at>\d{14})",
                html_path.stem,
            )
            if m2:
                html_info = m2.groupdict()

    account = extract_login_account_from_userdata_db(mydata_dir)
    role = (
        info.get("name")
        or info.get("role_name")
        or info.get("szName")
        or info.get("RoleName")
        or info.get("szRoleName")
        or html_info.get("role")
    )
    server = (
        info.get("server")
        or info.get("server_name")
        or info.get("szServer")
        or info.get("ServerName")
        or html_info.get("server")
    )
    region = (
        info.get("region")
        or info.get("region_name")
        or info.get("szRegion")
        or html_info.get("region")
    )

    return {
        "login_account": account,
        "uid": info.get("uid") or uid,
        "role_name": role,
        "server": server,
        "region": region,
        "server_origin": info.get("server_origin"),
        "region_origin": info.get("region_origin"),
        "role_id": info.get("id"),
        "source_mydata_dir": str(mydata_dir),
        "html_exported_at": html_info.get("exported_at"),
        "latest_mtime": mydata_dir_latest_mtime(mydata_dir),
        "identity_source": "mydata_info",
        "display": " / ".join(x for x in [account, role, server] if x),
    }


def current_identity_from_jx3_path(jx3_path: Path) -> Optional[Dict[str, Any]]:
    """Find the most recently active my#data dir and infer identity from it."""
    root = find_zhcn_hd_root(jx3_path) or Path(jx3_path)
    mydata = root / "interface" / "my#data"
    if not mydata.exists():
        return None
    dirs = [d for d in mydata.iterdir() if d.is_dir() and re.match(r"\d+@zhcn_hd$", d.name)]
    if not dirs:
        return None
    latest = max(dirs, key=mydata_dir_latest_mtime)
    ident = identity_from_mydata_dir(latest)
    ident["identity_source"] = "latest_active_mydata_dir"
    return ident


# ── Identity from path ─────────────────────────────────────────


def identity_from_path(path: Path) -> Dict[str, Any]:
    """Infer login account/role/server from JX3 my#data path or exported HTML path."""
    p = path.resolve()
    parts = list(p.parts)
    mydata_dir: Optional[Path] = None
    uid = None
    for i, part in enumerate(parts):
        m = re.match(r"(?P<uid>\d+)@zhcn_hd$", part)
        if m:
            uid = m.group("uid")
            mydata_dir = Path(*parts[: i + 1])
            break
    if mydata_dir:
        return identity_from_mydata_dir(mydata_dir, p if p.suffix.lower() in {".html", ".htm"} else None)
    current = current_identity_from_jx3_path(p)
    if current:
        return current
    return {"login_account": None, "uid": uid, "role_name": None, "server": None, "display": ""}


def apply_identity_override(
    identity: Optional[Dict[str, Any]], role_name_override: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Override role_name in identity dict."""
    if not identity:
        identity = {}
    else:
        identity = dict(identity)
    role_name_override = normalize_text(role_name_override)
    if role_name_override:
        identity["role_name"] = role_name_override
        identity["role_name_source"] = "manual_override"
    identity["display"] = " / ".join(
        x for x in [identity.get("login_account"), identity.get("role_name"), identity.get("server")] if x
    )
    return identity


# ── Session-local identity inference ───────────────────────────


def infer_identity_from_session_files(session_dir: Path) -> Optional[Dict[str, Any]]:
    """Infer the current role for a settlement session from its own events.

    Uses an activity scoring system to identify the raiding character database
    that was most active during the session, rather than the receiving character's
    database which only received a large wage.
    """
    from src.core.json_io import load_jsonl
    from src.core.text_utils import normalize_text
    
    raw_events = list(load_jsonl(session_dir / "raw_events.jsonl") or [])
    business_events = list(load_jsonl(session_dir / "business_events.jsonl") or [])
    
    candidate_dbs = set()
    for e in raw_events:
        db = e.get("db")
        if db:
            candidate_dbs.add(db)
            
    if not candidate_dbs:
        return None
        
    db_scores = {}
    for db in candidate_dbs:
        score = 0.0
        for e in business_events:
            if e.get("db") != db:
                continue
            kind = e.get("kind")
            if kind == "final_purchase":
                score += 10.0
            elif kind == "bid":
                score += 5.0
            elif kind == "auction_start":
                score += 10.0
            elif kind == "team_append_income":
                score += 10.0
            elif kind == "money_gain":
                amt_copper = e.get("amount_copper") or 0
                if amt_copper == 100000: # 10 gold (Boss reward)
                    score += 20.0
                else:
                    score += 1.0
            elif kind == "item_gain":
                score += 2.0
            elif kind == "team_message":
                score += 1.0
                
        # Tie-breaker: raw event count
        raw_count = sum(1 for e in raw_events if e.get("db") == db)
        score += raw_count * 0.01
        db_scores[db] = score
        
    # Sort candidate databases by score descending
    sorted_dbs = sorted(db_scores.keys(), key=lambda db: db_scores[db], reverse=True)
    for db in sorted_dbs:
        ident = identity_from_path(Path(db))
        if ident and ident.get("role_name"):
            ident["identity_source"] = "session_activity_scoring"
            ident["identity_score"] = db_scores[db]
            ident["display"] = " / ".join(x for x in [ident.get("login_account"), ident.get("role_name"), ident.get("server")] if x)
            return ident

    return None
