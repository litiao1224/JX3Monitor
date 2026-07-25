# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for 小鹦鹉记账 v1.0.0."""

import os
from pathlib import Path

project_root = Path(os.getcwd())

a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'README.md'), '.'),
        (str(project_root / 'src' / 'gui' / 'icon.ico'), 'src/gui'),
        (str(project_root / 'jx3_click_monitor_gui_ctk.py'), '.'),
    ],
    hiddenimports=[
        # Standard library
        'sqlite3',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'tkinter.ttk',
        'customtkinter',
        'html',
        'html.parser',
        'urllib.parse',
        'winreg',
        'queue',
        'threading',
        'calendar',
        'json',
        'csv',
        'typing',
        'struct',
        'datetime',
        'time',
        're',
        'os',
        'sys',
        'pathlib',
        # CLI module
        'jx3_click_monitor',
        # Core modules (newly split)
        'src.core.utils',
        'src.core.scanner',
        'src.core.parser',
        'src.core.settlement',
        'src.core.analysis',
        'src.core.business_events',
        'src.core.auction',
        'src.core.reconciliation',
        'src.core.identity_inference',
        'src.core.instance_detect',
        'src.core.session',
        'src.core.identity',
        'src.core.report',
        'src.core.json_io',
        'src.core.money',
        'src.core.text_utils',
        'src.core.paths',
        'src.core.timestamps',
        'src.core.income_memory',
        'src.core.patterns',
        # GUI CTK modules
        'src.gui_ctk.widgets',
        'src.gui_ctk.themes',
        'src.gui_ctk.animations',
        'src.gui_ctk.error_handler',
        'src.gui_ctk.state',
        'src.gui_ctk.icon_cache',
        'src.gui_ctk.pages',
        'src.gui_ctk.dialogs',
        'src.gui_ctk.dialogs.shared',
        'src.gui_ctk.dialogs.settlement_confirm',
        'src.gui_ctk.dialogs.income_edit',
        'src.gui_ctk.dialogs.income_filter',
        'src.gui_ctk.dialogs.growth_selectors',
        'src.gui_ctk.dialogs.growth_filter',
        'src.gui_ctk.dialogs.config_picker',
        'src.gui_ctk.dialogs.chat_importer',
        # Services & Data
        'src.services.jx3box_client',
        'src.services.growth_service',
        'src.data.income_repo',
        # Legacy GUI
        'src.gui.app',
        'src.gui.theme',
        'src.gui.widgets',
        # Config & Logger
        'src.config',
        'src.logger',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'jupyter',
        'IPython',
        'pytest',
        'unittest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='小鹦鹉记账',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'src' / 'gui' / 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='小鹦鹉记账',
)
