# -*- coding: utf-8 -*-
"""小鹦鹉记账 - LRU 图标缓存

两级缓存：
  1. 内存 LRU（OrderedDict，最多 200 项 CTkImage）
  2. 磁盘缓存（jx3box_item_cache.json，base64，最多 1000 项）

线程安全：所有写操作持 threading.Lock。
磁盘写入：懒惰写（累积 _DIRTY_THRESHOLD 次修改后刷盘），关闭时强制 flush。
"""
from __future__ import annotations

import base64
import json
import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

try:
    import customtkinter as ctk
    from PIL import Image
    import io
    _CTK_AVAILABLE = True
except ImportError:
    _CTK_AVAILABLE = False

logger = logging.getLogger("jx3_monitor.icon_cache")

_MEM_MAX = 200      # 内存最多缓存项数
_DISK_MAX = 1000    # 磁盘最多缓存项数
_DIRTY_THRESHOLD = 20  # 积累多少次写操作后刷盘


class IconCache:
    """两级图标缓存：内存 LRU + 磁盘 JSON base64。

    key 格式：任意字符串（通常为 f"icon:{icon_id}"）
    value 内存：CTkImage 对象
    value 磁盘：base64 编码的 PNG bytes
    """

    def __init__(self, disk_path: Optional[Path] = None) -> None:
        self._disk_path = disk_path
        self._mem: OrderedDict[str, "ctk.CTkImage"] = OrderedDict()
        self._disk: dict[str, str] = {}  # key → base64
        self._lock = threading.Lock()
        self._dirty_count = 0

        if disk_path:
            self._load_disk()

    # ── 公开接口 ──

    def get(self, key: str) -> Optional["ctk.CTkImage"]:
        """从内存获取缓存，命中时移到 LRU 末尾。"""
        with self._lock:
            if key in self._mem:
                self._mem.move_to_end(key)
                return self._mem[key]
        return None

    def get_b64(self, key: str) -> Optional[str]:
        """从磁盘缓存获取 base64，未命中返回 None。"""
        with self._lock:
            return self._disk.get(key)

    def put(self, key: str, image: "ctk.CTkImage", b64: Optional[str] = None) -> None:
        """写入内存缓存，可选同时写磁盘缓存。"""
        with self._lock:
            # 写内存
            self._mem[key] = image
            self._mem.move_to_end(key)
            if len(self._mem) > _MEM_MAX:
                evicted_key, _ = self._mem.popitem(last=False)
                logger.debug("内存缓存淘汰: %s", evicted_key)

            # 写磁盘
            if b64 is not None:
                self._disk[key] = b64
                self._dirty_count += 1
                # 淘汰最旧的磁盘项
                while len(self._disk) > _DISK_MAX:
                    oldest = next(iter(self._disk))
                    del self._disk[oldest]
                    logger.debug("磁盘缓存淘汰: %s", oldest)
                # 懒惰刷盘
                if self._dirty_count >= _DIRTY_THRESHOLD:
                    self._flush_disk_locked()

    def put_b64_only(self, key: str, b64: str) -> None:
        """仅写磁盘缓存（用于预填充，不构造 CTkImage）。"""
        with self._lock:
            self._disk[key] = b64
            self._dirty_count += 1
            while len(self._disk) > _DISK_MAX:
                oldest = next(iter(self._disk))
                del self._disk[oldest]
            if self._dirty_count >= _DIRTY_THRESHOLD:
                self._flush_disk_locked()

    def build_ctk_image(self, b64: str, size: tuple[int, int] = (40, 40)) -> Optional["ctk.CTkImage"]:
        """从 base64 构建 CTkImage（在后台线程调用，不持锁）。"""
        if not _CTK_AVAILABLE:
            return None
        try:
            img_data = base64.b64decode(b64)
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGBA")
            return ctk.CTkImage(pil_img, size=size)
        except Exception as e:
            logger.warning("构建 CTkImage 失败: %s", e)
            return None

    def flush(self) -> None:
        """强制将脏数据刷入磁盘。"""
        with self._lock:
            self._flush_disk_locked()

    def clear_memory(self) -> None:
        """清空内存缓存（不影响磁盘）。"""
        with self._lock:
            self._mem.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "memory_items": len(self._mem),
                "disk_items": len(self._disk),
                "dirty_count": self._dirty_count,
            }

    # ── 内部方法 ──

    def _load_disk(self) -> None:
        """从磁盘 JSON 加载缓存（启动时调用，不持锁）。"""
        if not self._disk_path or not self._disk_path.exists():
            return
        try:
            raw = self._disk_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                # 兼容旧格式（直接 dict）和新格式（带 schema）
                if "items" in data:
                    self._disk = {k: v for k, v in data["items"].items()
                                  if isinstance(k, str) and isinstance(v, str)}
                else:
                    self._disk = {k: v for k, v in data.items()
                                  if isinstance(k, str) and isinstance(v, str)}
            logger.info("磁盘图标缓存加载完成：%d 项", len(self._disk))
        except Exception as e:
            logger.warning("磁盘图标缓存加载失败: %s", e)
            self._disk = {}

    def _flush_disk_locked(self) -> None:
        """刷盘（调用前需持锁）。"""
        if not self._disk_path or not self._disk:
            self._dirty_count = 0
            return
        try:
            payload = {"schema": 1, "items": dict(self._disk)}
            tmp = self._disk_path.with_suffix(self._disk_path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            tmp.replace(self._disk_path)
            self._dirty_count = 0
            logger.debug("磁盘图标缓存已刷新：%d 项", len(self._disk))
        except Exception as e:
            logger.error("磁盘图标缓存写入失败: %s", e)

    def __del__(self) -> None:
        """析构时强制刷盘。"""
        try:
            if self._dirty_count > 0:
                self._flush_disk_locked()
        except Exception:
            pass


# ── 全局单例（惰性初始化）──

_global_cache: Optional[IconCache] = None
_global_lock = threading.Lock()


def get_icon_cache(disk_path: Optional[Path] = None) -> IconCache:
    """获取全局图标缓存单例。首次调用时传入 disk_path 以初始化磁盘缓存。"""
    global _global_cache
    with _global_lock:
        if _global_cache is None:
            _global_cache = IconCache(disk_path)
        return _global_cache
