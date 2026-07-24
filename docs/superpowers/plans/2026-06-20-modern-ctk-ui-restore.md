# Modern CTK UI Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the modern CustomTkinter UI entrypoint while preserving correct Chinese text and fixing role growth headers/dungeon names.

**Architecture:** Replace the damaged CTK entrypoint with a focused modern shell that reuses existing business logic from `jx3_click_monitor_gui.py`. Keep the UI small enough to verify quickly: sidebar, dashboard/history/income/growth/settings pages, and working growth refresh/rendering.

**Tech Stack:** Python 3.14, CustomTkinter, Tkinter message/file dialogs, existing `CTkTable` widget and current project business helpers.

---

### Task 1: CTK UI Regression Tests

**Files:**
- Create/modify: `tests/test_growth_columns.py`
- Modify: `jx3_click_monitor_gui_ctk.py`

- [ ] Ensure tests assert CTK growth columns use `账号`, `区服`, `角色`, `装分` and mapped dungeon names.
- [ ] Ensure tests can import `App` without creating a window.
- [ ] Run: `C:\Users\litia\AppData\Local\Python\bin\python.exe -c "import sys; sys.path.insert(0, r'E:\OpenClaw\workspace\jx3_click_monitor'); import tests.test_growth_columns as t; t.test_growth_role_columns_use_readable_chinese_headers(); t.test_build_growth_dungeon_map_uses_dungeon_names(); print('growth columns passed')"`
- [ ] Expected initial result before implementation: fails because safe launcher has no `App`.

### Task 2: Rebuild Modern CTK Entrypoint

**Files:**
- Replace: `jx3_click_monitor_gui_ctk.py`

- [ ] Implement `App(ctk.CTk)` with dark/gold theme constants.
- [ ] Add sidebar pages: `新的记录`, `历史记录`, `收支统计`, `角色成长`, `设置`.
- [ ] Add safe page builders with Chinese labels only; no mojibake literals.
- [ ] Reuse `src.gui_ctk.widgets.CTkTable` for tables.
- [ ] Add `main()` that starts the CTK app.

### Task 3: Growth Page Data Integration

**Files:**
- Modify: `jx3_click_monitor_gui_ctk.py`

- [ ] Import existing helpers: `load_character_growth_data`, `load_dungeon_growth_data`, `load_account_lookup`, `load_role_stat_userdata_lookup`, `dungeon_display_name`, `fmt_money`.
- [ ] Implement `build_growth_dungeon_map(records)`.
- [ ] Implement `growth_role_columns()` with readable Chinese headers and dungeon names.
- [ ] Implement `refresh_growth_page()` to load data, merge minimal records, update filters/table.
- [ ] Keep account/server filters and a refresh button.

### Task 4: Verification and Preview

**Files:**
- Verify: `jx3_click_monitor_gui_ctk.py`
- Verify: `tests/test_growth_columns.py`

- [ ] Run py_compile for CTK and tests.
- [ ] Run growth column tests manually.
- [ ] Run existing golden settlement test.
- [ ] Launch `jx3_click_monitor_gui_ctk.py` once for user preview.

---

Self-review: The plan focuses only on restoring the modern CTK entrypoint and role growth display. It avoids rewriting settlement/business logic and avoids using the damaged mojibake source as a base.
