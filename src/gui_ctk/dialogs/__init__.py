# -*- coding: utf-8 -*-
"""CTk dialog windows for JX3 Click Monitor.

All dialogs are CTkToplevel subclasses using the neutral Codex-like theme.

This package re-exports all dialog classes for backward compatibility.
New code should import from specific submodules.
"""
from __future__ import annotations

# Shared helpers
from src.gui_ctk.dialogs.shared import (
    CustomMessageBox,
    CustomInputDialog,
    ask_yes_no,
    show_info,
    prompt_input,
    position_dialog,
)

# Settlement confirm
from src.gui_ctk.dialogs.settlement_confirm import SettlementConfirmDialog

# Income edit
from src.gui_ctk.dialogs.income_edit import IncomeEditDialog

# Income filter / columns / analysis
from src.gui_ctk.dialogs.income_filter import (
    IncomeColumnsWindow,
    IncomeFilterWindow,
    IncomeAnalysisWindow,
)

# Growth selectors
from src.gui_ctk.dialogs.growth_filter import GrowthFilterDialog

from src.gui_ctk.dialogs.growth_selectors import (
    GrowthDungeonSelector,
    GrowthEquipmentWindow,
    GrowthRoleSelector,
)

# Config picker
from src.gui_ctk.dialogs.config_picker import ConfigDatetimePicker

# Chat importer
from src.gui_ctk.dialogs.chat_importer import ChatImporter

__all__ = [
    "CustomMessageBox",
    "CustomInputDialog",
    "ask_yes_no",
    "show_info",
    "prompt_input",
    "position_dialog",
    "SettlementConfirmDialog",
    "IncomeEditDialog",
    "IncomeFilterWindow",
    "IncomeColumnsWindow",
    "IncomeAnalysisWindow",
    "GrowthRoleSelector",
    "GrowthDungeonSelector",
    "GrowthEquipmentWindow",
    "GrowthFilterDialog",
    "ConfigDatetimePicker",
    "ChatImporter",
]
