# CLAUDE.md — 小鹦鹉记账 (JX3 Click Monitor)

## Project Overview

A desktop application for monitoring JX3 (剑网3) team raids (金团). It reads the game's local SQLite chat logs, parses auction/bid/purchase/wage events, and generates financial settlement reports.

**Tech stack:** Python 3.10+, CustomTkinter (GUI), SQLite (chat log reader), JSON/JSONL (data persistence)

**Key entry points:**
- `src/main.py` — GUI entry point (launches `src/gui_ctk/` via `src/gui/app.py`)
- `jx3_click_monitor.py` — CLI module (argparse-based, also re-exports core functions)
- `jx3_click_monitor_gui_ctk.py` — Main CustomTkinter GUI application

## Architecture

```
src/
├── core/              # Business logic (no GUI dependencies)
│   ├── utils.py       # Re-export compatibility layer (imports from submodules)
│   ├── patterns.py    # Regex patterns & constants for JX3 chat
│   ├── json_io.py     # JSON/JSONL read/write with atomic writes
│   ├── money.py       # Gold/silver/copper conversion
│   ├── text_utils.py  # Text normalization & gold amount parsing
│   ├── paths.py       # JX3 path resolution & wildcard matching
│   ├── timestamps.py  # Time helpers & session ID generation
│   ├── income_memory.py  # Income memory persistence helpers
│   ├── scanner.py     # SQLite chat log reader (incremental, read-only)
│   ├── parser.py      # Raw chat text → event type classification
│   ├── business_events.py  # Raw events → business events (auction, bid, etc.)
│   ├── auction.py     # Auction instance grouping & relist filtering
│   ├── analysis.py    # Session analysis → auction summary
│   ├── settlement.py  # Full settlement engine (orchestrator)
│   ├── reconciliation.py  # Snapshot dedup & purchase-gap analysis
│   ├── identity_inference.py  # Identity from game data files
│   ├── instance_detect.py   # Dungeon/instance detection
│   ├── session.py     # Session lifecycle management
│   ├── identity.py    # Role identity store (persistent name→class mapping)
│   └── report.py      # Text/JSON report generation
├── gui/               # Legacy Tkinter GUI (fallback)
├── gui_ctk/           # CustomTkinter GUI (primary)
│   ├── pages/         # Page modules (New, History, Income, Growth, Settings)
│   ├── widgets.py     # Custom CTk widgets (table, property grid, calendar)
│   ├── themes.py      # VS Code-inspired dark theme constants
│   ├── animations.py  # Fade/slide/pulse animation utilities
│   ├── dialogs.py     # All dialog windows (settlement confirm, income editor, etc.)
│   ├── error_handler.py  # @handle_ui_error decorator
│   ├── state.py       # AppState enum + StateMachine
│   └── icon_cache.py  # Two-tier icon cache (memory + disk)
├── services/          # External API clients
│   ├── jx3box_client.py   # JX3Box game data API
│   └── growth_service.py  # Character growth data service
├── data/              # Data access layer
│   └── income_repo.py     # SQLite-backed income records
├── config.py          # AppConfig with typed properties
└── logger.py          # Logging setup (file + console)
```

## Key Patterns

- **Session lifecycle:** create → poll (incremental SQLite scan) → analyze (business events) → settlement (financial report) → export
- **Data format:** Raw events in JSONL (append-only), analysis results in JSON
- **Atomic writes:** All JSON writes use tmp+rename pattern to prevent corruption
- **Error handling:** `@handle_ui_error` decorator for UI methods, `@handle_thread_error` for background threads
- **State machine:** `AppState` enum with validated transitions prevents illegal UI states

## Running Tests

```powershell
# Golden settlement regression test
python tests/test_golden_basic_settlement.py

# Full test suite
pytest tests/
```

## Dependency Management

- Runtime: `customtkinter`, `Pillow`
- Dev: `pytest`, `ruff`, `mypy` (see `pyproject.toml`)
- Build: PyInstaller `.spec` files for distributing standalone `.exe`

## Important Notes

- The app reads JX3 chat SQLite databases in **read-only mode** (`mode=ro` URI) — never modifies game files
- Chat log path convention: `<JX3_PATH>/interface/my#data/**/userdata/chat_log/chatlog_*.v2.db`
- Identity inference uses multiple fallback sources: `info.jx3dat`, `userdata.db`, DB file paths, HTML export filenames
- The `utils.py` re-export layer exists for backward compatibility — new code should import from specific submodules
