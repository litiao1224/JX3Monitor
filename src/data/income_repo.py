# -*- coding: utf-8 -*-
"""小鹦鹉记账 - SQLite 收支记录仓库

替换原有的 income_memory.json 存储方案。
提供：
  - 高效的按日期/角色/区服/副本查询（带 SQLite 索引）
  - 幂等的 JSON 迁移工具（migrate_from_json）
  - 导出 JSON 备份（export_json）
  - 全字段 CRUD

向后兼容：
  - 保持与原 income_memory.json 相同的 record 字段结构
  - migrate_from_json 可重复执行（幂等，按 seq 防重）
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger("jx3_monitor.income_repo")

# ── Schema ──

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS income_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    seq          INTEGER UNIQUE,              -- 原 income_memory.json 的 seq，用于迁移去重
    recorded_at  TEXT NOT NULL DEFAULT '',    -- 入账时间（ISO 字符串）
    server       TEXT NOT NULL DEFAULT '',
    role         TEXT NOT NULL DEFAULT '',
    black_role   TEXT NOT NULL DEFAULT '',
    instance     TEXT NOT NULL DEFAULT '',
    income_gold  REAL NOT NULL DEFAULT 0,
    expense_gold REAL NOT NULL DEFAULT 0,
    net_gold     REAL NOT NULL DEFAULT 0,
    note         TEXT NOT NULL DEFAULT '',
    session_time TEXT NOT NULL DEFAULT '',    -- session 目录名
    session_dir  TEXT NOT NULL DEFAULT '',    -- session 完整路径
    raw_json     TEXT NOT NULL DEFAULT '{}'   -- 原始 dict 的 JSON 快照
);

CREATE INDEX IF NOT EXISTS idx_recorded_at ON income_records(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_role        ON income_records(role);
CREATE INDEX IF NOT EXISTS idx_server      ON income_records(server);
CREATE INDEX IF NOT EXISTS idx_instance    ON income_records(instance);

CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
INSERT OR IGNORE INTO _meta(key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO _meta(key, value) VALUES ('migrated_from_json', '0');
"""

_DB_FILENAME = "income_records.db"


