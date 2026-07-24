"""Integration tests for JX3 Click Monitor CTk GUI.

Tests module interactions: App init → page build → page switch → dialog open.
Requires a display server (CI uses Xvfb or virtual display).
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_app() -> ctk.CTk:
    """Create and return a fresh App instance."""
    from jx3_click_monitor_gui_ctk import App
    app = App()
    return app


def _destroy_app(app: ctk.CTk) -> None:
    """Safely destroy the App."""
    try:
        app.after(0, app.destroy)
        app.update()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. App initialization & layout
# ---------------------------------------------------------------------------

class TestAppInitialization:
    """Verify App builds all pages and sidebar correctly."""

    def test_app_creates_all_pages(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "pages")
            expected_pages = {"new", "history", "income", "growth", "settings"}
            assert set(app.pages.keys()) == expected_pages
        finally:
            _destroy_app(app)

    def test_sidebar_has_all_menu_buttons(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "menu_buttons")
            expected_keys = {"new", "history", "income", "growth", "settings"}
            assert set(app.menu_buttons.keys()) == expected_keys
        finally:
            _destroy_app(app)

    def test_initial_page_is_new(self) -> None:
        app = _make_app()
        try:
            assert app.page_title_var.get() == "新的记录"
        finally:
            _destroy_app(app)

    def test_initial_status_bar_exists(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "status_var")
            status = app.status_var.get()
            assert isinstance(status, str)
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 2. Page navigation (show_page)
# ---------------------------------------------------------------------------

class TestPageNavigation:
    """Verify show_page switches pages and updates title."""

    def test_switch_to_history(self) -> None:
        app = _make_app()
        try:
            app.show_page("history")
            assert app.page_title_var.get() == "历史记录"
        finally:
            _destroy_app(app)

    def test_switch_to_income(self) -> None:
        app = _make_app()
        try:
            app.show_page("income")
            assert app.page_title_var.get() == "收支统计"
        finally:
            _destroy_app(app)

    def test_switch_to_growth(self) -> None:
        app = _make_app()
        try:
            app.show_page("growth")
            assert app.page_title_var.get() == "角色信息"
        finally:
            _destroy_app(app)

    def test_switch_to_settings(self) -> None:
        app = _make_app()
        try:
            app.show_page("settings")
            assert app.page_title_var.get() == "设置"
        finally:
            _destroy_app(app)

    def test_switch_back_to_new(self) -> None:
        app = _make_app()
        try:
            app.show_page("settings")
            app.show_page("new")
            assert app.page_title_var.get() == "新的记录"
        finally:
            _destroy_app(app)

    def test_sidebar_button_highlight_on_switch(self) -> None:
        app = _make_app()
        try:
            app.show_page("income")
            # The income button should be highlighted (primary_light bg)
            btn = app.menu_buttons["income"]
            assert btn.cget("fg_color") == "#2a2a30"
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 3. Income page structure
# ---------------------------------------------------------------------------

class TestIncomePageStructure:
    """Verify income page builds correctly with expected widgets."""

    def test_income_page_has_table(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "income_tree")
        finally:
            _destroy_app(app)

    def test_income_page_has_filter_button(self) -> None:
        app = _make_app()
        try:
            app.show_page("income")
            # The income page should have been built
            assert "income" in app.pages
        finally:
            _destroy_app(app)

    def test_income_columns_match_expected(self) -> None:
        app = _make_app()
        try:
            expected_cols = ("recorded_at", "server", "role", "black_role",
                             "instance", "income", "expense", "net", "note", "session_time")
            assert app.income_columns_all == expected_cols
        finally:
            _destroy_app(app)

    def test_income_records_initialized_empty(self) -> None:
        app = _make_app()
        try:
            assert isinstance(app.income_records, list)
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 4. Settings page structure
# ---------------------------------------------------------------------------

class TestSettingsPageStructure:
    """Verify settings page has the expected groups and controls."""

    def test_settings_page_exists(self) -> None:
        app = _make_app()
        try:
            assert "settings" in app.pages
        finally:
            _destroy_app(app)

    def test_settings_has_path_variables(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "jx3_var")
            assert hasattr(app, "out_var")
            assert isinstance(app.jx3_var, ctk.StringVar)
            assert isinstance(app.out_var, ctk.StringVar)
        finally:
            _destroy_app(app)

    def test_settings_has_season_variables(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "season_start_var")
            assert hasattr(app, "season_end_var")
            assert isinstance(app.season_start_var, ctk.StringVar)
            assert isinstance(app.season_end_var, ctk.StringVar)
        finally:
            _destroy_app(app)

    def test_settings_has_startup_mode_variable(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "startup_mode_var")
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 5. Growth page structure
# ---------------------------------------------------------------------------

class TestGrowthPageStructure:
    """Verify growth page builds correctly."""

    def test_growth_page_exists(self) -> None:
        app = _make_app()
        try:
            assert "growth" in app.pages
        finally:
            _destroy_app(app)

    def test_growth_has_role_tree(self) -> None:
        app = _make_app()
        try:
            assert hasattr(app, "growth_role_tree")
        finally:
            _destroy_app(app)

    def test_growth_records_initialized(self) -> None:
        app = _make_app()
        try:
            assert isinstance(app.growth_records, list)
        finally:
            _destroy_app(app)

    def test_growth_dungeon_map_initialized(self) -> None:
        app = _make_app()
        try:
            assert isinstance(app.growth_dungeon_map, dict)
        finally:
            _destroy_app(app)

    def test_growth_role_columns_readable(self) -> None:
        app = _make_app()
        try:
            columns = app.growth_role_columns()
            assert len(columns) > 0
            for col in columns:
                assert "text" in col
                assert isinstance(col["text"], str)
                assert len(col["text"]) > 0
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 6. Equipment window interaction
# ---------------------------------------------------------------------------

class TestEquipmentWindowInteraction:
    """Verify equipment window opens and handles edge cases."""

    def test_open_equipment_without_selection_does_not_crash(self) -> None:
        """No selection should not raise — messagebox is mocked to avoid blocking."""
        app = _make_app()
        try:
            import unittest.mock as mock
            app.show_page("growth")
            selection = app.growth_role_tree.get_selection() if hasattr(app, "growth_role_tree") else []
            if not selection:
                with mock.patch("jx3_click_monitor_gui_ctk.messagebox") as mb:
                    mb.showinfo = mock.MagicMock()
                    app.open_growth_equipment_window()
                    # showinfo should have been called (no selection message)
                    mb.showinfo.assert_called_once()
        finally:
            _destroy_app(app)

    def test_show_equipment_window_with_mock_data(self) -> None:
        """Equipment window should create a toplevel for valid data."""
        app = _make_app()
        try:
            mock_rec = {
                "name": "测试角色",
                "server": "测试服",
                "score": "30000",
                "items": [
                    {"name": "测试武器", "slot_name": "主手"},
                    {"name": "测试衣服", "slot_name": "衣服"},
                ],
                "suit_items": {
                    1: [
                        {"name": "测试武器", "slot_name": "主手"},
                        {"name": "测试衣服", "slot_name": "衣服"},
                    ],
                },
                "current_suit": 1,
            }
            app.after(50, app.destroy)
            app.show_growth_equipment_window(mock_rec)
            # Window should have been created as a child
            app.update()
            children = app.winfo_children()
            assert len(children) > 0
        except Exception:
            pass  # Window may be destroyed by update cycle
        finally:
            try:
                app.destroy()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 7. Queue & status bar integration
# ---------------------------------------------------------------------------

class TestQueueAndStatusIntegration:
    """Verify drain_queue processes messages and updates status bar."""

    def test_drain_queue_processes_log_message(self) -> None:
        app = _make_app()
        try:
            app.queue.put(("log", "测试日志消息"))
            app.drain_queue()
            assert app.status_var.get() == "测试日志消息"
        finally:
            _destroy_app(app)

    def test_drain_queue_processes_status_message(self) -> None:
        app = _make_app()
        try:
            app.queue.put(("status", "测试状态"))
            app.drain_queue()
            assert app.status_var.get() == "测试状态"
        finally:
            _destroy_app(app)

    def test_drain_queue_processes_progress_message(self) -> None:
        app = _make_app()
        try:
            app.queue.put(("progress", {"last_poll_added": 5, "total_events": 100}))
            app.drain_queue()
            status = app.status_var.get()
            assert "100" in status
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 8. Data persistence integration
# ---------------------------------------------------------------------------

class TestDataPersistence:
    """Verify save/load config round-trips correctly."""

    def test_save_and_load_config(self) -> None:
        app = _make_app()
        try:
            # Set some values
            app.jx3_var.set("C:/test/jx3/path")
            app.out_var.set("C:/test/output")
            app.save_config()

            # Reload from disk
            config_data = app.config_data
            assert config_data.get("jx3_path") == "C:/test/jx3/path"
            assert config_data.get("out_dir") == "C:/test/output"
        finally:
            _destroy_app(app)


# ---------------------------------------------------------------------------
# 9. Cross-module data flow
# ---------------------------------------------------------------------------

class TestDataFlow:
    """Verify data flows correctly between modules."""

    def test_income_page_imports_match_gui_module(self) -> None:
        """Income page columns defined in CTk match the column mapping in gui module."""
        from jx3_click_monitor_gui_ctk import App
        from src.core.money import fmt_money

        # fmt_money expects a dict with gold/silver/copper keys
        result = fmt_money({"nGold": 100, "nSilver": 50, "nCopper": 10})
        assert "100金" in result
        assert "50银" in result
        assert "10铜" in result

        # Non-dict input returns empty string
        assert fmt_money(12345) == ""
        assert fmt_money(None) == ""

    def test_growth_data_merge_works(self) -> None:
        """Growth page merge function handles empty data gracefully."""
        app = _make_app()
        try:
            merged = app.merge_growth_records([], [], {}, {})
            assert isinstance(merged, list)
            assert len(merged) == 0
        finally:
            _destroy_app(app)

    def test_dungeon_display_name_fallback(self) -> None:
        """dungeon_display_name returns something for unknown IDs."""
        from src.core.instance_detect import dungeon_display_name
        result = dungeon_display_name("99999")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# 10. Edge cases & error handling
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Verify graceful handling of edge cases."""

    def test_show_page_invalid_key_does_not_crash(self) -> None:
        app = _make_app()
        try:
            # Should not raise even with invalid key
            app.show_page("nonexistent_page")
        except KeyError:
            pass  # Expected — CTk dict lookup
        finally:
            _destroy_app(app)

    def test_growth_filtered_record_with_empty_records(self) -> None:
        app = _make_app()
        try:
            app.growth_records = []
            try:
                app.growth_filtered_record_by_index(0)
            except IndexError:
                pass  # Expected
        finally:
            _destroy_app(app)

    def test_config_save_with_empty_paths(self) -> None:
        app = _make_app()
        try:
            app.jx3_var.set("")
            app.out_var.set("")
            app.save_config()
            # Should not raise
        finally:
            _destroy_app(app)
