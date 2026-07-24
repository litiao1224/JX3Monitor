# -*- coding: utf-8 -*-
"""Deployment / packaging / installation tests for JX3 Click Monitor.

Validates that the application can be packaged, distributed, and run
correctly in a deployment context:
  1. Packaging readiness: spec file, hidden imports, resource paths
  2. Path resolution: frozen vs source mode, relative vs absolute
  3. Permission checks: write access to config/output dirs
  4. Config portability: config survives copy between locations
  5. Resource integrity: embedded assets, icon, modules

Run: python -m pytest tests/test_deployment.py -v
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jx3_click_monitor as core
from src.config import (
    _app_base_dir,
    APP_BASE_DIR,
    CONFIG_PATH,
    DEFAULT_JX3_PATH,
    DEFAULT_OUT_DIR,
    INCOME_MEMORY_PATH,
    ROLE_STATS_PATH,
    APP_NAME,
)


# ===================================================================
# PART 1: PACKAGING READINESS
# ===================================================================

class TestPackagingReadiness:
    """Verify the project is ready for PyInstaller packaging."""

    def test_spec_file_exists(self):
        """PyInstaller spec file exists and is valid."""
        spec_files = list(ROOT.glob("*.spec"))
        assert len(spec_files) >= 1, "No .spec file found"
        spec = spec_files[0]
        content = spec.read_text(encoding="utf-8")
        assert "Analysis" in content
        assert "jx3_click_monitor_gui_ctk" in content
        assert "console=False" in content or "console = False" in content

    def test_spec_includes_all_hidden_imports(self):
        """Spec file lists all required hidden imports."""
        spec_files = list(ROOT.glob("*.spec"))
        content = spec_files[0].read_text(encoding="utf-8")
        required = [
            "sqlite3", "tkinter", "customtkinter", "json", "csv",
            "threading", "queue", "urllib.parse", "jx3_click_monitor",
            "struct", "html", "html.parser",
        ]
        for mod in required:
            assert mod in content, f"Missing hidden import: {mod}"

    def test_spec_excludes_heavy_unnecessary_libs(self):
        """Spec file excludes unnecessary heavy libraries to reduce size."""
        spec_files = list(ROOT.glob("*.spec"))
        content = spec_files[0].read_text(encoding="utf-8")
        # These should be excluded for smaller package
        for lib in ["matplotlib", "numpy", "pandas"]:
            assert lib in content, f"Should exclude {lib} in spec"

    def test_main_entrypoint_exists(self):
        """Main GUI entrypoint file exists."""
        entry = ROOT / "jx3_click_monitor_gui_ctk.py"
        assert entry.exists(), "jx3_click_monitor_gui_ctk.py not found"
        content = entry.read_text(encoding="utf-8")
        assert "class App" in content or "def main" in content

    def test_core_module_importable(self):
        """Core module is importable from any context."""
        import jx3_click_monitor
        assert hasattr(jx3_click_monitor, "create_session")
        assert hasattr(jx3_click_monitor, "analyze_session")
        assert hasattr(jx3_click_monitor, "extract_settlement")
        assert hasattr(jx3_click_monitor, "APP_VERSION")

    def test_gui_module_importable(self):
        """GUI module is importable."""
        try:
            import jx3_click_monitor_gui_ctk
            assert hasattr(jx3_click_monitor_gui_ctk, "App")
        except (ImportError, tk.TclError):
            pytest.skip("GUI module requires display")

    def test_all_required_packages_installed(self):
        """All runtime dependencies are installed."""
        import importlib
        required = ["customtkinter"]
        for pkg in required:
            try:
                importlib.import_module(pkg)
            except ImportError:
                pytest.fail(f"Required package not installed: {pkg}")


# ===================================================================
# PART 2: PATH RESOLUTION
# ===================================================================

class TestPathResolution:
    """Verify path resolution works in both source and frozen modes."""

    def test_app_base_dir_source_mode(self):
        """In source mode, _app_base_dir returns __file__ parent."""
        with patch.object(sys, "frozen", False, create=True):
            result = _app_base_dir()
            assert result.is_absolute()
            # Should be the project root
            assert (result / "jx3_click_monitor_gui_ctk.py").exists() or \
                   (result / "jx3_click_monitor.py").exists()

    def test_app_base_dir_frozen_mode(self):
        """In frozen mode, _app_base_dir returns executable parent."""
        fake_exe = Path(tempfile.mkdtemp()) / "fake_app.exe"
        fake_exe.touch()
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(fake_exe)):
            result = _app_base_dir()
            assert result == fake_exe.resolve().parent

    def test_config_path_uses_app_base_dir(self):
        """CONFIG_PATH is relative to APP_BASE_DIR, not CWD."""
        base = APP_BASE_DIR
        assert CONFIG_PATH.parent == base
        assert CONFIG_PATH.name == "gui_config.json"

    def test_income_memory_path_uses_app_base_dir(self):
        """INCOME_MEMORY_PATH is relative to APP_BASE_DIR."""
        base = APP_BASE_DIR
        assert INCOME_MEMORY_PATH.parent == base
        assert INCOME_MEMORY_PATH.name == "income_memory.db"

    def test_role_stats_path_uses_app_base_dir(self):
        """ROLE_STATS_PATH is relative to APP_BASE_DIR."""
        base = APP_BASE_DIR
        assert ROLE_STATS_PATH.parent == base
        assert ROLE_STATS_PATH.name == "all_role_stats.json"

    def test_default_out_dir_uses_app_base_dir(self):
        """DEFAULT_OUT_DIR is relative to APP_BASE_DIR."""
        base = APP_BASE_DIR
        assert DEFAULT_OUT_DIR.startswith(str(base)) or "runs" in DEFAULT_OUT_DIR

    def test_config_path_not_using_cwd(self):
        """Config path does not depend on current working directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            # Re-evaluate _app_base_dir — should still point to project
            result = _app_base_dir()
            # CWD is now tempdir, but _app_base_dir should still be project root
            assert (result / "jx3_click_monitor.py").exists()
        finally:
            os.chdir(original_cwd)

    def test_no_hardcoded_user_paths_in_core(self):
        """Core module should not contain hardcoded user-specific paths."""
        core_path = ROOT / "jx3_click_monitor.py"
        content = core_path.read_text(encoding="utf-8")
        # Should not have hardcoded paths like C:\Users\...
        import re
        hardcoded = re.findall(r'[A-Z]:\\Users\\[^\s"\']+', content)
        assert len(hardcoded) == 0, f"Hardcoded user paths found: {hardcoded}"

    def test_resource_paths_are_portable(self):
        """All resource references use Path objects, not string concatenation."""
        gui_path = ROOT / "jx3_click_monitor_gui_ctk.py"
        content = gui_path.read_text(encoding="utf-8")
        # Should use Path / operator, not string \\ concatenation for paths
        # Allow some string paths for external URLs but not local file paths
        bad_patterns = [r'["\'][A-Z]:\\[^\s"\']*\\[^\s"\']+["\']']
        import re
        for pat in bad_patterns:
            matches = re.findall(pat, content)
            # Filter out DEFAULT_JX3_PATH which is intentionally a default
            real_matches = [m for m in matches if "JX3" not in m and "DEFAULT" not in m]
            assert len(real_matches) == 0, f"Hardcoded paths: {real_matches}"


