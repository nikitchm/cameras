import sys
if False:
    print(f"--- DIAGNOSTICS: camera_gui.py ---")
    print(f"__name__: {__name__}")
    print(f"__package__: {__package__}")
    print(f"sys.path: {sys.path}")
    print(f"-----------------------------------")
import os
import cv2
import numpy as np
import argparse
import dataclasses
from enum import Enum
import traceback
import functools

from PyQt5.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, QComboBox,
    QPushButton, QHBoxLayout, QMessageBox, QDialog, QCheckBox, QMainWindow, QGroupBox, QStackedWidget, 
    QToolButton, QMenu, QAction
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QObject
from PyQt5 import QtCore

from typing import Union, Type, List

# Custom modules
from .grabbers.camera_interface import CameraGrabberInterface, CameraProperties

# Import the new plugin interface and specific plugins
from .plugins.plugin_interface import ExtraPlugin


# --- Conditional import for SharedMemoryFrameSender ---
try:
    from shared_memory_sender import SharedMemoryFrameSender
    _SHARED_MEMORY_IMPORTS_SUCCESSFUL = True
    SHARED_MEM_NAME = "CameraFrameMMF"
    SHARED_MUTEX_NAME = "CameraFrameMutex"
    DEFAULT_MAX_MMF_BUFFER_SIZE = 1920 * 1080 * 3
except ImportError as e:
    print(f"Warning: Shared Memory functionality disabled. Could not import pywin32 modules: {e}")
    print("Please ensure 'pywin32' is correctly installed and its DLLs are accessible.")
    _SHARED_MEMORY_IMPORTS_SUCCESSFUL = False
    SharedMemoryFrameSender = None

@dataclasses.dataclass
class Grabber:
    class KNOWN_GRABBERS:
        OPENCV = "opencv"
        PyCapture2 = "pycapture2"
    name: KNOWN_GRABBERS
    cls: Type[CameraGrabberInterface] # Use Type for class reference
    cam_settings_wnd: Type[QDialog] # Use Type for class reference
    settings: CameraProperties = None


# --- Frame Acquisition Thread ---
class FrameAcquisitionThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    camera_initialized = pyqtSignal(CameraProperties)

    def __init__(self, camera_grabber: CameraGrabberInterface, camera_index: int, desired_props: CameraProperties):
        super().__init__()
        self._grabber = camera_grabber
        self._camera_index = camera_index
        self._desired_props = desired_props
        self._running = True

    def run(self):
        try:
            actual_props = self._grabber.open(self._camera_index, self._desired_props)
            if not self._grabber.is_opened():
                self.error_occurred.emit(f"Camera {self._camera_index} failed to initialize.")
                return

            self.camera_initialized.emit(actual_props)

            while self._running:
                frame = self._grabber.get_frame()
                if frame is not None:
                    self.frame_ready.emit(frame)
                else:
                    self.error_occurred.emit(f"Failed to grab frame from Camera {self._camera_index}.")
                    self._running = False
                self.msleep(1) # Small delay to prevent 100% CPU usage
        except Exception as e:
            self.error_occurred.emit(f"An error occurred in acquisition thread: {e}")
            traceback.print_exc(file=sys.stdout)
        finally:
            if self._grabber:
                self._grabber.release()

    def stop(self):
        self._running = False
        self.quit()
        self.wait() # Wait for the thread to finish execution
        print(f"FrameAcquisitionThread for camera {self._camera_index} stopped.")
		# print(f"FrameAcquisitionThread for camera {self._grabber.name} stopped.")


