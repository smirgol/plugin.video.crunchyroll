"""
pytest configuration for Crunchyroll plugin tests

Configures Python path and common fixtures for testing.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to Python path so tests can import from resources.lib
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Mock Kodi modules BEFORE any imports
sys.modules["xbmc"] = MagicMock()
sys.modules["xbmcgui"] = MagicMock()
sys.modules["xbmcplugin"] = MagicMock()
sys.modules["xbmcaddon"] = MagicMock()
sys.modules["xbmcvfs"] = MagicMock()

# Mock globals.G BEFORE importing resources.lib modules
mock_args = MagicMock()
mock_args.device_id = "test-device-id-12345"
mock_args.addon_name = "Crunchyroll Test"
mock_args.addon = MagicMock()
mock_args.addon.getLocalizedString = lambda x: f"String_{x}"

mock_g = MagicMock()
mock_g.args = mock_args

# Create a fake globals module
fake_globals = type(sys)("globals")
fake_globals.G = mock_g
sys.modules["resources.lib.globals"] = fake_globals

# Bind the fake module as an attribute on the parent package as well.
# On Python 3.8, unittest.mock._dot_lookup resolves patch targets via getattr on
# the parent package; without this binding, patch('resources.lib.globals.G') fails
# with AttributeError even though the module is present in sys.modules.
resources_lib = importlib.import_module("resources.lib")
resources_lib.globals = fake_globals
