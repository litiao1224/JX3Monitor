# -*- coding: utf-8 -*-
"""JX3 Click Monitor - Application configuration.

Central config management with file-based persistence.
升级：
- 补全所有业务字段的 @property
- 修复编码不一致（加载 utf-8-sig，保存 utf-8）
- 使用 write_json 原子写入（先写 .tmp 再 rename）
- 加载失败时自动降级为默认值
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.utils import read_json, write_json, ensure_dir

CONFIG_FILE = "jx3_monitor_config.json"

DEFAULTS: Dict[str, Any] = {
    # ── 核心路径 ──
    "jx3_path": "",
    "out_dir": "",
    # ── 角色 ──
    "my_role": "",
    "my_server": "",
    # ── 扫描参数 ──
    "scan_interval_ms": 1000,
    "auto_settle": True,
    "split_role": True,
    "split_item": True,
    # ── 窗口尺寸 ──
    "income_window_size": 800,
    "income_window_height": 600,
    "history_window_width": 900,
    "history_window_height": 700,
    # ── 外观 ──
    "theme": "default",
    # ── 金团配置 ──
    "member_count": "",
    "personal_subsidy": "",
    "startup_mode": "manual",
    # ── 赛季日期 ──
    "season_start": "",
    "season_end": "",
    # ── 离线扫描时间 ──
    "offline_start_time": "",
    "offline_end_time": "",
    # ── 角色成长 ──
    "selected_growth_dungeons": [],
    "hidden_growth_ownerkeys": [],
    "selected_growth_ownerkeys": [],
    # ── 收支统计列 ──
    "income_visible_columns": [
        "recorded_at", "server", "role", "instance",
        "income", "expense", "net", "black_role", "note",
    ],
    # ── 其他 ──
    "plugins": {},
    "version": 1,
}


class AppConfig:
    """Application-level configuration with typed property accessors."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / CONFIG_FILE
        self._path = config_path
        self._data: Dict[str, Any] = {}
        self.load()

    # ── 加载 / 保存 ──

    def _merge_defaults(self) -> None:
        for k, v in DEFAULTS.items():
            self._data.setdefault(k, v)

    def load(self) -> None:
        """加载配置文件，支持 UTF-8-BOM 编码，失败时降级为默认值。"""
        if self._path.exists():
            try:
                # 同时兼容 utf-8 和 utf-8-sig（带 BOM）
                raw = self._path.read_text(encoding="utf-8-sig")
                import json
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    self._data = loaded
                else:
                    self._data = {}
            except Exception:
                self._data = {}
        else:
            self._data = {}
        self._merge_defaults()

    def save(self) -> None:
        """原子写入配置（先写 .tmp，再 rename，防止写入中断损坏文件）。"""
        ensure_dir(self._path.parent)
        write_json(self._path, self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, **kwargs: Any) -> None:
        self._data.update(kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    # ── 核心路径 ──

    @property
    def jx3_path(self) -> str:
        return str(self._data.get("jx3_path", ""))

    @jx3_path.setter
    def jx3_path(self, value: str) -> None:
        self._data["jx3_path"] = value

    @property
    def out_dir(self) -> str:
        return str(self._data.get("out_dir", ""))

    @out_dir.setter
    def out_dir(self, value: str) -> None:
        self._data["out_dir"] = value

    # ── 角色 ──

    @property
    def my_role(self) -> str:
        return str(self._data.get("my_role", ""))

    @my_role.setter
    def my_role(self, value: str) -> None:
        self._data["my_role"] = value

    @property
    def my_server(self) -> str:
        return str(self._data.get("my_server", ""))

    @my_server.setter
    def my_server(self, value: str) -> None:
        self._data["my_server"] = value

    # ── 扫描参数 ──

    @property
    def scan_interval_ms(self) -> int:
        return int(self._data.get("scan_interval_ms", 1000))

    @scan_interval_ms.setter
    def scan_interval_ms(self, value: int) -> None:
        self._data["scan_interval_ms"] = int(value)

    @property
    def auto_settle(self) -> bool:
        return bool(self._data.get("auto_settle", True))

    @auto_settle.setter
    def auto_settle(self, value: bool) -> None:
        self._data["auto_settle"] = bool(value)

    # ── 金团配置 ──

    @property
    def member_count(self) -> str:
        return str(self._data.get("member_count", "") or "")

    @member_count.setter
    def member_count(self, value: str) -> None:
        self._data["member_count"] = value

    @property
    def personal_subsidy(self) -> str:
        return str(self._data.get("personal_subsidy", "") or "")

    @personal_subsidy.setter
    def personal_subsidy(self, value: str) -> None:
        self._data["personal_subsidy"] = value

    @property
    def startup_mode(self) -> str:
        return str(self._data.get("startup_mode", "manual") or "manual")

    @startup_mode.setter
    def startup_mode(self, value: str) -> None:
        self._data["startup_mode"] = value

    # ── 赛季日期 ──

    @property
    def season_start(self) -> str:
        return str(self._data.get("season_start", "") or "")

    @season_start.setter
    def season_start(self, value: str) -> None:
        self._data["season_start"] = value

    @property
    def season_end(self) -> str:
        return str(self._data.get("season_end", "") or "")

    @season_end.setter
    def season_end(self, value: str) -> None:
        self._data["season_end"] = value

    # ── 离线扫描时间 ──

    @property
    def offline_start_time(self) -> str:
        return str(self._data.get("offline_start_time", "") or "")

    @offline_start_time.setter
    def offline_start_time(self, value: str) -> None:
        self._data["offline_start_time"] = value

    @property
    def offline_end_time(self) -> str:
        return str(self._data.get("offline_end_time", "") or "")

    @offline_end_time.setter
    def offline_end_time(self, value: str) -> None:
        self._data["offline_end_time"] = value

    # ── 角色成长 ──

    @property
    def selected_growth_dungeons(self) -> List[str]:
        v = self._data.get("selected_growth_dungeons", [])
        return list(v) if v else []

    @selected_growth_dungeons.setter
    def selected_growth_dungeons(self, value: List[str]) -> None:
        self._data["selected_growth_dungeons"] = sorted(value)

    @property
    def hidden_growth_ownerkeys(self) -> List[str]:
        v = self._data.get("hidden_growth_ownerkeys", [])
        return list(v) if v else []

    @hidden_growth_ownerkeys.setter
    def hidden_growth_ownerkeys(self, value: List[str]) -> None:
        self._data["hidden_growth_ownerkeys"] = sorted(value)

    @property
    def selected_growth_ownerkeys(self) -> List[str]:
        v = self._data.get("selected_growth_ownerkeys", [])
        return list(v) if v else []

    @selected_growth_ownerkeys.setter
    def selected_growth_ownerkeys(self, value: List[str]) -> None:
        self._data["selected_growth_ownerkeys"] = sorted(value)

    # ── 收支统计列 ──

    @property
    def income_visible_columns(self) -> List[str]:
        v = self._data.get("income_visible_columns", [])
        return list(v) if v else DEFAULTS["income_visible_columns"][:]

    @income_visible_columns.setter
    def income_visible_columns(self, value: List[str]) -> None:
        self._data["income_visible_columns"] = list(value)

    # ── 方便方法 ──

    def sync_from_app(
        self,
        *,
        jx3_path: str = "",
        out_dir: str = "",
        member_count: str = "",
        personal_subsidy: str = "",
        startup_mode: str = "manual",
        season_start: str = "",
        season_end: str = "",
        offline_start_time: str = "",
        offline_end_time: str = "",
        selected_growth_dungeons: Optional[List[str]] = None,
        hidden_growth_ownerkeys: Optional[List[str]] = None,
        selected_growth_ownerkeys: Optional[List[str]] = None,
        income_visible_columns: Optional[List[str]] = None,
        **extra: Any,
    ) -> None:
        """从 App 的各个 StringVar 同步配置（一次性批量更新）。"""
        self.jx3_path = jx3_path
        self.out_dir = out_dir
        self.member_count = member_count
        self.personal_subsidy = personal_subsidy
        self.startup_mode = startup_mode
        self.season_start = season_start
        self.season_end = season_end
        self.offline_start_time = offline_start_time
        self.offline_end_time = offline_end_time
        if selected_growth_dungeons is not None:
            self.selected_growth_dungeons = selected_growth_dungeons
        if hidden_growth_ownerkeys is not None:
            self.hidden_growth_ownerkeys = hidden_growth_ownerkeys
        if selected_growth_ownerkeys is not None:
            self.selected_growth_ownerkeys = selected_growth_ownerkeys
        if income_visible_columns is not None:
            self.income_visible_columns = income_visible_columns
        self._data.update(extra)


# ── 模块级路径常量（供所有层直接 import，不依赖 GUI 文件） ──────────────

def _app_base_dir() -> Path:
    """返回应用根目录：打包时为 exe 所在目录，开发时为项目根目录。"""
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/config.py → src/ → project root
    return Path(__file__).resolve().parent.parent


APP_BASE_DIR: Path = _app_base_dir()

# ── 默认路径 ──
DEFAULT_JX3_PATH: str = r"F:\JX3\Game\JX3\bin\zhcn_hd"
DEFAULT_OUT_DIR: str = str(APP_BASE_DIR / "runs" / "live")
CONFIG_PATH: Path = APP_BASE_DIR / "gui_config.json"
INCOME_MEMORY_PATH: Path = APP_BASE_DIR / "income_memory.db"
ROLE_STATS_PATH: Path = APP_BASE_DIR / "all_role_stats.json"
JX3BOX_CACHE_PATH: Path = APP_BASE_DIR / "jx3box_item_cache.json"

# ── 应用标识 ──
APP_NAME: str = "小鹦鹉记账"
AUTOSTART_RUN_NAME: str = "JX3GoldMonitor"
JX3_PROCESS_NAMES: set = {"JX3ClientX64.exe", "JX3Client.exe", "GameClient.exe"}

# ── JX3BOX API ──
JX3BOX_ITEM_API: str = "https://node.jx3box.com/item"
JX3BOX_ITEM_SEARCH_API: str = "https://node.jx3box.com/item/search"
JX3BOX_ICON_URL: str = "https://icon.jx3box.com/icon/{icon_id}.png"
