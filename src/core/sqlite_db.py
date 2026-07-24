# -*- coding: utf-8 -*-
"""JX3 Click Monitor - SQLite DB backend for income memory."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_db_path(json_path: Path) -> Path:
    """Return the equivalent .db path for a given .json path."""
    return json_path.with_suffix(".db")


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=15000")
    except Exception:
        pass
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income_records (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            session_dir TEXT UNIQUE,
            recorded_at TEXT,
            recorded_ts INTEGER,
            session_start TEXT,
            session_end TEXT,
            account TEXT,
            role TEXT,
            server TEXT,
            instance TEXT,
            instance_confidence TEXT,
            income_gold REAL,
            expense_gold REAL,
            net_gold REAL,
            black_role TEXT,
            total_auction_gold REAL,
            member_count INTEGER,
            average_wage_gold REAL,
            note TEXT,
            manual BOOLEAN,
            created_at TEXT,
            updated_at TEXT,
            expense_items_json TEXT
        )
    ''')
    conn.commit()
    return conn


def migrate_json_to_db_if_needed(json_path: Path) -> None:
    db_path = get_db_path(json_path)
    if not json_path.exists() or db_path.exists():
        return
    
    from src.core.income_memory import load_income_memory
    data = load_income_memory(json_path)
    records = data.get("records", [])
    
    conn = init_db(db_path)
    try:
        cursor = conn.cursor()
        for r in records:
            cursor.execute('''
                INSERT OR IGNORE INTO income_records (
                    seq, session_dir, recorded_at, recorded_ts, session_start, session_end,
                    account, role, server, instance, instance_confidence, income_gold,
                    expense_gold, net_gold, black_role, total_auction_gold, member_count,
                    average_wage_gold, note, manual, created_at, updated_at, expense_items_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                r.get("seq"), r.get("session_dir"), r.get("recorded_at"), r.get("recorded_ts"),
                r.get("session_start"), r.get("session_end"), r.get("account"), r.get("role"),
                r.get("server"), r.get("instance"), r.get("instance_confidence"),
                r.get("income_gold"), r.get("expense_gold"), r.get("net_gold"),
                r.get("black_role"), r.get("total_auction_gold"), r.get("member_count"),
                r.get("average_wage_gold"), r.get("note"), r.get("manual", False),
                r.get("created_at"), r.get("updated_at"),
                json.dumps(r.get("expense_items", []), ensure_ascii=False)
            ))
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["manual"] = bool(d["manual"])
    if d.get("expense_items_json"):
        try:
            d["expense_items"] = json.loads(d["expense_items_json"])
        except Exception:
            d["expense_items"] = []
    else:
        d["expense_items"] = []
    d.pop("expense_items_json", None)
    return d


def search_records(db_path: Path, query: str = "") -> List[Dict[str, Any]]:
    conn = init_db(db_path)
    try:
        cursor = conn.cursor()
        if query:
            q = f"%{query}%"
            cursor.execute('''
                SELECT * FROM income_records
                WHERE role LIKE ? OR server LIKE ? OR instance LIKE ? OR note LIKE ?
                ORDER BY seq DESC
            ''', (q, q, q, q))
        else:
            cursor.execute('SELECT * FROM income_records ORDER BY seq DESC')
        
        results = [_row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    return results


def get_record_by_session(db_path: Path, session_dir: str) -> Optional[Dict[str, Any]]:
    conn = init_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM income_records WHERE session_dir = ?', (session_dir,))
        row = cursor.fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row else None


def get_record_by_seq(db_path: Path, seq: int) -> Optional[Dict[str, Any]]:
    conn = init_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM income_records WHERE seq = ?', (seq,))
        row = cursor.fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row else None


def delete_record(db_path: Path, seq: int) -> bool:
    conn = init_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM income_records WHERE seq = ?', (seq,))
        changes = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    return changes > 0


def upsert_record(db_path: Path, record: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    should_close = False
    if conn is None:
        conn = init_db(db_path)
        should_close = True

    try:
        cursor = conn.cursor()
        seq = record.get("seq")
        session_dir = record.get("session_dir")
        
        existing = None
        if seq:
            cursor.execute('SELECT * FROM income_records WHERE seq = ?', (seq,))
            existing = cursor.fetchone()
        elif session_dir:
            cursor.execute('SELECT * FROM income_records WHERE session_dir = ?', (session_dir,))
            existing = cursor.fetchone()
            
        if existing:
            seq = existing["seq"]
            update_fields = []
            update_values = []
            for k, v in record.items():
                if k in {"seq", "expense_items"}:
                    continue
                update_fields.append(f"{k} = ?")
                update_values.append(v)
                
            if "expense_items" in record:
                update_fields.append("expense_items_json = ?")
                update_values.append(json.dumps(record["expense_items"], ensure_ascii=False))
                
            update_values.append(seq)
            
            cursor.execute(f'''
                UPDATE income_records SET {', '.join(update_fields)} WHERE seq = ?
            ''', update_values)
        else:
            fields = []
            values = []
            for k, v in record.items():
                if k == "expense_items":
                    fields.append("expense_items_json")
                    values.append(json.dumps(v, ensure_ascii=False))
                else:
                    fields.append(k)
                    values.append(v)
                    
            placeholders = ", ".join(["?"] * len(fields))
            cursor.execute(f'''
                INSERT INTO income_records ({', '.join(fields)}) VALUES ({placeholders})
            ''', values)
            seq = cursor.lastrowid
            
        if should_close:
            conn.commit()
        
        cursor.execute('SELECT * FROM income_records WHERE seq = ?', (seq,))
        row = cursor.fetchone()
        return _row_to_dict(row)
    finally:
        if should_close:
            conn.close()


def replace_all_records(db_path: Path, records: List[Dict[str, Any]]) -> None:
    conn = init_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM income_records")
        for rec in records:
            upsert_record(db_path, rec, conn=conn)
        conn.commit()
    finally:
        conn.close()
