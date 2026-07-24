# -*- coding: utf-8 -*-
"""JX3 Click Monitor - JSON / JSONL I/O utilities.

Atomic writes (write .tmp then rename) prevent corruption on crash.
JSONL support is streaming-friendly (append or read line-by-line).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON: write to .tmp then rename. Fallback on GVFS/FUSE error."""
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            tmp.replace(path)
        except OSError:
            if path.exists():
                path.unlink()
            tmp.rename(path)
    except OSError:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    """Append JSONL rows; return count written."""
    ensure_dir(path.parent)
    n = 0
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            n += 1
    return n


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    """Overwrite with JSONL rows; return count written."""
    ensure_dir(path.parent)
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            n += 1
    return n


def load_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield JSON objects from a JSONL file, skipping malformed lines."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def count_jsonl(path: Path) -> int:
    """Count non-empty lines in a JSONL file."""
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                n += 1
    return n
