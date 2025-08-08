# Main module in a python package for the control of frame grabbers and is responsible for the selection 
# of the used frame grabber, mechanism of sharing data with other processes and selection of the plugin for
# post-processing of the acquired frames.
# See docs/README.md details.
# To start, either 

import sys
if False:
    print(f"-----------------------------------")
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
import colorama

colorama.init(autoreset=True)   # autoreset=True ensures that after each print, the styling is reset back to the default terminal color, so you don't have to manually add Style.RESET_ALL.

script_dir = os.path.dirname(os.path.abspath(__file__))

from PyQt5.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, QComboBox,
    QPushButton, QHBoxLayout, QMessageBox, QDialog, QCheckBox, QMainWindow, QGroupBox, QStackedWidget, 
    QToolButton, QMenu, QAction, QScrollArea
)
from PyQt5.QtGui import QImage, QPixmap, QIcon
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QObject, QSize
from PyQt5 import QtCore

from typing import Union, Type, List

# Custom modules
from .grabbers.camera_interface import CameraGrabberInterface, CameraProperties, Grabber, Source

# Import the new plugin interface and specific plugins
from .plugins.plugin_interface import FrameProcessingPlugin

from .utils.dataclass_utils import create_child_from_parent, create_child_from_parent_deep
from .utils.common import print_error, print_warning

# --- SharedMemoryFrameSender ---
try:
    from .utils.shared_memory_sender import SharedMemoryFrameSender
    _SHARED_MEMORY_IMPORTS_SUCCESSFUL = True
    SHARED_MEM_NAME = "CameraFrameMMF"
    SHARED_MUTEX_NAME = "CameraFrameMutex"
    DEFAULT_MAX_MMF_BUFFER_SIZE = 2048 * 2048 * 3
except ImportError as e:
    print_error(f"Warning: Shared Memory functionality disabled. Could not import pywin32 modules: {e}")
    print("Please ensure 'pywin32' is correctly installed and its DLLs are accessible.")
    _SHARED_MEMORY_IMPORTS_SUCCESSFUL = False
    SharedMemoryFrameSender = None


# --- Frame Acquisition Thread ---
class FrameAcquisitionThread(QThread):
    """
    QThread's start() method starts a new thread and runs the run() method defined below.
    """
    frame_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    camera_initialized = pyqtSignal(CameraProperties)

    def __init__(self, src: Source, ms_sleep_bs_acquisitions: int=1):
        super().__init__()
        self._grabber = src.obj
        self._src = src
        self._src_internal_id = src.id
        self._desired_props = src.settings
        self._running = True
        self.ms_sleep_bs_acquisitions = ms_sleep_bs_acquisitions

    def run(self):
        # This method is called by the .start() method of QThread after the thread has been created
        try:
            # actual_props = self._grabber.open(self._src_internal_id, self._desired_props)
            self._src = self._grabber.open(self._src)
            actual_props = self._src.settings
            if not self._grabber.is_opened():
                self.print(f"Camera '{self._src_internal_id}' failed to initialize.")
                self.error_occurred.emit(f"Camera '{self._src_internal_id}' failed to initialize.")
                return
            self.camera_initialized.emit(actual_props)
            while self._running:
                frame = self._grabber.get_frame()
                if frame is not None:
                    self.send_frame(frame)
                else:
                    self.error_occurred.emit(f"Failed to grab frame from Camera {self._src_internal_id}.")
                    self._running = False
                if self.ms_sleep_bs_acquisitions > 0:
                    self.msleep(self.ms_sleep_bs_acquisitions) # Small delay to prevent 100% CPU usage
        except Exception as e:
            self.print_error(f"error: {e}")
            self.error_occurred.emit(f"An error occurred in acquisition thread: {e}")
            traceback.print_exc(file=sys.stdout)
        finally:
            if self._grabber:
                self._grabber.release()

    def send_frame(self, frame):
        #! should be replaced with a class for sharing data using different methods,
        # with an option of sharing using several methods, potentially, simultaneously over several channels
        self.frame_ready.emit(frame)

    def stop(self):
        self._running = False
        self.quit()
        self.wait() # Wait for the thread to finish execution
        self.print(f"Camera '{self._src_internal_id}' thread stopped.")

    def print(self, s):
        print(f"FrameAcquisitionThread: {s}")

    def print_error(self, s):
        print_error(f"FrameAcquisitionThread: {s}")


