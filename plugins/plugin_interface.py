import abc
import numpy as np
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QObject

from ..grabbers.camera_interface import CameraProperties 

class ExtraPlugin(QObject):
    """
    Abstract base class for all extra plugins that can process camera frames.
    """
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.viewer_parent: QWidget = parent # Reference to the CameraViewer instance

    @abc.abstractmethod
    def init_plugin(self, camera_properties: CameraProperties):
        """
        Initializes the plugin with the camera properties.
        This method should be called when the camera is successfully opened.
        """
        pass

    @abc.abstractmethod
    def process_frame(self, frame: np.ndarray):
        """
        Processes a single camera frame.
        """
        pass

    @abc.abstractmethod
    def stop_plugin(self):
        """
        Stops and cleans up the plugin.
        This method should be called when the camera is closed or the application exits.
        """
        pass

    @abc.abstractmethod
    def get_ui_widget(self) -> QWidget:
        """
        Returns a QWidget (e.g., a button, a checkbox, or a group box)
        that will be added to the main camera viewer's UI.
        This widget should allow the user to interact with or enable/disable the plugin.
        Returns None if the plugin has no UI component to add to the main layout.
        """
        pass

    @abc.abstractmethod
    def get_name(self) -> str:
        """
        Returns the human-readable name of the plugin.
        """
        pass