class IncomeRepo:
    """SQLite 收支记录仓库。

    线程安全：每次操作创建新连接（SQLite WAL 模式支持多读一写）。
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    # ── 初始化 ──

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA_SQL)
            # 启用 WAL 模式，提升并发读性能
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        logger.info("IncomeRepo 初始化完成：%s", self._db_path)

    # ── 连接上下文管理器 ──

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── CRUD ──

    def insert(self, record: dict) -> int:
        """插入一条收支记录，返回新行的 id。"""
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO income_records
                (seq, recorded_at, server, role, black_role, instance,
                 income_gold, expense_gold, net_gold, note, session_time, session_dir, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("seq"),
                    record.get("recorded_at", ""),
                    record.get("server", ""),
                    record.get("role", ""),
                    record.get("black_role", ""),
                    record.get("instance", ""),
                    float(record.get("income", record.get("income_gold", 0)) or 0),
                    float(record.get("expense", record.get("expense_gold", 0)) or 0),
                    float(record.get("net", record.get("net_gold", 0)) or 0),
                    record.get("note", ""),
                    record.get("session_time", ""),
                    record.get("session_dir", ""),
                    json.dumps(record, ensure_ascii=False),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def update(self, record_id: int, record: dict) -> None:
        """更新指定 id 的收支记录。"""
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE income_records SET
                    recorded_at  = ?,
                    server       = ?,
                    role         = ?,
                    black_role   = ?,
                    instance     = ?,
                    income_gold  = ?,
                    expense_gold = ?,
                    net_gold     = ?,
                    note         = ?,
                    session_time = ?,
                    session_dir  = ?,
                    raw_json     = ?
                WHERE id = ?
                """,
                (
                    record.get("recorded_at", ""),
                    record.get("server", ""),
                    record.get("role", ""),
                    record.get("black_role", ""),
                    record.get("instance", ""),
                    float(record.get("income", record.get("income_gold", 0)) or 0),
                    float(record.get("expense", record.get("expense_gold", 0)) or 0),
                    float(record.get("net", record.get("net_gold", 0)) or 0),
                    record.get("note", ""),
                    record.get("session_time", ""),
                    record.get("session_dir", ""),
                    json.dumps(record, ensure_ascii=False),
                    record_id,
                ),
            )

    def delete(self, record_id: int) -> None:
        """删除指定 id 的收支记录。"""
        with self._conn() as conn:
            conn.execute("DELETE FROM income_records WHERE id = ?", (record_id,))

    def get_by_id(self, record_id: int) -> Optional[dict]:
        """按 id 查询单条记录。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM income_records WHERE id = ?", (record_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    # ── 查询 ──

    def query(
        self,
        *,
        date_from: str = "",
        date_to: str = "",
        role: str = "",
        server: str = "",
        instance: str = "",
        note_keyword: str = "",
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict]:
        """条件查询，支持日期范围、角色、区服、副本、备注关键词过滤。"""
        where_parts: list[str] = []
        params: list = []

        if date_from:
            where_parts.append("recorded_at >= ?")
            params.append(date_from)
        if date_to:
            where_parts.append("recorded_at <= ?")
            params.append(date_to + "Z")  # 包含当天最后一秒
        if role:
            where_parts.append("role = ?")
            params.append(role)
        if server:
            where_parts.append("server = ?")
            params.append(server)
        if instance:
            where_parts.append("instance LIKE ?")
            params.append(f"%{instance}%")
        if note_keyword:
            where_parts.append("note LIKE ?")
            params.append(f"%{note_keyword}%")

        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM income_records {where} ORDER BY recorded_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM income_records").fetchone()[0]

    def all_roles(self) -> list[str]:
        """返回所有不重复的角色名列表（用于筛选下拉框）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT role FROM income_records WHERE role != '' ORDER BY role"
            ).fetchall()
        return [r[0] for r in rows]

    def all_servers(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT server FROM income_records WHERE server != '' ORDER BY server"
            ).fetchall()
        return [r[0] for r in rows]

    # ── 迁移 ──

    def migrate_from_json(self, json_path: Path) -> int:
        """从 income_memory.json 迁移到 SQLite（幂等，可重复执行）。

        Returns:
            迁移的新记录数（已存在的 seq 会跳过）。
        """
        if not json_path.exists():
            logger.info("migrate_from_json: %s 不存在，跳过", json_path)
            return 0

        try:
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            logger.error("migrate_from_json: 读取 JSON 失败: %s", e)
            return 0

        records = data.get("records", []) if isinstance(data, dict) else []
        if not records:
            logger.info("migrate_from_json: 无记录，跳过")
            return 0

        inserted = 0
        skipped = 0
        for rec in records:
            try:
                self.insert(rec)
                inserted += 1
            except sqlite3.IntegrityError:
                # seq UNIQUE 冲突 → 已存在，跳过
                skipped += 1
            except Exception as e:
                logger.warning("migrate_from_json: 跳过一条记录: %s | %s", e, rec)

        # 标记已迁移
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO _meta(key, value) VALUES ('migrated_from_json', '1')"
            )

        logger.info(
            "migrate_from_json 完成：新增 %d 条，跳过（已存在）%d 条",
            inserted, skipped,
        )
        return inserted

    def is_migrated(self) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM _meta WHERE key = 'migrated_from_json'"
            ).fetchone()
        return row is not None and row[0] == "1"

    # ── 导出 ──

    def export_json(self, output_path: Path) -> int:
        """导出所有记录为 income_memory.json 兼容格式（备份用）。"""
        records = self.query(limit=99999)
        # 重建 seq
        for i, rec in enumerate(records, start=1):
            rec.setdefault("seq", i)

        payload = {
            "schema": 1,
            "next_seq": len(records) + 1,
            "records": records,
        }
        tmp = output_path.with_suffix(output_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output_path)
        logger.info("export_json: 导出 %d 条记录到 %s", len(records), output_path)
        return len(records)

    # ── 内部辅助 ──

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """将 SQLite Row 转为与原 income_memory record 兼容的 dict。"""
        d = dict(row)
        # 解析 raw_json 补充原始字段
        try:
            raw = json.loads(d.get("raw_json", "{}") or "{}")
        except Exception:
            raw = {}
        raw.update({
            "id":          d["id"],
            "seq":         d.get("seq"),
            "recorded_at": d["recorded_at"],
            "server":      d["server"],
            "role":        d["role"],
            "black_role":  d["black_role"],
            "instance":    d["instance"],
            "income":      d["income_gold"],
            "expense":     d["expense_gold"],
            "net":         d["net_gold"],
            "note":        d["note"],
            "session_time": d["session_time"],
            "session_dir": d["session_dir"],
        })
        return raw


# ── 工厂函数 ──

def open_income_repo(base_dir: Path) -> IncomeRepo:
    """在 base_dir 下打开（或创建）IncomeRepo。"""
    return IncomeRepo(base_dir / _DB_FILENAME)


def ensure_migrated(repo: IncomeRepo, json_path: Path) -> None:
    """确保已从 JSON 迁移到 SQLite（首次运行时自动执行）。"""
    if not repo.is_migrated() and json_path.exists():
        logger.info("首次运行，自动从 %s 迁移到 SQLite…", json_path)
        n = repo.migrate_from_json(json_path)
        logger.info("迁移完成，共迁移 %d 条收支记录", n)
