# -*- coding: utf-8 -*-
"""小鹦鹉记账 - 角色成长数据后台服务

精简版：仅使用 dungeon_records（副本进度）+ role_stat_lookup（茗伊角色数据）
两个数据源，砍掉 equip_records 和 account_lookup。

用途：
    self._growth_service = GrowthService()
    self._growth_service.load_async(
        jx3_path=self.jx3_var.get(),
        callback=lambda recs: self.after(0, lambda: self._on_growth_data(recs)),
        on_error=lambda e: self.after(0, lambda: self.status_var.set(f"角色信息加载失败: {e}")),
    )
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("jx3_monitor.growth_service")

_CACHE_TTL = 30.0

OnDataCallback = Callable[[list[dict]], None]
OnErrorCallback = Callable[[Exception], None]


class GrowthService:
    """角色成长数据的后台加载、合并、去重服务。

    数据源：
    - dungeon_records：区服、角色、副本进度
    - role_stat_lookup：账号、区服、角色、装分（茗伊角色统计）

    特性：
    - mtime 感知缓存：文件未变化时直接返回缓存
    - 单次并发：防止重复加载
    - 线程安全回调：结果通过 callback 交回调用方
    """

    def __init__(self) -> None:
        self._cache: Optional[list[dict]] = None
        self._cache_jx3_path: str = ""
        self._cache_ts: float = 0.0
        self._lock = threading.Lock()
        self._loading = False

    # ── 公开接口 ──

    # ── 静态工具方法（供 GUI 层直接调用，消除重复代码） ──

    @staticmethod
    def normalize_server(value: object) -> str:
        """规范化区服名称（去前缀），用于对比去重。"""
        text = str(value or "").strip().lower()
        for prefix in ("电信区", "双线区", "无界区", "缘起区", "网通区"):
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix):]
        return text

    @staticmethod
    def record_dedupe_key(rec: dict) -> tuple:
        """返回角色记录的去重 key：(账号, 区服, 角色名)。"""
        return (
            str(rec.get("account", "")).lower(),
            GrowthService.normalize_server(rec.get("server", "")),
            str(rec.get("name", "")).lower(),
        )

    @staticmethod
    def merge_record_values(base: dict, incoming: dict) -> dict:
        """将 incoming 中的字段合并进 base，副本进度按 map_id 合并。"""
        merged = dict(base)
        for key, value in incoming.items():
            if key == "dungeons":
                existing = {
                    str(d.get("map_id")): d
                    for d in merged.get("dungeons") or []
                    if isinstance(d, dict)
                }
                for dungeon in value or []:
                    if isinstance(dungeon, dict):
                        existing[str(dungeon.get("map_id"))] = dungeon
                merged["dungeons"] = list(existing.values())
            elif key == "items":
                if value and len(value or []) > len(merged.get("items") or []):
                    merged[key] = value
            elif key == "score" and value not in (None, "", "-"):
                merged[key] = value
            elif value not in (None, "", [], {}) and not merged.get(key):
                merged[key] = value
        return merged

    @staticmethod
    def dedupe_records(records: list) -> list:
        """按账号+区服+角色名去重，重复记录合并字段。"""
        seen: dict = {}
        for rec in records:
            key = GrowthService.record_dedupe_key(rec)
            if key in seen:
                seen[key] = GrowthService.merge_record_values(seen[key], rec)
            else:
                seen[key] = dict(rec)
        return list(seen.values())

    @staticmethod
    def merge_records(records: list, extra_records: list | None = None) -> list:
        """合并两个角色记录列表，去重后返回。"""
        merged: list = list(records or [])
        merged.extend(extra_records or [])
        return GrowthService.dedupe_records(merged)


    def load_async(
        self,
        jx3_path: str,
        callback: OnDataCallback,
        on_error: Optional[OnErrorCallback] = None,
        force: bool = False,
    ) -> None:
        with self._lock:
            if self._loading:
                logger.debug("GrowthService: 已有加载任务进行中，跳过")
                return
            if not force and self._is_cache_valid(jx3_path):
                logger.debug("GrowthService: 使用缓存（%d 条）", len(self._cache or []))
                cached = list(self._cache or [])
                threading.Thread(
                    target=lambda: callback(cached),
                    daemon=True,
                    name="GrowthService-cache-cb",
                ).start()
                return
            self._loading = True

        t = threading.Thread(
            target=self._worker,
            args=(jx3_path, callback, on_error),
            daemon=True,
            name="GrowthService-load",
        )
        t.start()

    def get_cached(self) -> Optional[list[dict]]:
        with self._lock:
            return list(self._cache) if self._cache is not None else None

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_ts = 0.0

    # ── 内部实现 ──

    def _is_cache_valid(self, jx3_path: str) -> bool:
        if self._cache is None:
            return False
        if self._cache_jx3_path != jx3_path:
            return False
        if time.monotonic() - self._cache_ts > _CACHE_TTL:
            return False
        return True

    def _worker(
        self,
        jx3_path: str,
        callback: OnDataCallback,
        on_error: Optional[OnErrorCallback],
    ) -> None:
        try:
            records = self._load_and_process(jx3_path)
            with self._lock:
                self._cache = records
                self._cache_jx3_path = jx3_path
                self._cache_ts = time.monotonic()
                self._loading = False
            logger.info("GrowthService: 加载完成，共 %d 条记录", len(records))
            callback(records)
        except Exception as e:
            logger.exception("GrowthService: 加载失败")
            with self._lock:
                self._loading = False
            if on_error:
                on_error(e)

    def _load_and_process(self, jx3_path: str) -> list[dict]:
        if not jx3_path:
            return []

        try:
            dungeon_records, _ = load_dungeon_growth_data(jx3_path)
            role_stat_lookup = load_role_stat_userdata_lookup(jx3_path)
        except Exception as e:
            logger.warning("GrowthService: 数据加载失败: %s", e)
            return []

        return self._merge(dungeon_records, role_stat_lookup)

    def _normalize_server(self, value: object) -> str:
        text = str(value or "").strip().lower()
        for prefix in ("电信区", "双线区", "无界区", "缘起区", "网通区"):
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix):]
        return text

    def _merge(
        self,
        dungeon_records: list[dict],
        role_stat_lookup: dict,
    ) -> list[dict]:
        """合并 dungeon_records 和 role_stat_lookup，按账号+区服+角色去重。"""
        role_stat_lookup = role_stat_lookup or {}
        merged: list[dict] = []
        seen_keys: set[tuple[str, str]] = set()

        # 1. 从 dungeon_records 提取基础信息 + 副本进度
        for dungeon in dungeon_records or []:
            key = (str(dungeon.get("server") or ""), str(dungeon.get("name") or ""))
            if key in seen_keys:
                continue
            role_stat = role_stat_lookup.get(key, {})
            merged.append({
                "account": dungeon.get("account") or role_stat.get("account") or "",
                "server": dungeon.get("server") or "",
                "name": dungeon.get("name") or "",
                "score": role_stat.get("score") or "",
                "dungeons": dungeon.get("dungeons") or [],
            })
            seen_keys.add(key)

        # 2. 补充 role_stat_lookup 中独有的角色（有账号装分但无副本记录）
        for key, role_stat in role_stat_lookup.items():
            if key in seen_keys:
                continue
            server, name = key
            merged.append({
                "account": role_stat.get("account") or "",
                "server": server,
                "name": name,
                "score": role_stat.get("score") or "",
                "dungeons": [],
            })

        # 3. 按 (账号, 区服, 角色名) 去重
        return self._dedupe(merged)

    def _dedupe(self, records: list[dict]) -> list[dict]:
        """按账号+区服+角色名去重，合并副本进度。"""
        seen: dict[tuple[str, str, str], dict] = {}
        for rec in records:
            key = (
                str(rec.get("account", "")).lower(),
                self._normalize_server(rec.get("server", "")),
                str(rec.get("name", "")).lower(),
            )
            if key in seen:
                base = seen[key]
                # 合并副本进度
                existing_d = {str(d.get("map_id")): d for d in base.get("dungeons") or [] if isinstance(d, dict)}
                for d in rec.get("dungeons") or []:
                    if isinstance(d, dict):
                        existing_d[str(d.get("map_id"))] = d
                base["dungeons"] = list(existing_d.values())
                # 装分取非空值
                if rec.get("score") and not base.get("score"):
                    base["score"] = rec["score"]
            else:
                seen[key] = dict(rec)
        return list(seen.values())


# ── SQLite & MYData Data Loading Helpers ──────────────────────────

def sqlite_readonly_uri(path: Path) -> str:
    import urllib.parse
    s = path.resolve().as_posix()
    if not s.startswith("/"):
        s = "/" + s
    return "file:" + urllib.parse.quote(s, safe="/:") + "?mode=ro"


class MYDataParser:
    """Parser for 茗伊 LUAData BLOB values stored in userdata.db."""

    def __init__(self, data: bytes):
        self.data = data or b""
        self.i = 0

    def read(self, n: int) -> bytes:
        if self.i + n > len(self.data):
            raise EOFError("unexpected end of MYData blob")
        b = self.data[self.i:self.i + n]
        self.i += n
        return b

    def value(self):
        import struct
        tag = self.read(1)
        if tag == b"n":
            return struct.unpack("<d", self.read(8))[0]
        if tag == b"b":
            return bool(struct.unpack("<I", self.read(4))[0])
        if tag == b"s":
            ln = struct.unpack("<H", self.read(2))[0]
            return self.read(ln).decode("gbk", "replace")
        if tag == b"t":
            cnt = struct.unpack("<H", self.read(2))[0]
            arr: list[tuple[int, object]] = []
            mp: dict[str, object] = {}
            numeric = True
            for _ in range(cnt):
                k = self.value()
                v = self.value()
                if isinstance(k, (int, float)) and float(k).is_integer():
                    arr.append((int(k), v))
                else:
                    numeric = False
                    mp[str(k)] = v
            if numeric and arr:
                arr.sort(key=lambda x: x[0])
                keys = [k for k, _v in arr]
                if keys == list(range(1, len(arr) + 1)) or keys == list(range(0, len(arr))):
                    return [v for _k, v in arr]
            for k, v in arr:
                mp[str(k)] = v
            return mp
        raise ValueError(f"unknown MYData tag {tag!r} at {self.i - 1}")


def fmt_num(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        f = float(value)
    except Exception:
        return str(value)
    return str(int(f)) if f.is_integer() else str(f)


def find_my_data_dir(jx3_path: str) -> Path | None:
    from src.config import DEFAULT_JX3_PATH
    from src.core.paths import find_plugin_data_dir
    base = Path(jx3_path or DEFAULT_JX3_PATH)
    if base.name.lower() == "my#data" and base.exists():
        return base
    if base.name.lower() == "role_statistics" and len(base.parents) >= 3 and base.parents[2].name.lower() == "my#data":
        return base.parents[2]
    return find_plugin_data_dir(base, "my#data")


def find_dungeon_stat_db(jx3_path: str) -> Path | None:
    from src.config import DEFAULT_JX3_PATH
    base = Path(jx3_path or DEFAULT_JX3_PATH)
    if base.is_file() and base.name.lower() == "dungeon_stat.v3.db":
        return base
    direct = base / "dungeon_stat.v3.db"
    if direct.exists():
        return direct
    my_data = find_my_data_dir(jx3_path)
    candidates = []
    if my_data:
        candidates.append(my_data / "!all-users@zhcn_hd" / "userdata" / "role_statistics" / "dungeon_stat.v3.db")
    for p in candidates:
        if p.exists():
            return p
    if my_data and my_data.exists():
        hits = list(my_data.glob("!all-users*/userdata/role_statistics/dungeon_stat.v3.db"))
        if hits:
            return hits[0]
    return None


def parse_lua_bool_map(text: str) -> dict[int, list[bool]]:
    out: dict[int, list[bool]] = {}
    for mid, body in re.findall(r"\[(\d+)\]\s*=\s*\{([^}]*)\}", text or ""):
        vals = []
        for token in re.findall(r"true|false", body, flags=re.I):
            vals.append(token.lower() == "true")
        out[int(mid)] = vals
    return out


def parse_lua_list_map(text: str) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for mid, body in re.findall(r"\[(\d+)\]\s*=\s*\{([^}]*)\}", text or ""):
        vals = [v.strip().strip('"\'') for v in body.split(",") if v.strip()]
        out[int(mid)] = vals
    return out


def latest_weekly_dungeon_reset_ts(now: datetime | None = None) -> int:
    from datetime import datetime, timedelta
    now = now or datetime.now()
    reset = now.replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    if now < reset:
        reset -= timedelta(days=7)
    return int(reset.timestamp())


def load_account_lookup(jx3_path: str) -> dict[tuple[str, str], str]:
    import sqlite3
    my_data = find_my_data_dir(jx3_path)
    if not my_data:
        return {}
    lookup: dict[tuple[str, str], str] = {}
    for db_path in my_data.glob("*@zhcn_hd/userdata/userdata.db"):
        try:
            con = sqlite3.connect(sqlite_readonly_uri(db_path), uri=True)
            row = con.execute("SELECT value FROM data WHERE key=?", ("MY_RoleStatistics_RoleStat.tAlertTodayVal",)).fetchone()
            con.close()
            if not row:
                continue
            parsed = MYDataParser(row[0]).value()
            data = parsed.get("d") if isinstance(parsed, dict) and isinstance(parsed.get("d"), dict) else parsed
            if not isinstance(data, dict):
                continue
            server = str(data.get("server") or data.get("servers") or "").strip()
            name = str(data.get("name") or data.get("names") or "").strip()
            account = str(data.get("account") or data.get("accounts") or "").strip()
            if server and name and account:
                lookup[(server, name)] = account
        except Exception as e:
            logger.warning("Failed to parse userdata.db at %s: %s", db_path, e)
            continue
    return lookup


def load_role_stat_userdata_lookup(jx3_path: str) -> dict[tuple[str, str], dict]:
    import sqlite3
    from src.core.money import fmt_money
    my_data = find_my_data_dir(jx3_path)
    if not my_data:
        return {}
    lookup: dict[tuple[str, str], dict] = {}
    for db_path in my_data.glob("*@zhcn_hd/userdata/userdata.db"):
        try:
            con = sqlite3.connect(sqlite_readonly_uri(db_path), uri=True)
            row = con.execute("SELECT value FROM data WHERE key=?", ("MY_RoleStatistics_RoleStat.tAlertTodayVal",)).fetchone()
            con.close()
            if not row:
                continue
            parsed = MYDataParser(row[0]).value()
            data = parsed.get("d") if isinstance(parsed, dict) and isinstance(parsed.get("d"), dict) else parsed
            if not isinstance(data, dict):
                continue
            server = str(data.get("server") or data.get("servers") or "").strip()
            name = str(data.get("name") or data.get("names") or "").strip()
            if not server or not name:
                continue
            stat_time = int(float(data.get("time") or data.get("nTime") or 0))
            role_stat_file = db_path.parent / "role_statistics" / "role_stat.jx3dat"
            role_stat_mtime = int(role_stat_file.stat().st_mtime) if role_stat_file.exists() else 0
            role_stat_stale = bool(role_stat_mtime and stat_time and role_stat_mtime > stat_time + 60)
            stale_text = "待茗伊写盘"
            stat = {
                "guid": str(data.get("guid") or ""),
                "account": str(data.get("account") or data.get("accounts") or ""),
                "region": str(data.get("region") or data.get("regions") or ""),
                "server": server,
                "name": name,
                "level": fmt_num(data.get("level")),
                "score": fmt_num(data.get("equip_score")),
                "achievement": stale_text if role_stat_stale else fmt_num(data.get("achievement_score")),
                "pet_score": fmt_num(data.get("pet_score")),
                "money": stale_text if role_stat_stale else fmt_money(data.get("money")),
                "xiaxing": stale_text if role_stat_stale else fmt_num(data.get("justice")),
                "xiaxing_limit": stale_text if role_stat_stale else fmt_num(data.get("justice_remain")),
                "role_stamina": data.get("role_stamina"),
                "account_stamina": data.get("account_stamina"),
                "time": stat_time,
            }
            lookup[(server, name)] = stat
        except Exception as e:
            logger.warning("Failed to parse userdata.db at %s: %s", db_path, e)
            continue
    return lookup


def load_dungeon_growth_data(jx3_path: str) -> tuple[list[dict], str]:
    import sqlite3
    from src.core.instance_detect import dungeon_display_name
    db_path = find_dungeon_stat_db(jx3_path)
    if not db_path:
        return [], "未找到 dungeon_stat.v3.db。请确认茗伊角色统计-秘境统计已启用并保存。"
    con = sqlite3.connect(sqlite_readonly_uri(db_path), uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM DungeonInfo ORDER BY time DESC")]
    finally:
        con.close()
    records: list[dict] = []
    weekly_reset_ts = latest_weekly_dungeon_reset_ts()
    seen_roles: set[tuple[str, str]] = set()
    for r in rows:
        role_key = (str(r.get("server") or ""), str(r.get("name") or ""))
        if role_key in seen_roles:
            continue
        seen_roles.add(role_key)
        progress = parse_lua_bool_map(str(r.get("progress_info") or ""))
        copy_info = parse_lua_list_map(str(r.get("copy_info") or ""))
        dungeons = []
        record_time = int(float(r.get("time") or 0))
        reset_by_weekly_cd = bool(record_time and record_time < weekly_reset_ts)
        for mid in sorted(set(progress) | set(copy_info)):
            bosses = progress.get(mid) or []
            if reset_by_weekly_cd and bosses:
                bosses = [False for _ in bosses]
            killed = sum(1 for x in bosses if x)
            total = len(bosses)
            try:
                import src.core.jx3box_map as jx3box_map
                map_info = jx3box_map.get_dungeon_info(mid) or {}
            except Exception:
                map_info = {}
            boss_names = map_info.get("bosses", [])
            dungeons.append({
                "map_id": mid,
                "name": dungeon_display_name(mid),
                "progress": f"{killed}/{total}" if total else (copy_info.get(mid, ["已记录"])[0] if copy_info.get(mid) else "--"),
                "done": bool(total and killed >= total),
                "bosses": bosses,
                "boss_names": boss_names,
                "copy_ids": copy_info.get(mid) or [],
                "reset_by_weekly_cd": reset_by_weekly_cd,
                "weekly_reset_ts": weekly_reset_ts,
            })
        r["dungeons"] = dungeons
        records.append(r)
    return records, f"秘境读取：{db_path}"
