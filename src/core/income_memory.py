# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Income memory helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.core.json_io import read_json, write_json


def load_income_memory(path: Path) -> Dict[str, Any]:
    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.migrate_json_to_db_if_needed(path.with_suffix(".json"))
        if not path.exists():
            return {"schema": 1, "next_seq": 1, "records": []}
        records = sqlite_db.search_records(path, "")
        records.sort(key=lambda r: r.get("seq", 0))
        next_seq = (records[-1]["seq"] + 1) if records else 1
        return {"schema": 1, "next_seq": next_seq, "records": records}
        
    data = read_json(path, None)
    if not isinstance(data, dict):
        data = {"schema": 1, "next_seq": 1, "records": []}
    data.setdefault("schema", 1)
    data.setdefault("next_seq", 1)
    data.setdefault("records", [])
    if not isinstance(data["records"], list):
        data["records"] = []
    return data


def save_income_memory(path: Path, data: Dict[str, Any] | List[Dict[str, Any]]) -> None:
    if isinstance(data, list):
        records = data
        data_dict = {"schema": 1, "next_seq": len(records) + 1, "records": records}
    else:
        data_dict = data
        records = data_dict.get("records") or []

    records = sorted(records, key=lambda r: int(r.get("seq") or 0))
    max_seq = max([int(r.get("seq") or 0) for r in records] + [0])
    data_dict["records"] = records
    data_dict["next_seq"] = max(int(data_dict.get("next_seq") or 1), max_seq + 1)

    if path.suffix == ".db":
        import src.core.sqlite_db as sqlite_db
        sqlite_db.replace_all_records(path, records)
        return

    write_json(path, data_dict)
