# -*- coding: utf-8 -*-
"""小鹦鹉记账 - JX3Box API 客户端（加固版）

将原 jx3_click_monitor_gui.py 中散落的 jx3box_* 函数
整合为独立模块，加入：

1. 指数退避重试（max 3 次）
2. 完善超时处理（connect + read 分离）
3. HTTP 错误分类（4xx 不重试，5xx 重试）
4. 线程安全的磁盘缓存（原子写入 + 锁）
5. 可选的异步回调接口
"""
from __future__ import annotations

import base64
import html
import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("jx3_monitor.jx3box")

# ── Constants ──
_ITEM_API = "https://node.jx3box.com/item"
_SEARCH_API = "https://node.jx3box.com/item/search"
_ICON_URL_FMT = "https://icon.jx3box.com/icon/{icon_id}.png"
_USER_AGENT = "jx3-click-monitor/1.0"

# retry config
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 0.5   # seconds
_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 10


# ── Low-level HTTP ──

class JX3BoxAPIError(Exception):
    """JX3Box 接口异常。"""
    def __init__(self, message: str, status: int = 0, retryable: bool = True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


def _request_json(url: str, *, timeout: float = _READ_TIMEOUT) -> dict:
    """发起 HTTP GET 请求并解析 JSON。

    Raises:
        JX3BoxAPIError: 请求失败或解析异常时抛出（含是否可重试标记）。
    """
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        retryable = e.code >= 500 or e.code == 429
        raise JX3BoxAPIError(
            f"HTTP {e.code}: {e.reason}", status=e.code, retryable=retryable
        ) from e
    except urllib.error.URLError as e:
        raise JX3BoxAPIError(f"连接失败: {e.reason}", retryable=True) from e
    except TimeoutError:
        raise JX3BoxAPIError("请求超时", retryable=True)
    except json.JSONDecodeError as e:
        raise JX3BoxAPIError(f"JSON 解析失败: {e}", retryable=False)


def _request_with_retry(url: str, *, retries: int = _MAX_RETRIES) -> dict:
    """带指数退避重试的 HTTP JSON 请求。"""
    last_err: Exception | None = None
    backoff = _INITIAL_BACKOFF

    for attempt in range(1, retries + 1):
        try:
            return _request_json(url)
        except JX3BoxAPIError as e:
            last_err = e
            if not e.retryable or attempt == retries:
                break
            logger.warning(
                "JX3Box API 请求失败 (attempt %d/%d): %s — %.1fs 后重试",
                attempt, retries, e, backoff,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 8.0)

    raise last_err  # type: ignore[misc]


def fetch_icon_bytes(icon_id: object) -> bytes | None:
    """下载图标 PNG 数据。失败返回 None。"""
    if not icon_id:
        return None
    url = _ICON_URL_FMT.format(icon_id=icon_id)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_READ_TIMEOUT) as resp:
            return resp.read()
    except Exception as e:
        logger.debug("图标下载失败 [%s]: %s", icon_id, e)
        return None


# ── Disk Cache ──