# --- Main GUI Class ---
class CameraViewer(QMainWindow): #QDialog):
    def __init__(self, grabber: Type[Grabber], plugins: List[ExtraPlugin], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.available_cameras = []
        self._current_camera_index = -1
        self._frame_grabber = grabber # Renamed from _grabber to avoid conflict with instance
        self._camera_grabber: Union[CameraGrabberInterface, None] = None
        self.camera_thread: Union[FrameAcquisitionThread, None] = None
        self._actual_camera_properties: Union[CameraProperties, None] = None # Stores properties from the opened camera

        self.settings_window: Union[QDialog, None] = None

        self.shared_memory_sender: Union[SharedMemoryFrameSender, None] = None
        self.shared_frame_id_counter = 0
        self._shared_memory_available = _SHARED_MEMORY_IMPORTS_SUCCESSFUL

        self.extra_plugins: List[ExtraPlugin] = plugins
        # Ensure plugins have a reference to this viewer for UI elements
        for plugin in self.extra_plugins:
            plugin.viewer_parent = self

        self.init_ui()
        
        self.detect_and_populate_cameras()

    def init_ui2(self):
        main_layout = QVBoxLayout()

        top_layout = QHBoxLayout()
        self.camera_selector = QComboBox()
        self.camera_selector.currentIndexChanged.connect(self.switch_camera)
        top_layout.addWidget(self.camera_selector)

        self.refresh_button = QPushButton("Refresh Cameras")
        self.refresh_button.clicked.connect(self.detect_and_populate_cameras)
        top_layout.addWidget(self.refresh_button)

        self.settings_button = QPushButton("Camera Settings")
        self.settings_button.clicked.connect(self.open_camera_settings)
        self.settings_button.setEnabled(False) # Initially disabled
        top_layout.addWidget(self.settings_button)

        # Add shared memory checkbox to top layout
        self.mmf_checkbox = QCheckBox("Enable Shared Memory")
        self.mmf_checkbox.stateChanged.connect(self.toggle_shared_memory)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and self._actual_camera_properties is not None)
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")
        top_layout.addWidget(self.mmf_checkbox)

        main_layout.addLayout(top_layout)

        # Layout for extra plugins
        plugins_layout = QHBoxLayout()
        plugins_group_box = QGroupBox("Plugins")
        plugins_group_layout = QHBoxLayout()

        for plugin in self.extra_plugins:
            widget = plugin.get_ui_widget()
            if widget:
                plugins_group_layout.addWidget(widget)
        
        plugins_group_box.setLayout(plugins_group_layout)
        main_layout.addWidget(plugins_group_box)

        self.label = QLabel("No Camera Selected")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.label)

        self.setLayout(main_layout)
   
    def init_ui(self):
        # Create a central widget that will hold the main layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Set the main layout directly on the central widget
        main_layout = QVBoxLayout(central_widget)

        top_layout = QHBoxLayout()
        self.camera_selector = QComboBox()
        self.camera_selector.currentIndexChanged.connect(self.switch_camera)
        top_layout.addWidget(self.camera_selector)

        self.refresh_button = QPushButton("Refresh Cameras")
        self.refresh_button.clicked.connect(self.detect_and_populate_cameras)
        top_layout.addWidget(self.refresh_button)

        self.settings_button = QPushButton("Camera Settings")
        self.settings_button.clicked.connect(self.open_camera_settings)
        self.settings_button.setEnabled(False) # Initially disabled
        top_layout.addWidget(self.settings_button)

        # Add shared memory checkbox to top layout
        self.mmf_checkbox = QCheckBox("Enable Shared Memory")
        self.mmf_checkbox.stateChanged.connect(self.toggle_shared_memory)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and self._actual_camera_properties is not None)
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")
        top_layout.addWidget(self.mmf_checkbox)

        # Plugins QToolButton
        self.plugins_tool_button = QToolButton(self)
        self.plugins_tool_button.setText("Plugins") # Text on the button
        # self.plugins_tool_button.setIcon(QIcon('path/to/your/icon.png')) # Optional: use an icon
        self.plugins_tool_button.setPopupMode(QToolButton.InstantPopup) # Menu pops up instantly on click
        self.plugins_tool_button.setArrowType(Qt.DownArrow) # Adds a small down arrow to indicate a menu

        self.plugins_menu = QMenu(self) # Create the menu that will contain plugin actions

        if not self.extra_plugins:
            self.plugins_tool_button.setEnabled(False)
            self.plugins_tool_button.setText("No Plugins") # Concise text when disabled
        else:
            for plugin in self.extra_plugins:
                action = QAction(plugin.get_name(), self)
                # Connect the action's triggered signal to our activation slot
                action.triggered.connect(functools.partial(self._activate_selected_plugin, plugin))
                self.plugins_menu.addAction(action) # Add the action to the menu

        self.plugins_tool_button.setMenu(self.plugins_menu) # Set the created menu for the QToolButton
        top_layout.addWidget(self.plugins_tool_button) # <--- Add the QToolButton directly to top_layout

        main_layout.addLayout(top_layout)

        self.label = QLabel("No Camera Selected")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(self.label)

        self.setWindowTitle("Camera Viewer")
        # self.show() # You might call show() from outside, e.g., in __main__

    def _activate_selected_plugin(self, plugin: ExtraPlugin):
        """
        Activates the selected plugin's main action.
        This method is called when an action in the plugin menu is triggered.
        """
        print(f"Attempting to activate plugin: {plugin.get_name()}")

        plugin_main_widget = plugin.get_ui_widget()

        if isinstance(plugin_main_widget, QPushButton):
            plugin_main_widget.click() # Programmatically click the plugin's main button
            print(f"Plugin '{plugin.get_name()}' activated by programmatic click.")
        else:
            QMessageBox.information(self, "Plugin Activation",
                                    f"Plugin '{plugin.get_name()}' does not have a direct activation button "
                                    f"via its get_ui_widget method. Its UI might appear differently or require direct handling.")
            print(f"WARNING: Plugin '{plugin.get_name()}' get_ui_widget() returned {type(plugin_main_widget)}, "
                  f"not QPushButton. Cannot simulate click.")


    def detect_and_populate_cameras(self):
        temp_grabber = self._frame_grabber.cls()

        self.available_cameras = temp_grabber.detect_cameras()
        temp_grabber.release()

        try:
            self.camera_selector.currentIndexChanged.disconnect(self.switch_camera)
        except TypeError:
            pass
            
        self.camera_selector.clear()
        
        if self.available_cameras:
            self.camera_selector.addItems(self.available_cameras)
            
            initial_selection_made = False
            if self._current_camera_index != -1:
                if self._frame_grabber.name == Grabber.KNOWN_GRABBERS.OPENCV:
                     if f"Camera {self._current_camera_index}" in self.available_cameras:
                         self.camera_selector.setCurrentText(f"Camera {self._current_camera_index}")
                         initial_selection_made = True
                elif self._frame_grabber.name == Grabber.KNOWN_GRABBERS.PyCapture2:
                     if self._current_camera_index < self.camera_selector.count():
                         self.camera_selector.setCurrentIndex(self._current_camera_index)
                         initial_selection_made = True

            if not initial_selection_made and self.camera_selector.count() > 0:
                self.camera_selector.setCurrentIndex(0)
                initial_selection_made = True 

            self.camera_selector.currentIndexChanged.connect(self.switch_camera)
            
            if initial_selection_made:
                self.switch_camera()
            else:
                self.settings_button.setEnabled(False)
                self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
                self._current_camera_index = -1
                if self.camera_thread:
                    self.camera_thread.stop()
                    self.camera_thread = None
                for plugin in self.extra_plugins:
                    plugin.stop_plugin()

        else:
            self.camera_selector.addItem("No cameras found")
            self.label.setText("No cameras found.")
            self.settings_button.setEnabled(False)
            self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            self._current_camera_index = -1
            if self.camera_thread:
                self.camera_thread.stop()
                self.camera_thread = None
            for plugin in self.extra_plugins:
                plugin.stop_plugin()
            self.camera_selector.currentIndexChanged.connect(self.switch_camera)

    def start_camera(self, camera_index: int, desired_props: CameraProperties = None):
        """Starts a new camera acquisition thread with specified or default properties."""
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait()

        if self.shared_memory_sender:
            self.shared_memory_sender.release()
            self.shared_memory_sender = None
        self.mmf_checkbox.setChecked(False)

        # Stop and re-initialize all extra plugins
        for plugin in self.extra_plugins:
            plugin.stop_plugin()

        self._current_camera_index = camera_index
        self._camera_grabber = self._frame_grabber.cls()

        if desired_props is None:
            desired_props = CameraProperties(width=640, height=480, fps=30.0, brightness=-1, offsetX=0, offsetY=0)

        self.camera_thread = FrameAcquisitionThread(
            self._camera_grabber,
            self._current_camera_index,
            desired_props
        )
        self.camera_thread.frame_ready.connect(self._on_frame_ready)
        self.camera_thread.error_occurred.connect(self.handle_error)
        self.camera_thread.camera_initialized.connect(self._on_camera_initialized_and_start_display)
        self.camera_thread.start()

    def _on_camera_initialized_and_start_display(self, actual_props: CameraProperties):
        """Slot called when the camera acquisition thread initializes the camera."""
        self._actual_camera_properties = actual_props
        print(f"CameraViewer: Camera initialized with actual properties: {actual_props}")

        self.settings_button.setEnabled(True)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and True)
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")

        # Initialize all extra plugins with the actual camera properties
        for plugin in self.extra_plugins:
            print(f"____ actual props: {actual_props}")
            plugin.init_plugin(actual_props)


    def switch_camera(self):
        """Switch to the selected camera based on combobox selection."""
        selected_camera_text = self.camera_selector.currentText()
        if selected_camera_text and "No cameras found" not in selected_camera_text:
            camera_index = -1
            if self._frame_grabber.name == Grabber.KNOWN_GRABBERS.OPENCV:
                try:
                    camera_index = int(selected_camera_text.split()[-1])
                except (ValueError, IndexError):
                    print(f"Error: Could not parse OpenCV camera index from '{selected_camera_text}'.")
                    QMessageBox.warning(self, "Camera Selection Error", 
                                        f"Could not determine camera index from '{selected_camera_text}'. Please select a valid camera.")
                    return
            elif self._frame_grabber.name == Grabber.KNOWN_GRABBERS.PyCapture2:
                camera_index = self.camera_selector.currentIndex()
                if camera_index == -1:
                    QMessageBox.warning(self, "Camera Selection Error", 
                                        f"Could not determine camera index for '{selected_camera_text}'. Please select a valid camera.")
                    return

            if self._current_camera_index == camera_index and self.camera_thread and self.camera_thread.isRunning():
                print(f"Camera {camera_index} is already active and running.")
                return

            self.start_camera(camera_index, desired_props=self._frame_grabber.settings)
        else:
            self.settings_button.setEnabled(False)
            self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            self._current_camera_index = -1
            if self.camera_thread:
                self.camera_thread.stop()
                self.camera_thread = None
            for plugin in self.extra_plugins:
                plugin.stop_plugin()

    def _on_frame_ready(self, frame: np.ndarray):
        """Convert frame and display in QLabel, also pass to active plugins."""
        if self._actual_camera_properties:
            q_image = self.convert_cv_qt(frame)
            self.label.setPixmap(QPixmap.fromImage(q_image))

            # Pass frame to all active extra plugins
            for plugin in self.extra_plugins:
                plugin.process_frame(frame)

            if self._shared_memory_available and self.shared_memory_sender and self.shared_memory_sender.is_initialized:
                self.shared_frame_id_counter += 1
                if frame.ndim == 2:
                    frame_for_mmf = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else: 
                    frame_for_mmf = frame
                self.shared_memory_sender.write_frame(frame_for_mmf, self.shared_frame_id_counter)

    def convert_cv_qt(self, cv_img: np.ndarray) -> QImage:
        """Converts an OpenCV image (numpy array) to a QImage."""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

    def handle_error(self, error_message: str):
        """Handle camera or plugin errors."""
        QMessageBox.critical(self, "Error", error_message)
        self.label.setText(f"Error: {error_message}")
        
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
        
        for plugin in self.extra_plugins:
            plugin.stop_plugin()
        
        if self.shared_memory_sender:
            self.shared_memory_sender.release()
            self.shared_memory_sender = None
            self.mmf_checkbox.setChecked(False)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            
        self.settings_button.setEnabled(False)

    def open_camera_settings(self):
        if not self.settings_window or not self.settings_window.isVisible():
            self.settings_window = self._frame_grabber.cam_settings_wnd(
                self.camera_thread,
                self._camera_grabber,
                self._actual_camera_properties,
                parent=self
            )
            self.settings_window.settings_applied.connect(self.apply_camera_settings)
            self.settings_window.accepted.connect(self.handle_settings_window_closed)
            self.settings_window.rejected.connect(self.handle_settings_window_closed)
            self.settings_window.show()
        else:
            self.settings_window.activateWindow()
            self.settings_window.raise_()

    def handle_settings_window_closed(self):
        """Slot to handle the settings window closing."""
        if self.settings_window:
            try:
                self.settings_window.settings_applied.disconnect(self.apply_camera_settings)
            except TypeError:
                pass
            try:
                self.settings_window.accepted.disconnect(self.handle_settings_window_closed)
            except TypeError:
                pass
            try:
                self.settings_window.rejected.disconnect(self.handle_settings_window_closed)
            except TypeError:
                pass
            self.settings_window = None

    def apply_camera_settings(self, settings_props: CameraProperties):
        """Applies the settings received from the settings dialog by restarting the camera."""
        if self._camera_grabber and self._camera_grabber.is_opened():
            print(f"Applying new settings and re-opening camera: {settings_props}")
            self.start_camera(self._current_camera_index, settings_props)
        else:
            QMessageBox.warning(self, "No Active Camera", "No camera is currently active to apply settings to.")

    def toggle_shared_memory(self, state):
        """Handles enabling/disabling shared memory."""
        if not self._shared_memory_available:
            self.mmf_checkbox.setChecked(False)
            QMessageBox.warning(self, "Shared Memory Unavailable", "Shared Memory functionality is disabled due to an import error with pywin32 modules.")
            return

        if state == QtCore.Qt.Checked:
            if self._actual_camera_properties:
                width = self._actual_camera_properties.width
                height = self._actual_camera_properties.height
                buffer_size = width * height * 3
                
                if self.shared_memory_sender:
                    self.shared_memory_sender.release()

                try:
                    self.shared_memory_sender = SharedMemoryFrameSender(
                        name=SHARED_MEM_NAME,
                        mutex_name=SHARED_MUTEX_NAME,
                        max_buffer_size=buffer_size
                    )
                    if not self.shared_memory_sender.is_initialized:
                        QMessageBox.warning(self, "Shared Memory Error", "Failed to initialize Shared Memory. See console for details.")
                        self.mmf_checkbox.setChecked(False)
                except Exception as e:
                    QMessageBox.critical(self, "Shared Memory Fatal Error", f"An unexpected error occurred during Shared Memory setup: {e}\nShared memory will be disabled.")
                    self.shared_memory_sender = None
                    self.mmf_checkbox.setChecked(False)
                    self.mmf_checkbox.setEnabled(False)
                    self._shared_memory_available = False
            else:
                QMessageBox.warning(self, "Shared Memory", "Camera not active. Cannot enable shared memory.")
                self.mmf_checkbox.setChecked(False)
        else:
            if self.shared_memory_sender:
                self.shared_memory_sender.release()
                self.shared_memory_sender = None
                self.shared_frame_id_counter = 0

    def closeEvent(self, event):
        """Handles the main window closing event, ensuring all threads and resources are stopped."""
        print("Closing application. Stopping threads...")
        
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.wait()

        for plugin in self.extra_plugins:
            plugin.stop_plugin()

        if self.settings_window and self.settings_window.isVisible():
            self.settings_window.close()
        
        if self.shared_memory_sender:
            self.shared_memory_sender.release()

        if self._camera_grabber:
            self._camera_grabber.release()

        super().closeEvent(event)
        print("Application closed.")


