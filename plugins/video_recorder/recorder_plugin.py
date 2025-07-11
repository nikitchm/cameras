from PyQt5.QtWidgets import QPushButton, QMessageBox, QHBoxLayout, QWidget, QGroupBox
from PyQt5.QtCore import pyqtSignal, QObject
import numpy as np

from ..plugin_interface import FrameProcessingPlugin
from ...grabbers.camera_interface import CameraProperties
from .recording_thread import RecordingThread
from .video_recorder_gui import RecorderWindow


class RecorderPlugin(FrameProcessingPlugin):
    """
    An extra plugin for video recording.
    Encapsulates the RecordingThread and RecorderWindow.
    """
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._name = "Video Recorder"
        self.recording_thread = RecordingThread()
        self.recording_thread.error_occurred.connect(self._handle_recording_error)
        
        self.recorder_window = RecorderWindow(self.recording_thread, parent=self.viewer_parent)
        self.recorder_window.close_signal.connect(self._handle_recorder_window_closed)
        self.recording_thread.recording_status_changed.connect(self.recorder_window.update_button_states)

        self.record_button = QPushButton("Record Video")
        self.record_button.clicked.connect(self._open_recorder_window)
        self.record_button.setEnabled(False) # Initially disabled

    def get_name(self) -> str:
        return self._name

    def init_plugin(self, camera_properties: CameraProperties):
        """
        Initializes the recorder plugin with camera properties.
        """
        self.recording_thread.set_video_properties(
            camera_properties.width,
            camera_properties.height,
            camera_properties.fps
        )
        self.record_button.setEnabled(True)
        self.recorder_window.update_button_states(self.recording_thread.is_recording(), self.recording_thread.is_paused())

    def process_frame(self, frame: np.ndarray):
        """
        Enqueues the frame for recording if recording is active.
        """
        if self.recording_thread.is_recording_active():
            self.recording_thread.enqueue_frame(frame)

    def stop_plugin(self):
        """
        Stops the recording thread and closes the recorder window.
        """
        print(f"{self.get_name()}: Stopping plugin.")
        if self.recording_thread:
            self.recording_thread.stop_recording()
        if self.recorder_window and self.recorder_window.isVisible():
            self.recorder_window.close()
        self.record_button.setEnabled(False)

    def get_ui_widget(self) -> QWidget:
        """
        Returns the record button widget to be added to the main UI.
        """
        # For simplicity, returning just the button. Could be a GroupBox if more controls are needed.
        return self.record_button

    def _open_recorder_window(self):
        """Opens the video recorder dialog."""
        if self.recording_thread: # _actual_camera_properties check is now in init_plugin
            self.recorder_window.show() # Show non-modally
            self.recorder_window.activateWindow() # Bring to front
            self.recorder_window.raise_()
        else:
            QMessageBox.information(self.viewer_parent, "Information", "Recording thread not initialized.")

    def _handle_recording_error(self, error_message: str):
        """Handle errors from the recording thread."""
        QMessageBox.critical(self.viewer_parent, "Recording Error", error_message)
        # Potentially disable recording button or take further action
        self.record_button.setEnabled(False)
        self.recorder_window.update_button_states(False, False)

    def _handle_recorder_window_closed(self):
        """Slot to handle the recorder window closing."""
        if self.recording_thread:
            self.recorder_window.update_button_states(self.recording_thread.is_recording(), self.recording_thread.is_paused())
        # The recorder_window object is kept, not cleared, as it's part of the plugin's state.