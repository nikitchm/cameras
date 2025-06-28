from PyQt5.QtWidgets import QWidget, QPushButton, QMessageBox, QHBoxLayout, QGroupBox
from PyQt5.QtCore import pyqtSignal
import numpy as np

from ..plugin_interface import ExtraPlugin
from ...grabbers.camera_interface import CameraProperties

class AnalysisMockPlugin(ExtraPlugin):
    """
    An example extra plugin for real-time image analysis.
    """
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._name = "Image Analysis"
        self._is_active = False
        
        self.toggle_button = QPushButton("Toggle Analysis")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(self._is_active)
        self.toggle_button.clicked.connect(self._toggle_analysis)
        self.toggle_button.setEnabled(False) # Initially disabled

    def get_name(self) -> str:
        return self._name

    def init_plugin(self, camera_properties: CameraProperties):
        """
        Initializes the analysis plugin.
        """
        print(f"{self.get_name()}: Initialized with camera properties: {camera_properties.width}x{camera_properties.height}@{camera_properties.fps}fps")
        self.toggle_button.setEnabled(True)
        # If analysis should start by default when camera opens:
        # self._is_active = True
        # self.toggle_button.setChecked(True)

    def process_frame(self, frame: np.ndarray):
        """
        Performs analysis on the given frame if active.
        (Placeholder for actual analysis logic)
        """
        if self._is_active:
            # print(f"{self.get_name()}: Processing frame (shape: {frame.shape})")
            # Example: simple frame average calculation
            average_pixel_value = np.mean(frame)
            # print(f"  Average pixel value: {average_pixel_value:.2f}")
            pass # Replace with actual analysis logic

    def stop_plugin(self):
        """
        Stops the analysis plugin.
        """
        print(f"{self.get_name()}: Stopping plugin.")
        self._is_active = False
        self.toggle_button.setChecked(False)
        self.toggle_button.setEnabled(False)


    def get_ui_widget(self) -> QWidget:
        """
        Returns the toggle button widget.
        """
        return self.toggle_button

    def _toggle_analysis(self, checked: bool):
        """
        Toggles the analysis on or off.
        """
        self._is_active = checked
        status = "enabled" if checked else "disabled"
        print(f"{self.get_name()} {status}.")
        QMessageBox.information(self.viewer_parent, self.get_name(), f"Image Analysis {status}.")