def main():
    parser = argparse.ArgumentParser(description="Camera Viewer Application")
    parser.add_argument(
        "--grabber",
        type=str,
        choices=[Grabber.KNOWN_GRABBERS.OPENCV, Grabber.KNOWN_GRABBERS.PyCapture2],
        default=Grabber.KNOWN_GRABBERS.OPENCV,
        help=f"Choose camera grabber backend: '{Grabber.KNOWN_GRABBERS.OPENCV}' (default) or '{Grabber.KNOWN_GRABBERS.PyCapture2}'"
    )
    parser.add_argument("--width", type=int, default=640,
        help=f"Choose the width of the image to grab (should be supported by the camera)")
    parser.add_argument("--height", type=int, default=480,
        help=f"Choose the height of the image to grab (should be supported by the camera)")
    parser.add_argument("--offsetX", type=int, default=0,
        help=f"Choose the offsetX of the image to grab (should be supported by the camera)")
    parser.add_argument("--offsetY", type=int, default=0,
        help=f"Choose the offsetY of the image to grab (should be supported by the camera)")
    parser.add_argument("--fps", type=float, default=30,
        help=f"Choose the rate (frames per second (fps)) of acquisition.")
    parser.add_argument("--brightness", type=int, default=10,
        help=f"Choose the brightness of the image to grab (should be supported by the camera).")
    parser.add_argument("--mode", type=int, default=0,
        help=f"Choose the mode of acquisition (should be supported by the camera).")
    parser.add_argument("--enable-recorder", action="store_true", default=True,
        help="Enable the video recording plugin.")
    parser.add_argument("--enable-analysis", action="store_true", default=True,
        help="Enable the tail tracking plugin.")


    args = parser.parse_args()

    print(args)

    print(f'{args.grabber == Grabber.KNOWN_GRABBERS.PyCapture2}, {args.grabber}, {Grabber.KNOWN_GRABBERS.PyCapture2}')
    if args.grabber == Grabber.KNOWN_GRABBERS.PyCapture2:
        from .grabbers.pycapture2.pycapture2_grabber import PyCapture2Grabber
        from .grabbers.pycapture2.camera_settings_gui import SettingsWindow
        grabber_config = Grabber(name=Grabber.KNOWN_GRABBERS.PyCapture2, cls=PyCapture2Grabber, cam_settings_wnd=SettingsWindow,
                          settings=CameraProperties(width=args.width,
                                                    height=args.height,
                                                    fps=args.fps,
                                                    brightness=-1,
                                                    offsetX=args.offsetX,
                                                    offsetY=args.offsetY,
                                                    other={'mode':args.mode})
                         )
        print("Using PyCapture2 as camera grabber.")
    else:
        from .grabbers.opencv.opencv_grabber import OpenCVCapture
        from .grabbers.opencv.camera_settings_gui import SettingsWindow
        grabber_config = Grabber(name=Grabber.KNOWN_GRABBERS.OPENCV, cls=OpenCVCapture, cam_settings_wnd=SettingsWindow,
                            settings=CameraProperties(width=args.width,
                                                      height=args.height,
                                                      fps=args.fps,
                                                      brightness=args.brightness,
                                                      offsetX=args.offsetX,
                                                      offsetY=args.offsetY)
                        )
        if args.grabber == Grabber.KNOWN_GRABBERS.OPENCV:
            print("Using OpenCV as camera grabber.")
        else:
            print(f"Error: Unknown grabber '{args.grabber}'. Defaulting to OpenCV.")

    app = QApplication(sys.argv)

    # Initialize extra plugins based on command-line arguments
    enabled_plugins: List[ExtraPlugin] = []
    if args.enable_recorder:
        from .plugins.video_recorder.recorder_plugin import RecorderPlugin
        enabled_plugins.append(RecorderPlugin())
    if args.enable_analysis:
        from .plugins.tail_tracking.tail_tracking_plugin import TailTrackingPlugin
        enabled_plugins.append(TailTrackingPlugin())

    viewer = CameraViewer(grabber_config, enabled_plugins)
    viewer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
