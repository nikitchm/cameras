"""
The 'cameras' package provides a comprehensive PyQt5-based camera viewer
application with extensible features.

It includes:
- Core camera grabbing interfaces (in 'grabbers' subpackage).
- A graphical user interface for live camera feed and controls (camera_gui.py).
- A plugin system for adding new functionalities like video recording
  and image analysis (in 'plugins' subpackage).
- An executable entry point via __main__.py.
"""
__version__ = "0.1.0"  # Current version of your package
__author__ = "Max Nikitchenko"
# __email__ = "your.email@example.com"

# Public API of the 'cameras' package
# When someone does 'from cameras import *', these names will be imported.
__all__ = [
    'camera_gui',
    'grabbers',
    'plugins',
]