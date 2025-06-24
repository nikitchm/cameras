import sys
import cv2
import numpy as np
import argparse
import dataclasses
from enum import Enum
import traceback

from PyQt5.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, QComboBox,
    QPushButton, QHBoxLayout, QMessageBox, QDialog, QCheckBox, QMainWindow, QGroupBox # QMainWindow for the main app window
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QObject
from PyQt5 import QtCore # This import is often used for specific Qt Enums like Qt.AlignCenter

from typing import Union, Type

# Custom modules (ensure these files are in the same directory or accessible via PYTHONPATH)
from grabbers.camera_interface import CameraGrabberInterface, CameraProperties
from recording_thread import RecordingThread
from video_recorder_gui import RecorderWindow # This is the QDialog for recording

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
    cls: CameraGrabberInterface
    cam_settings_wnd: QDialog
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
class CameraViewer(QWidget): # Renamed from RecorderWindow, and now QWidget for simplicity
    def __init__(self, grabber: Type[Grabber], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.available_cameras = []
        self._current_camera_index = -1
        self._grabber = grabber
        self._camera_grabber: Union[CameraGrabberInterface, None] = None
        self.camera_thread: Union[FrameAcquisitionThread, None] = None
        self._actual_camera_properties: Union[CameraProperties, None] = None # Stores properties from the opened camera

        self.recording_thread = RecordingThread()
        self.recording_thread.error_occurred.connect(self.handle_error) # Connect recording thread errors
        
        self.recorder_window = RecorderWindow(self.recording_thread)
        self.recorder_window.close_signal.connect(self.handle_recorder_window_closed)
        self.recording_thread.recording_status_changed.connect(self.recorder_window.update_button_states)

        self.settings_window: Union[QDialog, None] = None

        self.shared_memory_sender: Union[SharedMemoryFrameSender, None] = None
        self.shared_frame_id_counter = 0
        self._shared_memory_available = _SHARED_MEMORY_IMPORTS_SUCCESSFUL

        self.init_ui()
        self.detect_and_populate_cameras()

    def init_ui(self):
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

        self.record_button = QPushButton("Record Video")
        self.record_button.clicked.connect(self.open_recorder_window)
        self.record_button.setEnabled(False) # Initially disabled
        top_layout.addWidget(self.record_button)

        self.mmf_checkbox = QCheckBox("Enable Shared Memory")
        self.mmf_checkbox.stateChanged.connect(self.toggle_shared_memory)
        # Enable only if shared memory is available and camera properties are known
        self.mmf_checkbox.setEnabled(self._shared_memory_available and self._actual_camera_properties is not None) 
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")
        top_layout.addWidget(self.mmf_checkbox)


        main_layout.addLayout(top_layout)

        self.label = QLabel("No Camera Selected")
        self.label.setAlignment(QtCore.Qt.AlignCenter) # Align text to center
        main_layout.addWidget(self.label)

        self.setLayout(main_layout)

    def detect_and_populate_cameras(self):
        temp_grabber = self._grabber.cls() 

        self.available_cameras = temp_grabber.detect_cameras()
        temp_grabber.release() # Release the temporary grabber

        try:
            self.camera_selector.currentIndexChanged.disconnect(self.switch_camera) 
        except TypeError: # Disconnect if already connected, ignore if not
            pass
            
        self.camera_selector.clear()
        
        if self.available_cameras:
            self.camera_selector.addItems(self.available_cameras)
            
            initial_selection_made = False
            if self._current_camera_index != -1: # Try to re-select previously active camera
                if self._grabber.name == Grabber.KNOWN_GRABBERS.OPENCV:
                     if f"Camera {self._current_camera_index}" in self.available_cameras:
                         self.camera_selector.setCurrentText(f"Camera {self._current_camera_index}")
                         initial_selection_made = True
                elif self._grabber.name == Grabber.KNOWN_GRABBERS.PyCapture2:
                     if self._current_camera_index < self.camera_selector.count():
                         self.camera_selector.setCurrentIndex(self._current_camera_index)
                         initial_selection_made = True

            if not initial_selection_made and self.camera_selector.count() > 0:
                self.camera_selector.setCurrentIndex(0) # Select the first camera if no previous selection or it's gone
                initial_selection_made = True 

            self.camera_selector.currentIndexChanged.connect(self.switch_camera) # Reconnect signal
            
            if initial_selection_made:
                self.switch_camera() # Trigger camera switch with the selected item
            else:
                # If no camera could be selected or re-selected, disable related buttons
                self.settings_button.setEnabled(False)
                self.record_button.setEnabled(False)
                self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
                self._current_camera_index = -1
                if self.camera_thread: # Stop any running thread if camera selection is lost
                    self.camera_thread.stop()
                    self.camera_thread = None

        else: # No cameras found
            self.camera_selector.addItem("No cameras found")
            self.label.setText("No cameras found.")
            self.settings_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            self._current_camera_index = -1
            if self.camera_thread:
                self.camera_thread.stop()
                self.camera_thread = None
            self.camera_selector.currentIndexChanged.connect(self.switch_camera) # Still connect, but it will do nothing

    def start_camera(self, camera_index: int, desired_props: CameraProperties = None):
        """Starts a new camera acquisition thread with specified or default properties."""
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop() # Stop existing thread before starting a new one
            self.camera_thread.wait() # Wait for the thread to properly finish

        # Release shared memory if active, as camera properties might change
        if self.shared_memory_sender:
            self.shared_memory_sender.release()
            self.shared_memory_sender = None
        self.mmf_checkbox.setChecked(False) # Uncheck shared memory box

        self._current_camera_index = camera_index
        # Create a new grabber instance for the new thread
        self._camera_grabber = self._grabber.cls() 

        if desired_props is None:
            desired_props = CameraProperties(width=640, height=480, fps=30.0, brightness=-1, offsetX=0, offsetY=0) # Default properties

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
        self._actual_camera_properties = actual_props # Store the actual properties
        print(f"CameraViewer: Camera initialized with actual properties: {actual_props}")
        # Enable buttons related to camera operations
        self.settings_button.setEnabled(True)
        self.record_button.setEnabled(True)
        self.mmf_checkbox.setEnabled(self._shared_memory_available and True) # Enable MMF if available and camera is active
        if not self._shared_memory_available:
            self.mmf_checkbox.setToolTip("Shared Memory functionality is unavailable due to missing pywin32 modules.")

        # Update recording thread properties
        self.recording_thread.set_video_properties(
            actual_props.width,
            actual_props.height,
            actual_props.fps
        )
        # Update recorder window buttons based on new recording thread state
        self.recorder_window.update_button_states(self.recording_thread.is_recording(), self.recording_thread.is_paused()) 

    def switch_camera(self):
        """Switch to the selected camera based on combobox selection."""
        selected_camera_text = self.camera_selector.currentText()
        if selected_camera_text and "No cameras found" not in selected_camera_text:
            camera_index = -1
            if self._grabber.name == Grabber.KNOWN_GRABBERS.OPENCV:
                try:
                    camera_index = int(selected_camera_text.split()[-1]) # Extract index for OpenCV
                except (ValueError, IndexError):
                    print(f"Error: Could not parse OpenCV camera index from '{selected_camera_text}'.")
                    QMessageBox.warning(self, "Camera Selection Error", 
                                        f"Could not determine camera index from '{selected_camera_text}'. Please select a valid camera.")
                    return
            elif self._grabber.name == Grabber.KNOWN_GRABBERS.PyCapture2:
                camera_index = self.camera_selector.currentIndex()
                if camera_index == -1: # Should not happen if "No cameras found" is handled
                    QMessageBox.warning(self, "Camera Selection Error", 
                                        f"Could not determine camera index for '{selected_camera_text}'. Please select a valid camera.")
                    return

            if self._current_camera_index == camera_index and self.camera_thread and self.camera_thread.isRunning():
                print(f"Camera {camera_index} is already active and running.")
                return # Do nothing if same camera is already running

            self.start_camera(camera_index, desired_props=self._grabber.settings) # Start the selected camera
        else:
            # If no valid camera selected, disable related buttons and stop threads
            self.settings_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.mmf_checkbox.setEnabled(self._shared_memory_available and False)
            self._current_camera_index = -1
            if self.camera_thread:
                self.camera_thread.stop()
                self.camera_thread = None

    def _on_frame_ready(self, frame: np.ndarray):
        """Convert frame and display in QLabel, also pass to recorder if active."""
        if self._actual_camera_properties: # Ensure properties are available
            q_image = self.convert_cv_qt(frame)
            self.label.setPixmap(QPixmap.fromImage(q_image))

            if self.recording_thread.is_recording_active():
                self.recording_thread.enqueue_frame(frame)

            if self._shared_memory_available and self.shared_memory_sender and self.shared_memory_sender.is_initialized:
                self.shared_frame_id_counter += 1
                if frame.ndim == 2: # Convert grayscale to BGR for MMF if needed
                    frame_for_mmf = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                else: 
                    frame_for_mmf = frame
                self.shared_memory_sender.write_frame(frame_for_mmf, self.shared_frame_id_counter)

    def convert_cv_qt(self, cv_img: np.ndarray) -> QImage:
        """Converts an OpenCV image (numpy array) to a QImage."""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        # Using Format_RGB888 for this specific PyQt5 environment
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

    def handle_error(self, error_message: str):
        """Handle camera or recording errors."""
        QMessageBox.critical(self, "Error", error_message)
        self.label.setText(f"Error: {error_message}")
        
        # Stop threads and release resources on error
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None # Clear reference
        if self.recording_thread:
            self.recording_thread.stop_recording()
            self.recording_thread = None # Clear reference
        
        if self.shared_memory_sender:
            self.shared_memory_sender.release()
            self.shared_memory_sender = None
            self.mmf_checkbox.setChecked(False) # Uncheck on error
        self.mmf_checkbox.setEnabled(self._shared_memory_available and False) # Disable MMF
            
        # Disable buttons
        self.settings_button.setEnabled(False)
        self.record_button.setEnabled(False)
        # Update recorder window buttons
        self.recorder_window.update_button_states(False, False)

    def open_camera_settings(self):
        if not self.settings_window or not self.settings_window.isVisible():
            # Correctly pass the actual camera properties to the settings window
            self.settings_window = self._grabber.cam_settings_wnd(
                self.camera_thread,
                self._camera_grabber,
                self._actual_camera_properties, # Pass the stored CameraProperties object
                parent=self
            )
            # Connect signals from settings window
            self.settings_window.settings_applied.connect(self.apply_camera_settings)
            self.settings_window.accepted.connect(self.handle_settings_window_closed) # Using accepted signal
            self.settings_window.rejected.connect(self.handle_settings_window_closed) # Using rejected signal
            self.settings_window.show()
        else:
            self.settings_window.activateWindow()
            self.settings_window.raise_()
            # If the settings window is already open, update its internal thread/grabber if needed
            # This logic assumes SettingsWindow has a method to update these instances
            # self.settings_window.update_acquisition_thread_instance(self.camera_thread) # Removed as per previous fixes

    def handle_settings_window_closed(self):
        """Slot to handle the settings window closing."""
        if self.settings_window:
            try:
                self.settings_window.settings_applied.disconnect(self.apply_camera_settings)
            except TypeError: # Signal might already be disconnected
                pass
            try:
                self.settings_window.accepted.disconnect(self.handle_settings_window_closed)
            except TypeError:
                pass
            try:
                self.settings_window.rejected.disconnect(self.handle_settings_window_closed)
            except TypeError:
                pass
            self.settings_window = None # Clear reference

    def apply_camera_settings(self, settings_props: CameraProperties):
        """Applies the settings received from the settings dialog by restarting the camera."""
        if self._camera_grabber and self._camera_grabber.is_opened():
            print(f"Applying new settings and re-opening camera: {settings_props}") 
            # Restart the camera with the new properties
            # self.stop_camera()
            self.start_camera(self._current_camera_index, settings_props)
        else:
            QMessageBox.warning(self, "No Active Camera", "No camera is currently active to apply settings to.")

    def open_recorder_window(self):
        """Opens the video recorder dialog."""
        if self.recording_thread and self._actual_camera_properties:
            if self.recorder_window is None:
                # RecorderWindow (from video_recorder_gui.py) is a QDialog
                self.recorder_window = RecorderWindow(self.recording_thread, parent=self)
                self.recorder_window.close_signal.connect(self.handle_recorder_window_closed)
            self.recorder_window.show() # Show non-modally
            self.recorder_window.activateWindow() # Bring to front
            self.recorder_window.raise_()
        else:
            QMessageBox.information(self, "Information", "Please open a camera first to enable recording.")

    def handle_recorder_window_closed(self):
        """Slot to handle the recorder window closing."""
        # Update button states in main window after recorder window closes
        if self.recording_thread:
            self.recorder_window.update_button_states(self.recording_thread.is_recording(), self.recording_thread.is_paused()) 
        self.recorder_window = None # Clear reference when closed

    def toggle_shared_memory(self, state):
        """Handles enabling/disabling shared memory."""
        if not self._shared_memory_available:
            self.mmf_checkbox.setChecked(False) # Ensure it's unchecked if not available
            QMessageBox.warning(self, "Shared Memory Unavailable", "Shared Memory functionality is disabled due to an import error with pywin32 modules.")
            return

        if state == QtCore.Qt.Checked:
            if self._actual_camera_properties:
                width = self._actual_camera_properties.width
                height = self._actual_camera_properties.height
                # Calculate buffer size for 3 channels (BGR)
                buffer_size = width * height * 3 
                
                if self.shared_memory_sender: # Release existing if any
                    self.shared_memory_sender.release()

                try:
                    self.shared_memory_sender = SharedMemoryFrameSender(
                        name=SHARED_MEM_NAME,
                        mutex_name=SHARED_MUTEX_NAME,
                        max_buffer_size=buffer_size
                    )
                    if not self.shared_memory_sender.is_initialized:
                        QMessageBox.warning(self, "Shared Memory Error", "Failed to initialize Shared Memory. See console for details.")
                        self.mmf_checkbox.setChecked(False) # Uncheck if initialization fails
                except Exception as e:
                    QMessageBox.critical(self, "Shared Memory Fatal Error", f"An unexpected error occurred during Shared Memory setup: {e}\nShared memory will be disabled.")
                    self.shared_memory_sender = None
                    self.mmf_checkbox.setChecked(False) # Uncheck on fatal error
                    self.mmf_checkbox.setEnabled(False) # Disable checkbox permanently
                    self._shared_memory_available = False # Mark as unavailable
            else:
                QMessageBox.warning(self, "Shared Memory", "Camera not active. Cannot enable shared memory.")
                self.mmf_checkbox.setChecked(False) # Uncheck if camera not active
        else: # Unchecked state
            if self.shared_memory_sender:
                self.shared_memory_sender.release()
                self.shared_memory_sender = None
                self.shared_frame_id_counter = 0 # Reset frame counter

    def update_button_states(self):
        """Updates the enabled state of various buttons based on camera status."""
        is_camera_open = self._camera_grabber and self._camera_grabber.is_opened()

        self.open_button.setEnabled(not is_camera_open and self.camera_selector.currentIndex() != -1 and self.available_cameras)
        self.close_button.setEnabled(is_camera_open)
        self.settings_button.setEnabled(is_camera_open and self._actual_camera_properties is not None) # Settings require open camera and known properties
        self.record_button.setEnabled(is_camera_open and self._actual_camera_properties is not None) # Recorder requires open camera and known properties

        self.mmf_checkbox.setEnabled(self._shared_memory_available and is_camera_open and self._actual_camera_properties is not None)

    def handle_camera_error(self, error_message: str):
        """Handles errors reported by the camera acquisition thread."""
        QMessageBox.critical(self, "Camera Error", error_message)
        self.close_camera() # Attempt to close and clean up camera resources

    def closeEvent(self, event):
        """Handles the main window closing event, ensuring all threads and resources are stopped."""
        print("Closing application. Stopping threads...")
        
        # Stop camera acquisition thread
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread.wait() # Wait for the thread to terminate

        # Stop recording thread
        if self.recording_thread: 
            self.recording_thread.stop_recording()

        # Close any open child dialogs
        if self.settings_window and self.settings_window.isVisible():
            self.settings_window.close()

        if self.recorder_window and self.recorder_window.isVisible():
            self.recorder_window.close()
        
        # Release shared memory resources
        if self.shared_memory_sender:
            self.shared_memory_sender.release()

        # Release camera grabber
        if self._camera_grabber:
            self._camera_grabber.release()

        super().closeEvent(event)
        print("Application closed.")


if __name__ == '__main__':
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
    args = parser.parse_args()

    print(args)

    print(f'{args.grabber == Grabber.KNOWN_GRABBERS.PyCapture2}, {args.grabber}, {Grabber.KNOWN_GRABBERS.PyCapture2}')
    if args.grabber == Grabber.KNOWN_GRABBERS.PyCapture2:
        from grabbers.pycapture2.pycapture2_grabber import PyCapture2Grabber
        from grabbers.pycapture2.camera_settings_gui import SettingsWindow
        grabber = Grabber(name=Grabber.KNOWN_GRABBERS.PyCapture2, cls=PyCapture2Grabber, cam_settings_wnd=SettingsWindow,
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
        from grabbers.opencv.opencv_grabber import OpenCVCapture
        from grabbers.opencv.camera_settings_gui import SettingsWindow
        grabber = Grabber(name=Grabber.KNOWN_GRABBERS.OPENCV, cls=OpenCVCapture, cam_settings_wnd=SettingsWindow,
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
    viewer = CameraViewer(grabber)
    viewer.show()
    sys.exit(app.exec_())