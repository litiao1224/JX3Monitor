from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jx3_click_monitor_gui_ctk import App, repair_display_text


class HistoryColumnHarness:
    history_columns = App.history_columns


def test_history_columns_use_readable_chinese_headers() -> None:
    columns = HistoryColumnHarness().history_columns()

    assert [column["text"] for column in columns] == ["时间", "来源", "角色", "摘要"]
    assert not any("?" in str(column["text"]) for column in columns)


def test_repair_display_text_decodes_mojibake() -> None:
    assert repair_display_text("\u5a34\u5b2d\u762f\u93c8?") == "\u6d4b\u8bd5\u670d"
    assert repair_display_text("\u704f\u5fdb\u529f\u6963\u590b\u7974\u7487\u66de\u5f7f") == "\u5c0f\u9e66\u9e49\u6d4b\u8bd5\u53f7"


def test_repair_display_text_preserves_normal_text() -> None:
    assert repair_display_text("\u65b0\u7684\u8bb0\u5f55") == "\u65b0\u7684\u8bb0\u5f55"
    assert repair_display_text("-") == "-"
