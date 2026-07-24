import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from unittest.mock import MagicMock, patch
import pytest

from jx3_click_monitor_gui_ctk import App, SettlementConfirmDialog

@patch("jx3_click_monitor_gui_ctk.core.extract_settlement")
def test_gui_mock_settlement_flow(mock_extract):
    """Test the settlement flow without rendering."""
    # Setup mock data
    mock_extract.return_value = {
        "total_auction_gold": 100000,
        "member_count": 25,
        "purchases": [],
        "instance_name": "Test Instance"
    }

    app = MagicMock()
    app.session_dir = Path("/mock/session")
    app.new_report = {
        "total_auction_gold": 100000,
        "member_count": 25,
        "purchases": [],
        "instance_name": "Test Instance"
    }
    
    # Call the settlement dialog directly
    with patch("jx3_click_monitor_gui_ctk.SettlementConfirmDialog") as mock_dialog:
        App.open_settlement_confirm_dialog(app)
        
        # Verify it tries to create the dialog
        mock_dialog.assert_called_once()
        args, kwargs = mock_dialog.call_args
        assert args[2] == Path("/mock/session")
        assert args[3]["total_auction_gold"] == 100000

def test_settlement_confirm_dialog_calculations():
    app = MagicMock()
    parent = MagicMock()
    
    report = {
        "total_auction_gold": 200000,
        "member_count": 20,
        "purchases": [
            {"item": "Sword", "buyer": "TestBuyer", "amount_gold": 10000, "target": "TestBuyer"}
        ],
        "instance_name": "Test Raid"
    }
    
    dialog = MagicMock(spec=SettlementConfirmDialog)
    dialog.report = report
    
    base_income = SettlementConfirmDialog.default_income_gold(dialog)
    assert base_income == 0.0
