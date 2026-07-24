# -*- coding: utf-8 -*-
"""Backward-compatible re-exports for dialog modules.

All dialog classes have been split into dedicated submodules.
This file re-exports them so existing imports still work.
"""
from __future__ import annotations

from src.gui_ctk.dialogs.shared import (
    CustomMessageBox,
    ask_yes_no,
    position_dialog,
)
from src.gui_ctk.dialogs.settlement_confirm import SettlementConfirmDialog
from src.gui_ctk.dialogs.income_edit import IncomeEditDialog
from src.gui_ctk.dialogs.income_filter import (
    IncomeColumnsWindow,
    IncomeFilterWindow,
    IncomeAnalysisWindow,
)
from src.gui_ctk.dialogs.growth_selectors import (
    GrowthDungeonSelector,
    GrowthEquipmentWindow,
    GrowthRoleSelector,
)
from src.gui_ctk.dialogs.config_picker import ConfigDatetimePicker
from src.gui_ctk.dialogs.chat_importer import ChatImporter

__all__ = [
    "CustomMessageBox",
    "ask_yes_no",
    "position_dialog",
    "SettlementConfirmDialog",
    "IncomeEditDialog",
    "IncomeFilterWindow",
    "IncomeColumnsWindow",
    "IncomeAnalysisWindow",
    "GrowthRoleSelector",
    "GrowthDungeonSelector",
    "GrowthEquipmentWindow",
    "ConfigDatetimePicker",
    "ChatImporter",
]