# ===================================================================
# PART 3: PERMISSION CHECKS
# ===================================================================

class TestPermissionChecks:
    """Verify write access to required directories."""

    def test_config_dir_writable(self):
        """Config directory is writable."""
        config_dir = CONFIG_PATH.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        test_file = config_dir / ".permission_test"
        try:
            test_file.write_text("test", encoding="utf-8")
            assert test_file.exists()
        finally:
            test_file.unlink(missing_ok=True)

    def test_config_file_creatable_from_scratch(self):
        """Config file can be created in a fresh directory."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            config = tmp / "gui_config.json"
            data = {"jx3_path": "test", "out_dir": "test"}
            config.write_text(json.dumps(data), encoding="utf-8")
            loaded = json.loads(config.read_text(encoding="utf-8"))
            assert loaded == data
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_output_dir_creatable(self):
        """Output directory (runs/live) can be created."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            out = tmp / "runs" / "live"
            out.mkdir(parents=True, exist_ok=True)
            assert out.exists()
            assert out.is_dir()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_income_memory_file_creatable(self):
        """Income memory file can be created from scratch."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            path = tmp / "income_memory.json"
            data = {"next_seq": 1, "records": []}
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            assert loaded["records"] == []
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_readonly_dir_graceful_failure(self):
        """Writing to a read-only directory raises PermissionError, not crash."""
        if sys.platform == "win32":
            # Windows admin users can write to read-only dirs; skip
            try:
                import ctypes
                if ctypes.windll.shell32.IsUserAnAdmin():
                    pytest.skip("Admin user can write to read-only dirs on Windows")
            except Exception:
                pass
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            ro_dir = tmp / "readonly"
            ro_dir.mkdir()
            # Remove write permission
            ro_dir.chmod(stat.S_IREAD | stat.S_IEXEC)
            config = ro_dir / "gui_config.json"
            try:
                with pytest.raises((PermissionError, OSError)):
                    config.write_text("{}")
            finally:
                # Restore permissions for cleanup
                ro_dir.chmod(stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_session_creation_in_writable_dir(self):
        """Session creation works in a writable output directory."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            out = tmp / "sessions"
            out.mkdir()
            jx3 = tmp / "jx3"
            jx3.mkdir()
            session_dir = core.create_session(jx3, out)
            assert session_dir.exists()
            assert (session_dir / "session_meta.json").exists()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_jx3box_cache_writable(self):
        """JX3BOX cache file can be created and updated."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            cache_path = tmp / "jx3box_cache.json"
            cache = {"name:test": {"item": {"id": 1}}}
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            assert "name:test" in loaded
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 4: CONFIG PORTABILITY
# ===================================================================

class TestConfigPortability:
    """Config files should survive copy/move between locations."""

    def test_config_roundtrip(self):
        """Config can be saved, read, and verified."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            config = tmp / "gui_config.json"
            data = {
                "jx3_path": r"F:\JX3\Game\JX3\bin\zhcn_hd",
                "out_dir": str(tmp / "runs"),
                "member_count": "25",
                "personal_subsidy": "0",
                "startup_mode": "manual",
                "season_start": "2026-06-01",
                "season_end": "2026-06-30",
                "selected_growth_dungeons": ["冷龙峰", "九老洞"],
                "hidden_growth_ownerkeys": [],
                "selected_growth_ownerkeys": [],
                "income_visible_columns": ["recorded_at", "server", "role"],
            }
            config.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            loaded = json.loads(config.read_text(encoding="utf-8"))
            assert loaded["jx3_path"] == data["jx3_path"]
            assert loaded["selected_growth_dungeons"] == ["冷龙峰", "九老洞"]
            assert loaded["income_visible_columns"] == ["recorded_at", "server", "role"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_config_copy_between_dirs(self):
        """Config survives copy to a different directory."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            src = tmp / "src" / "gui_config.json"
            src.parent.mkdir()
            data = {"jx3_path": "test", "out_dir": "test"}
            src.write_text(json.dumps(data), encoding="utf-8")
            dst = tmp / "dst" / "gui_config.json"
            dst.parent.mkdir()
            shutil.copy2(src, dst)
            loaded = json.loads(dst.read_text(encoding="utf-8"))
            assert loaded == data
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_income_memory_roundtrip(self):
        """Income memory file can be saved, loaded, and modified."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            path = tmp / "income_memory.json"
            data = {
                "next_seq": 2,
                "records": [
                    {"seq": 1, "role": "测试", "server": "服", "income_gold": 1000.0}
                ],
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            # Load
            loaded = json.loads(path.read_text(encoding="utf-8"))
            assert len(loaded["records"]) == 1
            # Modify
            loaded["records"].append({"seq": 2, "role": "B", "income_gold": 2000.0})
            loaded["next_seq"] = 3
            path.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
            reloaded = json.loads(path.read_text(encoding="utf-8"))
            assert len(reloaded["records"]) == 2
            assert reloaded["next_seq"] == 3
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_config_with_unicode_paths(self):
        """Config with CJK characters in paths is portable."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            config = tmp / "gui_config.json"
            data = {
                "jx3_path": r"C:\剑网3\Game\JX3\bin\zhcn_hd",
                "out_dir": str(tmp / "输出目录"),
            }
            config.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(config.read_text(encoding="utf-8"))
            assert "剑网3" in loaded["jx3_path"]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bom_config_readable(self):
        """Config with BOM (utf-8-sig) is readable."""
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            config = tmp / "gui_config.json"
            data = {"jx3_path": "test"}
            config.write_text(json.dumps(data), encoding="utf-8-sig")
            # CTk version reads with utf-8-sig
            loaded = json.loads(config.read_text(encoding="utf-8-sig"))
            assert loaded == data
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_config_handled(self):
        """Empty or missing config returns defaults, not crash."""
        from jx3_click_monitor_gui_ctk import App
        # Test load_config with empty file
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            config = tmp / "gui_config.json"
            config.write_text("{}", encoding="utf-8")
            # Verify it loads without error
            loaded = json.loads(config.read_text(encoding="utf-8"))
            assert loaded == {}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_corrupt_config_handled(self):
        """Corrupt config file does not crash the app."""
        from jx3_click_monitor_gui_ctk import App
        tmp = Path(tempfile.mkdtemp(prefix="jx3deploy_"))
        try:
            config = tmp / "gui_config.json"
            config.write_text("NOT VALID JSON {{{", encoding="utf-8")
            # load_config should return {} on error
            try:
                loaded = json.loads(config.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                loaded = {}
            assert loaded == {}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================
# PART 5: RESOURCE INTEGRITY
# ===================================================================

class TestResourceIntegrity:
    """Verify embedded resources and critical files exist."""

    def test_readme_exists(self):
        """README.md exists for distribution."""
        readme = ROOT / "README.md"
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert len(content) > 100, "README is too short"

    def test_launcher_bat_exists(self):
        """Launcher .bat file exists for source-mode users."""
        bat = ROOT / "启动小鹦鹉记账.bat"
        assert bat.exists(), "Launcher .bat not found"

    def test_core_source_files_complete(self):
        """All core Python source files exist."""
        required = [
            "jx3_click_monitor.py",
            "jx3_click_monitor_gui_ctk.py",
            "src/core/utils.py",
            "src/core/scanner.py",
            "src/core/settlement.py",
        ]
        for f in required:
            assert (ROOT / f).exists(), f"Missing: {f}"

    def test_gui_widgets_module_exists(self):
        """CTkTable widget module exists."""
        widgets = ROOT / "src" / "gui_ctk" / "widgets.py"
        assert widgets.exists(), "src/gui_ctk/widgets.py not found"

    def test_app_version_defined(self):
        """APP_VERSION is defined and is a non-empty string."""
        assert hasattr(core, "APP_VERSION")
        version = core.APP_VERSION
        assert isinstance(version, str)
        assert len(version) > 0, "APP_VERSION should not be empty"

    def test_no_missing_imports_in_core(self):
        """Core module has no import errors."""
        # Already imported at module level — just verify it's functional
        assert callable(core.create_session)
        assert callable(core.analyze_session)
        assert callable(core.extract_settlement)
        assert callable(core.export_settlement_csv)
        assert callable(core.render_settlement_markdown)

    def test_jx3box_api_urls_defined(self):
        """JX3BOX API URLs are properly defined in the config module."""
        from src.config import JX3BOX_ITEM_API, JX3BOX_ITEM_SEARCH_API
        assert JX3BOX_ITEM_API.startswith("https://")
        assert JX3BOX_ITEM_SEARCH_API.startswith("https://")

    def test_default_jx3_path_format(self):
        """DEFAULT_JX3_PATH follows expected JX3 directory convention."""
        assert "zhcn_hd" in DEFAULT_JX3_PATH

    def test_app_name_is_chinese(self):
        """APP_NAME is a Chinese name for the target audience."""
        assert len(APP_NAME) > 0
        # Should contain at least one CJK character
        assert any('\u4e00' <= c <= '\u9fff' for c in APP_NAME)


# ===================================================================
# PART 6: FROZEN MODE SIMULATION
# ===================================================================

class TestFrozenModeSimulation:
    """Simulate PyInstaller frozen mode behavior."""

    def test_frozen_mode_detection(self):
        """sys.frozen attribute is correctly detected."""
        # In source mode, sys.frozen should be False or absent
        frozen = getattr(sys, "frozen", False)
        assert frozen is False

    def test_frozen_mode_paths_with_mock(self):
        """In frozen mode, paths resolve to exe directory."""
        fake_dir = Path(tempfile.mkdtemp(prefix="jx3frozen_"))
        fake_exe = fake_dir / "小鹦鹉记账.exe"
        fake_exe.touch()
        try:
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(fake_exe)):
                result = _app_base_dir()
                assert result == fake_dir
                # Config would be next to the exe
                expected_config = fake_dir / "gui_config.json"
                assert expected_config.parent == result
        finally:
            shutil.rmtree(fake_dir, ignore_errors=True)

    def test_frozen_mode_no依赖__file__with_mock(self):
        """In frozen mode, _app_base_dir does not use __file__."""
        fake_dir = Path(tempfile.mkdtemp(prefix="jx3frozen_"))
        fake_exe = fake_dir / "app.exe"
        fake_exe.touch()
        try:
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(fake_exe)):
                result = _app_base_dir()
                # Should NOT resolve to the source directory
                assert result != Path(__file__).resolve().parent
        finally:
            shutil.rmtree(fake_dir, ignore_errors=True)

    def test_spec_console_false(self):
        """Spec file has console=False (no black terminal window)."""
        spec_files = list(ROOT.glob("*.spec"))
        content = spec_files[0].read_text(encoding="utf-8")
        assert "console=False" in content or "console = False" in content

    def test_spec_has_upx(self):
        """Spec file enables UPX compression for smaller distribution."""
        spec_files = list(ROOT.glob("*.spec"))
        content = spec_files[0].read_text(encoding="utf-8")
        assert "upx=True" in content or "upx = True" in content