#! Split into FrameGrabberManager and CameraViewer

class CameraViewer(QMainWindow):
    def __init__(self, grabbers: Type[Grabber], plugins: List[FrameProcessingPlugin], autoplay: bool=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.autoplay = autoplay
        self._framegrabber_initialized = False
        self.available_sources = List[Source]
        self._current_src_index = 0
        self._current_src : Source = None
        self._frame_grabbers = grabbers         # requested frame grabbers / sources
        self.camera_thread: Union[FrameAcquisitionThread, None] = None
        self._actual_camera_properties: Union[CameraProperties, None] = None # Stores properties from the opened camera

        self.settings_window: Union[QDialog, None] = None

        self.shared_memory_sender: Union[SharedMemoryFrameSender, None] = None
        self.shared_frame_id_counter = 1
        self._shared_memory_available = _SHARED_MEMORY_IMPORTS_SUCCESSFUL

        self.image_scaling = True

        self.plugins: List[FrameProcessingPlugin] = plugins
        # Ensure plugins have a reference to this viewer for UI elements
        for plugin in self.plugins:
            plugin.viewer_parent = self

        self.init_ui()
        
        self.detect_and_populate_cameras()

    def init_ui(self):
        self.camera_selector = QComboBox()
        self.camera_selector.currentIndexChanged.connect(self.switch_source)

        self.play_pause_button = QPushButton("")  # "Run/Pause"
        self.play_pause_button.clicked.connect(self.run_pause_framegrabber)
        start_pause_icon = QIcon()
        start_pause_icon.addPixmap(QPixmap(os.path.join(script_dir, "rss\pause-button1.png")), QIcon.Normal, QIcon.Off)
        start_pause_icon.addPixmap(QPixmap(os.path.join(script_dir, "rss\start-button1.png")), QIcon.Normal, QIcon.On)
        self.play_pause_button.setIcon(start_pause_icon)
        self.play_pause_button.setIconSize(QSize(32, 32))
        self.play_pause_button.setFixedSize(QSize(36, 36))
        self.play_pause_button.setCheckable(True)
        self.play_pause_button.setChecked(True)

        self.refresh_button = QPushButton()  #"Refresh Cameras"
        refresh_button = QIcon(QIcon(os.path.join(script_dir, r"rss\reload_btn.png")))
        self.refresh_button.clicked.connect(self.detect_and_populate_cameras)
        self.refresh_button.setIcon(refresh_button)
        self.refresh_button.setIconSize(QSize(32, 32))
        self.refresh_button.setFixedSize(QSize(36, 36))

        self.settings_button = QPushButton()  # "Settings"
        self.settings_button.clicked.connect(self.open_camera_settings)
        self.settings_button.setIcon(QIcon(os.path.join(script_dir, r"rss\gear_black_full_10teeth.png")))
        self.settings_button.setIconSize(QSize(32, 32))
        self.settings_button.setFixedSize(QSize(36, 36))
        # self.settings_button.setEnabled(False)

        # Add shared memory checkbox to top layout
        self.mmf_checkbox = QCheckBox("Shared Memory")
        self.mmf_checkbox.stateChanged.connect(self.toggle_shared_memory)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and self._actual_camera_properties is not None)
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")
        self.mmf_checkbox.setFixedSize(QSize(150, 36))

        # Plugins QToolButton
        self.plugins_tool_button = QToolButton(self)
        self.plugins_tool_button.setText("Plugins") # Text on the button
        # self.plugins_tool_button.setIcon(QIcon('path/to/your/icon.png')) # Optional: use an icon
        self.plugins_tool_button.setPopupMode(QToolButton.InstantPopup) # Menu pops up instantly on click
        self.plugins_tool_button.setArrowType(Qt.DownArrow) # Adds a small down arrow to indicate a menu
        self.plugins_menu = QMenu(self) # Create the menu that will contain plugin actions
        if not self.plugins:
            self.plugins_tool_button.setEnabled(False)
            self.plugins_tool_button.setText("No Plugins") # Concise text when disabled
        else:
            for plugin in self.plugins:
                action = QAction(plugin.get_name(), self)
                # Connect the action's triggered signal to our activation slot
                action.triggered.connect(functools.partial(self._activate_selected_plugin, plugin))
                self.plugins_menu.addAction(action) # Add the action to the menu
        self.plugins_tool_button.setMenu(self.plugins_menu) # Set the created menu for the QToolButton

        # Image widget
        self.label = QLabel("No Camera Selected")
        self.label.setScaledContents(True)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        # self.scroll_area = self.label
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True) # This makes the contained widget (label)
                                                  # resize to fill the scroll area's viewport
        self.scroll_area.setWidget(self.label)

        ### LAYOUTS
        # top row layout
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.camera_selector)
        top_layout.addWidget(self.play_pause_button)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.settings_button)
        top_layout.addWidget(self.mmf_checkbox)
        top_layout.addWidget(self.plugins_tool_button)
        # Create a central widget that will hold the main layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        # Set the main layout directly on the central widget
        main_layout = QVBoxLayout(central_widget)
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.scroll_area)

        self.resize(800, 600) # Set an initial reasonable window size
        self.setWindowTitle("Camera Viewer")

    def _activate_selected_plugin(self, plugin: FrameProcessingPlugin):
        """
        Activates the selected plugin's main action.
        This method is called when an action in the plugin menu is triggered.
        """
        self.print(f"Attempting to activate plugin: {plugin.get_name()}")

        plugin_main_widget = plugin.get_ui_widget()

        if isinstance(plugin_main_widget, QPushButton):
            plugin_main_widget.click() # Programmatically click the plugin's main button
            self.print(f"Plugin '{plugin.get_name()}' activated by programmatic click.")
        else:
            QMessageBox.information(self, "Plugin Activation",
                                    f"Plugin '{plugin.get_name()}' does not have a direct activation button "
                                    f"via its get_ui_widget method. Its UI might appear differently or require direct handling.")
            self.print(f"WARNING: Plugin '{plugin.get_name()}' get_ui_widget() returned {type(plugin_main_widget)}, "
                  f"not QPushButton. Cannot simulate click.")

    def detect_and_populate_cameras(self):
        """  """
        
        self.detect_cameras()

        # populate 
        try:
            self.camera_selector.currentIndexChanged.disconnect(self.switch_source)
        except TypeError:
            pass

        self.camera_selector.clear()
        if self.available_sources:
            src_names = [src.name for src in self.available_sources]
            self.camera_selector.addItems(src_names)
            self.camera_selector.setCurrentIndex(self._current_src_index)
            self.camera_selector.currentIndexChanged.connect(self.switch_source)
            self._current_src = self.available_sources[self._current_src_index]
            self.switch_source()
        else:
            self.camera_selector.addItem("No cameras found")
            self.label.setText("No cameras found.")
            # self.settings_button.setEnabled(False)
            self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            self._current_src_index = -1
            if self.camera_thread:
                self.camera_thread.stop()
                self.camera_thread = None
            for plugin in self.plugins:
                plugin.stop_plugin()
            self.camera_selector.currentIndexChanged.connect(self.switch_source)
    
    def detect_cameras(self):
        # Detect requested sources / object of requested types and 
        # fill self.available_sources with the list of Source objects corresponding to these types
        # Add 'file' as the first available source by default
        self.available_sources = []
        for frame_grabber in self._frame_grabbers:
            # src = frame_grabber if type(frame_grabber) == Source else frame_grabber.cls()
            if type(frame_grabber) == Source:
                srcs = [frame_grabber]
            else:
                srcs = []
                temp_grabber = frame_grabber.cls()
                available_camera_ids = temp_grabber.detect_cameras()
                temp_grabber.release()
                for camera_id in available_camera_ids:
                    src = create_child_from_parent_deep(Source,
                                        frame_grabber,
                                        id = camera_id,
                                        name = f"{frame_grabber.cls_name}: {camera_id}")
                    srcs.append(src)
            self.available_sources += srcs
        detected_srcs_str = [f"{available_src.cls_name}: {available_src.id}" for available_src in self.available_sources]
        print(f"Detected sources.id = {detected_srcs_str}")
        self._current_src_index = min(self._current_src_index, len(self.available_sources)-1)

    def start_framegrabber(self):
        """Starts a new camera acquisition thread with specified or default properties."""
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait()

        if self.shared_memory_sender:
            self.shared_memory_sender.release()
            self.shared_memory_sender = None
        self.mmf_checkbox.setChecked(False)

        # Stop and re-initialize all plugins
        for plugin in self.plugins:
            plugin.stop_plugin()

        # if desired_props is None:
        #     desired_props = CameraProperties(width=640, height=480, fps=30.0, brightness=-1, offsetX=0, offsetY=0)

        self._current_src.obj = self._current_src.cls()     # self._camera_grabber -> self._current_src.obj

        self.camera_thread = FrameAcquisitionThread(self._current_src)   # desired_props
        
        self.camera_thread.frame_ready.connect(self._on_frame_ready)
        self.camera_thread.error_occurred.connect(self.handle_error)
        self.camera_thread.camera_initialized.connect(self._on_camera_initialized_and_start_display)
        self.camera_thread.start()
        self._framegrabber_initialized = True
        self.play_pause_button.setCheckable(True)

    def _on_camera_initialized_and_start_display(self, actual_props: CameraProperties):
        """Slot called when the camera acquisition thread initializes the camera."""
        self._actual_camera_properties = actual_props
        self.print(f"Frame grabber initialized with actual properties: {actual_props}")

        # self.settings_button.setEnabled(True)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and True)
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")

        # Initialize all plugins with the actual camera properties
        for plugin in self.plugins:
            plugin.init_plugin(actual_props)

    def run_pause_framegrabber(self, checked):
        try:
            if checked:
                if self.camera_thread and self.camera_thread.isRunning():
                    self.camera_thread.stop()
                    self.camera_thread.wait()
            else:
                if self._framegrabber_initialized:
                    self.camera_thread = FrameAcquisitionThread(self._current_src)   # desired_props

                    self.camera_thread.frame_ready.connect(self._on_frame_ready)
                    self.camera_thread.error_occurred.connect(self.handle_error)
                    self.camera_thread.camera_initialized.connect(self._on_camera_initialized_and_start_display)
                    self.camera_thread.start()
                else:
                    self.start_framegrabber()
        except Exception as e:
            self.print(f"run_pause_framegrabber: {e}")

    def switch_source(self):
        """Switch to the selected source based on combobox selection."""
        try:
            self._current_src_index = self.camera_selector.currentIndex()
            self._current_src = self.available_sources[self._current_src_index]
            print(f"Switching to {self._current_src.cls_name}: {self._current_src.id}")
            if self.autoplay:
                self.start_framegrabber()
            else:
                self._framegrabber_initialized = False 
            self.settings_window = None
        except Exception as e:
            self.print_error(f"{e}")

    def _on_frame_ready(self, frame_package: dict):
        """Convert frame and display in QLabel, also pass to active plugins."""
        frame = frame_package['frame']
        if self._actual_camera_properties:
            # Set 
            q_image = self.convert_cv_qt(frame)
            if self.image_scaling:
                q_image = q_image.scaled(
                  self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(QPixmap.fromImage(q_image))

            # Pass frame to all active plugins
            for plugin in self.plugins:
                plugin.process_frame(frame_package)

            if self._shared_memory_available and self.shared_memory_sender and self.shared_memory_sender.is_initialized:
                self.shared_frame_id_counter += 1
                if frame.ndim == 2:
                    frame_for_mmf = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else: 
                    frame_for_mmf = frame
                self.shared_memory_sender.write_frame(frame_for_mmf, self.shared_frame_id_counter)

    def resizeEvent(self, event):
        # This is crucial for dynamic scaling.
        # Whenever the window (and thus the label) resizes, re-scale the image.
        # frame_package = {'frame': }
        # self._on_frame_ready(frame_package)
        super().resizeEvent(event)

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
        
        for plugin in self.plugins:
            plugin.stop_plugin()
        
        if self.shared_memory_sender:
            self.shared_memory_sender.release()
            self.shared_memory_sender = None
            self.mmf_checkbox.setChecked(False)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            
        # self.settings_button.setEnabled(False)

    def open_camera_settings(self):
        try:
            if not self.settings_window or not self.settings_window.isVisible():
                self.settings_window = self.available_sources[self._current_src_index].cam_settings_wnd(
                    # self.camera_thread,
                    # self._current_src.obj,
                    # self._actual_camera_properties,
                    self._current_src,
                    parent=self
                )
                self.settings_window.settings_applied.connect(self.apply_camera_settings)
                self.settings_window.accepted.connect(self.handle_settings_window_closed)
                self.settings_window.rejected.connect(self.handle_settings_window_closed)
                self.settings_window.show()
            else:
                self.settings_window.activateWindow()
                self.settings_window.raise_()
        except Exception as e:
            self.print_error(f"{e}")
            traceback.print_exc(file=sys.stdout)

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

    def apply_camera_settings(self, updated_src: Source):
        """Applies the settings received from the settings dialog by restarting the camera."""
        self._current_src = updated_src
        self.print(f"Updating settings for the current frame source: {updated_src}")
        if self._current_src and self._current_src.obj and self._current_src.obj.is_opened():
            self.print(f"Re-opening camera: {self._current_src.cls_name}: {self._current_src.id}")
            self.start_framegrabber()
        # else:
        #     QMessageBox.warning(self, "No Active Camera", "No camera is currently active to apply settings to.")

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
        
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.wait()

        for plugin in self.plugins:
            plugin.stop_plugin()

        if self.settings_window and self.settings_window.isVisible():
            self.settings_window.close()
        
        if self.shared_memory_sender:
            self.shared_memory_sender.release()

        if self._current_src and self._current_src.obj:
            self._current_src.obj.release()

        super().closeEvent(event)
        self.print("Application closed.")

    def print(self, s: str):
        print(f"FrameGrabberManager: {s}")

    def print_error(self, s):
        print_error(f"FrameGrabberManager: {s}")


def main():
    """
    For example: python -m cameras --grabber pycapture2 --width=640 --height=640 --mode=0 --fps=90 --offsetX=500 --offsetY=500
    
    """
    args_grabbers_default = [Grabber.KNOWN_GRABBERS.OPENCV]
    parser = argparse.ArgumentParser(description="Frame Grabber Manager")
    parser.add_argument(
        "--grabbers",
        type=str,
        # choices=[Grabber.KNOWN_GRABBERS.File, Grabber.KNOWN_GRABBERS.OPENCV, Grabber.KNOWN_GRABBERS.PyCapture2],
        default=Grabber.KNOWN_GRABBERS.OPENCV,
        help=f"Choose camera grabber backend: '{Grabber.KNOWN_GRABBERS.File}, {Grabber.KNOWN_GRABBERS.OPENCV}' (default) or '{Grabber.KNOWN_GRABBERS.PyCapture2}', etc."
    )
    parser.add_argument("--cameras_to_detect", default="opencv",
        help="Specify camera types (frame grabbers) or specific cameras to look for.")
    parser.add_argument("--source_to_start", default="",
        help=f"Choose the source to start along with the desired parameters of the source")
    parser.add_argument("--config_file", default="",
        help=f"The path to the config file")
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
    parser.add_argument("--enable-gulping", action="store_true", default=False,
        help="Enable the zebrafish gulping tracking plugin.")
    
    args = parser.parse_args()
    print(f"input parameters: {args}")

    
    def extract_names_simple(text):
        text = text.strip()  # Remove leading/trailing whitespace
        if text.startswith('[') and text.endswith(']'):
            text = text[1:-1]
        names = [name.strip() for name in text.split(',')]
        return names

    ### Initialize grabbers
    args_grabbers = extract_names_simple(args.grabbers)
    print(f"args_grabbers = {args_grabbers}")
    # print(f'{args.grabber == Grabber.KNOWN_GRABBERS.PyCapture2}, {args.grabber}, {Grabber.KNOWN_GRABBERS.PyCapture2}')
    grabbers = []
    while not grabbers:
        for grabber in args_grabbers:
            if grabber == Grabber.KNOWN_GRABBERS.File:
                from .grabbers.file.file_streamer import FileStreaming
                from .grabbers.file.camera_settings_gui import SettingsWindow
                grabbers.append( Source(cls_name=Grabber.KNOWN_GRABBERS.File, cls=FileStreaming, cam_settings_wnd=SettingsWindow,
                                    # id=os.path.join(os.path.expanduser("~"), r"Downloads\output.avi"),
                                    id=os.path.join(os.path.expanduser("~"), r"Downloads\zoe_Newbreed_2025-07-26_IMG_7271.mov"),
                                    name='files',
                                    settings=CameraProperties(fps=args.fps)))
                print("Added `file` as source.")
            elif grabber == Grabber.KNOWN_GRABBERS.OPENCV:
                from .grabbers.opencv.opencv_grabber import OpenCVCapture
                from .grabbers.opencv.camera_settings_gui import SettingsWindow
                grabbers.append( Grabber(cls_name=Grabber.KNOWN_GRABBERS.OPENCV, cls=OpenCVCapture, cam_settings_wnd=SettingsWindow,
                                    settings=CameraProperties(width=args.width,
                                                            height=args.height,
                                                            fps=args.fps,
                                                            brightness=args.brightness,
                                                            offsetX=args.offsetX,
                                                            offsetY=args.offsetY)) )
                print("Added `opencv` as source.")
            elif grabber == Grabber.KNOWN_GRABBERS.PyCapture2:
                from .grabbers.pycapture2.pycapture2_grabber import PyCapture2Grabber
                from .grabbers.pycapture2.camera_settings_gui import SettingsWindow
                grabbers.append( Grabber(cls_name=Grabber.KNOWN_GRABBERS.PyCapture2, cls=PyCapture2Grabber, cam_settings_wnd=SettingsWindow,
                                settings=CameraProperties(width=args.width,
                                                            height=args.height,
                                                            fps=args.fps,
                                                            brightness=-1,
                                                            offsetX=args.offsetX,
                                                            offsetY=args.offsetY,
                                                            other={'mode':args.mode})) )
                print("Added `PyCapture2` as source.")
            elif grabber == Grabber.KNOWN_GRABBERS.PCO:
                from .grabbers.pco.pco_grabber import PCOCameraGrabber
                from .grabbers.pco.camera_settings_gui import SettingsWindow
                grabbers.append( Grabber(cls_name=Grabber.KNOWN_GRABBERS.PCO, cls=PCOCameraGrabber, cam_settings_wnd=SettingsWindow,
                                settings=CameraProperties(width=args.width,
                                                            height=args.height,
                                                            fps=args.fps,
                                                            brightness=-1,
                                                            offsetX=args.offsetX,
                                                            offsetY=args.offsetY)) )
                print("Added `PCO` as source.")
        if not grabbers:
            args_grabbers = [Grabber.KNOWN_GRABBERS.File, Grabber.KNOWN_GRABBERS.OPENCV]
            print_warning(f"No known grabbers is found in provided arguments: {args.grabbers}. Defaulting to {args_grabbers_default}")


    app = QApplication(sys.argv)

    ### Initialize plugins based on command-line arguments
    enabled_plugins: List[FrameProcessingPlugin] = []
    if args.enable_recorder:
        from .plugins.video_recorder.recorder_plugin import RecorderPlugin
        enabled_plugins.append(RecorderPlugin())
    if args.enable_gulping:
        from .plugins.tail_tracking.tail_tracking_plugin import TailTrackingPlugin
        enabled_plugins.append(TailTrackingPlugin())

    viewer = CameraViewer(grabbers, enabled_plugins)
    viewer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
