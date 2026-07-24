import sys
import types
from unittest.mock import MagicMock

# Create a mock module type to intercept missing modules
class MockModule(types.ModuleType):
    def __getattr__(self, name):
        return MagicMock()

# Mock tkinter and its submodules
sys.modules['tkinter'] = MockModule('tkinter')
sys.modules['tkinter.ttk'] = MockModule('tkinter.ttk')
sys.modules['tkinter.filedialog'] = MockModule('tkinter.filedialog')
sys.modules['tkinter.messagebox'] = MockModule('tkinter.messagebox')
sys.modules['tkinter.font'] = MockModule('tkinter.font')
sys.modules['tkinter.constants'] = MockModule('tkinter.constants')

# Mock winreg
sys.modules['winreg'] = MockModule('winreg')

# Mock customtkinter so that inheriting from its classes doesn't fail
class DummyWidget:
    def __init__(self, *args, **kwargs):
        self._config = kwargs
    def configure(self, **kwargs):
        self._config.update(kwargs)
    def cget(self, key):
        return self._config.get(key)
    def pack(self, *args, **kwargs): pass
    def pack_forget(self, *args, **kwargs): pass
    def __getattr__(self, name):
        return MagicMock()

class DummyVar:
    def __init__(self, value="", **kwargs):
        self._value = value
    def set(self, value):
        self._value = value
    def get(self):
        return self._value
    def trace_add(self, *args, **kwargs):
        pass

class MockCTKModule(types.ModuleType):
    def __getattr__(self, name):
        if name in ("StringVar", "BooleanVar", "IntVar", "DoubleVar"):
            return DummyVar
        return DummyWidget

sys.modules['customtkinter'] = MockCTKModule('customtkinter')

# Mock PIL
sys.modules['PIL'] = MockModule('PIL')
sys.modules['PIL.Image'] = MockModule('PIL.Image')
sys.modules['PIL.ImageTk'] = MockModule('PIL.ImageTk')
sys.modules['PIL.ImageFont'] = MockModule('PIL.ImageFont')
sys.modules['PIL.ImageDraw'] = MockModule('PIL.ImageDraw')
sys.modules['PIL.ImageSequence'] = MockModule('PIL.ImageSequence')
sys.modules['PIL.ImageChops'] = MockModule('PIL.ImageChops')
