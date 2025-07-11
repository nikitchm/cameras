# c:\Users\Max\Documents\codes\python\sandbox\PyQt_PySide_p3\opencv_camera_gui\pyqt5\video_recorder_gui.py

import os
# Changed from PyQt6 to PyQt5 imports
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QFileDialog, QMessageBox, QCheckBox
)
from PyQt5.QtCore import pyqtSignal
from .recording_thread import RecordingThread # Assuming this import

class RecorderWindow(QDialog):
    # Signal emitted when the window is closed, to allow parent to clean up
    close_signal = pyqtSignal()

    def __init__(self, recording_thread: RecordingThread, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Recorder")
        self.setGeometry(200, 200, 400, 150)

        self._recording_thread = recording_thread
        self._recording_thread.recording_status_changed.connect(self.update_button_states)

        self.init_ui()
        self.update_button_states(self._recording_thread.is_recording(), self._recording_thread.is_paused())

    def init_ui(self):
        main_layout = QVBoxLayout()

        # File Path selection
        file_path_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit("output.avi")
        self.browse_button = QPushButton("Browse...")
        file_path_layout.addWidget(QLabel("Output File:"))
        file_path_layout.addWidget(self.file_path_edit)
        file_path_layout.addWidget(self.browse_button)
        main_layout.addLayout(file_path_layout)

        self.timestamps_checkbox = QCheckBox("Create file with timestamps")
        self.timestamps_checkbox.setChecked(True) # Optional: set initial state
        main_layout.addWidget(self.timestamps_checkbox)

        # Control Buttons
        control_buttons_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Recording")
        self.pause_button = QPushButton("Pause Recording")
        self.stop_button = QPushButton("Stop Recording")
        control_buttons_layout.addWidget(self.start_button)
        control_buttons_layout.addWidget(self.pause_button)
        control_buttons_layout.addWidget(self.stop_button)
        main_layout.addLayout(control_buttons_layout)

        # Status Label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # Connect signals
        self.browse_button.clicked.connect(self.browse_file)
        self.start_button.clicked.connect(self.start_recording)
        self.pause_button.clicked.connect(self.pause_recording)
        self.stop_button.clicked.connect(self.stop_recording)

    def browse_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Video File",
                                                  self.file_path_edit.text(),
                                                  "Video Files (*.avi *.mp4);;All Files (*)", options=options)
        if file_name:
            self.file_path_edit.setText(file_name)

    def start_recording(self):
        file_path = self.file_path_edit.text()
        if not file_path:
            QMessageBox.warning(self, "Error", "Please specify an output file path.")
            return

        if self._recording_thread:
            if not self._recording_thread.is_recording():
                if self._recording_thread.start_recording(file_path, save_timestamps_in_separate_file=self.timestamps_checkbox.isChecked()):
                    self.status_label.setText(f"Recording: {os.path.basename(file_path)}")
                else:
                    QMessageBox.critical(self, "Error", "Failed to start recording.")
            else:
                QMessageBox.information(self, "Info", "Recording is already in progress.")

    def pause_recording(self):
        if self._recording_thread:
            if self._recording_thread.is_recording():
                self._recording_thread.pause_recording()
            else:
                QMessageBox.information(self, "Info", "No active recording to pause.")

    def stop_recording(self):
        if self._recording_thread:
            if self._recording_thread.is_recording():
                self._recording_thread.stop_recording()
                self.status_label.setText("Ready")
            else:
                QMessageBox.information(self, "Info", "No active recording to stop.")

    def update_button_states(self, is_recording: bool, is_paused: bool):
        """Updates the state of buttons based on recording status."""
        # print(f"RecorderWindow.update_button_states called with is_recording={is_recording}, is_paused={is_paused}")
        self.start_button.setEnabled(not is_recording)
        self.browse_button.setEnabled(not is_recording)
        self.file_path_edit.setEnabled(not is_recording)

        self.pause_button.setEnabled(is_recording)
        self.stop_button.setEnabled(is_recording)

        # print(f"  After update_button_states logic:")
        # print(f"    Start button enabled: {self.start_button.isEnabled()}")
        # print(f"    Pause button enabled: {self.pause_button.isEnabled()}")
        # print(f"    Stop button enabled: {self.stop_button.isEnabled()}")

        if is_recording:
            if is_paused:
                self.status_label.setText(f"Paused: {os.path.basename(self.file_path_edit.text())}")
                self.pause_button.setText("Resume Recording")
            else:
                self.status_label.setText(f"Recording: {os.path.basename(self.file_path_edit.text())}")
                self.pause_button.setText("Pause Recording")
        else:
            self.status_label.setText("Ready")
            self.pause_button.setText("Pause Recording") # Reset text when not recording

    def closeEvent(self, event):
        """Ensure signals are disconnected when the window is closed."""
        try:
            self._recording_thread.recording_status_changed.disconnect(self.update_button_states)
        except TypeError: # Signal might already be disconnected if app closes unexpectedly
            pass
        self.close_signal.emit() # Emit signal for parent cleanup
        super().closeEvent(event)