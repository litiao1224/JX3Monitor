from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jx3_click_monitor_gui_ctk import App


class GrowthColumnHarness:
    growth_role_columns = App.growth_role_columns
    growth_visible_dungeon_ids = App.growth_visible_dungeon_ids
    build_growth_dungeon_map = App.build_growth_dungeon_map

    def __init__(self) -> None:
        self.growth_dungeon_map = {
            "724": "冷龙峰",
            "794": "一之窟",
            "795": "九老洞",
        }
        self.selected_growth_dungeons = {"724", "794", "795"}


def test_growth_role_columns_use_readable_chinese_headers() -> None:
    columns = GrowthColumnHarness().growth_role_columns()

    assert [column["text"] for column in columns[:5]] == ["账号", "区服", "角色", "密码", "装分"]
    assert [column["text"] for column in columns[5:]] == ["冷龙峰", "一之窟", "九老洞"]
    assert not any("?" in str(column["text"]) for column in columns)


def test_build_growth_dungeon_map_uses_dungeon_names() -> None:
    records = [
        {"dungeons": [{"map_id": 724, "name": "冷龙峰"}]},
        {"dungeons": [{"map_id": "794", "name": "一之窟"}]},
        {"dungeons": [{"map_id": 795}]},
    ]

    dungeon_map = GrowthColumnHarness().build_growth_dungeon_map(records)
    assert dungeon_map.get("724") == "冷龙峰"


def test_growth_filter_texts_are_readable() -> None:
    source = (ROOT / "src/gui_ctk/pages/__init__.py").read_text(encoding="utf-8")

    growth_block = source[source.index('def build_growth_page'):source.index('def build_settings_page')]
    assert 'text="角色信息"' in growth_block or 'growth_role_columns' in source
    assert 'text="??"' not in growth_block
