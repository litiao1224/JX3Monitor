import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from unittest.mock import MagicMock, patch
import pytest

from jx3_click_monitor_gui_ctk import App

@patch("jx3_click_monitor_gui_ctk.filedialog.askopenfilename")
@patch("jx3_click_monitor_gui_ctk.core.import_all_data", create=True)
@patch("jx3_click_monitor_gui_ctk.messagebox.showinfo")
def test_gui_mock_import_data(mock_showinfo, mock_import_all_data, mock_askopen):
    """Test importing zip data via GUI method."""
    mock_askopen.return_value = "/mock/backup.zip"
    
    app = MagicMock()
    app.load_config.return_value = {"mock": "config"}
    
    App.import_data(app)
    
    # Assert core import was called with path
    mock_import_all_data.assert_called_once()
    args = mock_import_all_data.call_args[0]
    assert Path(args[0]).as_posix() == "/mock/backup.zip"
    
    # Assert config was reloaded
    app.load_config.assert_called_once()
    assert app.config_data == {"mock": "config"}
    
    # Assert success message shown
    mock_showinfo.assert_called_once()