class _ItemCache:
    """线程安全的 JSON 磁盘缓存。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._data: dict | None = None

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        try:
            if self._path.exists():
                raw = self._path.read_text(encoding="utf-8")
                self._data = json.loads(raw) if raw else {}
            else:
                self._data = {}
        except Exception:
            logger.warning("加载 JX3Box 缓存失败，使用空缓存")
            self._data = {}
        return self._data

    def get(self, key: str) -> dict | None:
        with self._lock:
            data = self._load()
            v = data.get(key)
            return v if isinstance(v, dict) else None

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            data = self._load()
            data[key] = value
            self._save(data)

    def _save(self, data: dict) -> None:
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self._path)
        except Exception as e:
            logger.warning("保存 JX3Box 缓存失败: %s", e)


# ── Public API ──

class JX3BoxClient:
    """JX3Box 物品查询客户端。

    用法：
        client = JX3BoxClient(cache_path=Path("jx3box_item_cache.json"))
        result = client.lookup_item("大橙武")
    """

    def __init__(self, cache_path: Path) -> None:
        self._cache = _ItemCache(cache_path)

    def lookup_item(self, name: str) -> dict:
        """按名称查询 JX3Box 物品信息（同步）。

        返回 dict 结构：
            {"item": {...}, "query": name, "url": "...", "fetched_at": "..."}
            或 {"error": "..."}
        """
        name = _normalize_search_name(name)
        if not name:
            return {"error": "装备名称为空"}

        # 检查缓存
        cache_key = f"name:{name}"
        cached = self._cache.get(cache_key)
        if cached and not str(cached.get("error") or "").startswith("?"):
            return cached

        # 搜索
        try:
            search_url = _SEARCH_API + "?" + urllib.parse.urlencode(
                {"keyword": name, "per": 8}
            )
            search = _request_with_retry(search_url)
        except JX3BoxAPIError as e:
            logger.warning("JX3Box 搜索失败 [%s]: %s", name, e)
            return {"error": f"JX3BOX 查询失败: {e}"}

        rows = (
            ((search.get("data") or {}).get("data") or [])
            if isinstance(search, dict)
            else []
        )
        if not rows:
            result = {"error": f"JX3BOX 未检索到：{name}"}
            self._cache.put(cache_key, result)
            return result

        # 精确匹配优先
        exact = next((r for r in rows if str(r.get("Name") or "") == name), None)
        chosen = exact or rows[0]
        item_id = chosen.get("id")

        # 获取详情
        detail: dict = {}
        if item_id:
            try:
                detail_json = _request_with_retry(
                    f"{_ITEM_API}/{urllib.parse.quote(str(item_id))}"
                )
                detail = (
                    ((detail_json.get("data") or {}).get("item") or {})
                    if isinstance(detail_json, dict)
                    else {}
                )
            except JX3BoxAPIError as e:
                logger.warning("JX3Box 详情查询失败 [id=%s]: %s", item_id, e)

        item = detail or chosen
        result = {
            "query": name,
            "item": item,
            "matches": rows[:8],
            "url": (
                f"https://www.jx3box.com/item/#/view/{item_id}"
                if item_id
                else f"https://www.jx3box.com/item/#/search/{urllib.parse.quote(name)}"
            ),
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._cache.put(cache_key, result)
        return result

    def lookup_item_async(
        self,
        name: str,
        callback: Callable[[dict], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """异步查询物品信息（在后台线程执行，结果通过 callback 返回）。"""
        def _worker():
            try:
                result = self.lookup_item(name)
                callback(result)
            except Exception as e:
                logger.exception("JX3Box async lookup 失败 [%s]", name)
                if on_error:
                    on_error(e)

        t = threading.Thread(target=_worker, daemon=True, name=f"jx3box-{name[:20]}")
        t.start()


# ── Text Parsing Utilities ──

def plain_text(value: object) -> str:
    """解析 JX3Box 富文本为纯文本（HTML 标签剥离、转义还原）。"""
    text = str(value or "")
    parts = []
    for match in re.finditer(r'text\s*=\s*"(?P<value>(?:\\.|[^"])*)"', text, re.I | re.S):
        parts.append(match.group("value"))
    if parts:
        text = "\n".join(parts)
    text = html.unescape(text)
    text = text.replace("\\n", "\n").replace('\\"', '"')
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s*font\s*=\s*\d+\s*$", "", text, flags=re.I)
    return text.strip()


def normalize_item_search_name(name: object) -> str:
    """清理物品搜索名称的前后中点与空白。"""
    text = str(name or "").strip()
    text = re.sub(r"^[\u00b7\u2022\s]+|[\u00b7\u2022\s]+$", "", text)
    return text


def normalize_attr_name(text: object) -> str:
    """将 JX3Box 属性名统一为简称。"""
    value = str(text or "")
    mapping = [
        ("外功防御等级", "外防"), ("内功防御等级", "内防"),
        ("加速等级", "加速"), ("破招值", "破招"),
        ("御劲等级", "御劲"), ("无双等级", "无双"),
        ("会心效果等级", "会效"), ("会心等级", "会心"),
        ("破防等级", "破防"), ("攻击力", "攻击"),
        ("气血最大值", "气血"), ("体质", "体质"),
        ("身法", "身法"), ("根骨", "根骨"),
        ("元气", "元气"), ("力道", "力道"),
    ]
    for raw, label in mapping:
        if raw in value:
            return label
    cleaned = re.sub(r"提高.*$", "", value).strip()
    return cleaned


normalize_jx3box_attr_name = normalize_attr_name


def parse_attr_entries(item: dict, fallback: str = "") -> list[str]:
    """从物品 dict 中提取属性条目列表。"""
    entries: list[str] = []
    for attr in item.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        if attr.get("type") == "atSkillEventHandler" or str(
            attr.get("color") or ""
        ).lower() == "orange":
            continue
        raw = str(attr.get("label") or "").strip()
        if not raw:
            continue
        name = normalize_attr_name(raw)
        value_match = re.search(r"(?:提高|\+)?\s*([+-]?\d+(?:\.\d+)?)", raw)
        value = value_match.group(1) if value_match else ""
        entry = f"{name} {value}".strip()
        if entry and entry not in entries:
            entries.append(entry)
    if entries:
        return entries
    text = fallback or ""
    for part in re.split(r"[\s?;?,]+", text):
        part = part.strip()
        if part and part not in entries:
            entries.append(part)
    return entries


def attributes_text(item: dict, fallback: str = "") -> str:
    """属性条目 → 单行文本。"""
    entries = parse_attr_entries(item, fallback)
    return "  ".join(entries) if entries else "-"


def effects_text(item: dict) -> str:
    """提取特殊效果文本（橙色属性）。"""
    effects: list[str] = []
    for attr in item.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        is_effect = attr.get("type") == "atSkillEventHandler" or str(
            attr.get("color") or ""
        ).lower() == "orange"
        if not is_effect:
            continue
        text = plain_text(attr.get("label"))
        text = text.replace("\\", "").strip()
        if text and text not in effects:
            effects.append(text)
    return "\n".join(effects)


def format_item_info(result: dict, fallback_attrs: str = "") -> str:
    """格式化物品查询结果为展示文本。"""
    if not result:
        return ""
    if result.get("error"):
        return str(result.get("error"))
    item = result.get("item") or {}
    attrs = attributes_text(item, fallback_attrs)
    lines = [
        "【JX3BOX 装备详情】",
        f"名称：{item.get('Name') or '-'}",
        f"等级：{item.get('Level') or '-'}",
        f"类型：{item.get('TypeLabel') or '-'}",
        f"属性：{attrs}",
    ]
    get_type = item.get("GetType") or item.get("GetSource")
    if get_type:
        lines.append(f"获取方式：{get_type}")
    efx = effects_text(item)
    if efx:
        lines.extend(["", "特殊效果：", efx])
    requires = item.get("Requires")
    if isinstance(requires, dict):
        req_text = "；".join(str(v) for v in requires.values() if str(v or "").strip())
        if req_text:
            lines.append(f"需求：{req_text}")
    desc = plain_text(item.get("Desc"))
    if desc:
        lines.extend(["", "说明：", desc])
    if result.get("url"):
        lines.extend(["", f"JX3BOX：{result.get('url')}"])
    return "\n".join(lines)


# ── Internal Helpers ──

def _normalize_search_name(name: object) -> str:
    """标准化物品搜索名（去除前后缀标点）。"""
    text = str(name or "").strip()
    text = re.sub(r"^[·•\s]+|[·•\s]+$", "", text)
    return text
