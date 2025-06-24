import sys#, os
import numpy as np
from PyQt5.QtWidgets import ( # Changed from PyQt6 to PyQt5
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, # QDialog instead of QWidget
    QLabel, QSlider, QLineEdit, QPushButton, QFormLayout, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QIntValidator, QDoubleValidator
# from opencv_camera_gui_multithreading_camera_selector import FrameAcquisitionThread
import cv2 # Still needed for CAP_PROP constants
from typing import Union

# current_script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root_dir = os.path.dirname(current_script_dir)
# sys.path.insert(0, project_root_dir)
# print(project_root_dir)
# from .. import camera_interface
from ..camera_interface import CameraGrabberInterface, CameraProperties


class SettingsWindow(QDialog): # Inherit from QDialog
    # Signal emitted when settings are applied, carrying CameraProperties object
    settings_applied = pyqtSignal(CameraProperties)

    def __init__(self, acquisition_thread_instance: Union['FrameAcquisitionThread', None],
                 grabber_instance: Union[CameraGrabberInterface, None],
                 initial_props: CameraProperties, # Added initial_props
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Settings")
        self.setGeometry(200, 200, 500, 350) # Adjusted geometry

        self._acquisition_thread = acquisition_thread_instance
        self._camera_grabber = grabber_instance
        self._initial_props = initial_props # Store initial properties

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()

        # --- Width Control ---
        self.width_input = QLineEdit()
        self.width_input.setValidator(QIntValidator(1, 4096)) # Assuming common max width
        self.width_input.editingFinished.connect(lambda: self._validate_and_update_value(self.width_input))
        form_layout.addRow("Width (pixels):", self.width_input)

        # --- Height Control ---
        self.height_input = QLineEdit()
        self.height_input.setValidator(QIntValidator(1, 4096)) # Assuming common max height
        self.height_input.editingFinished.connect(lambda: self._validate_and_update_value(self.height_input))
        form_layout.addRow("Height (pixels):", self.height_input)

        # --- FPS Control ---
        self.fps_input = QLineEdit()
        # Allow float values for FPS
        self.fps_input.setValidator(QDoubleValidator(1.0, 1000.0, 2)) # Min 1.0, Max 1000.0, 2 decimal places
        self.fps_input.editingFinished.connect(lambda: self._validate_and_update_value(self.fps_input))
        form_layout.addRow("FPS:", self.fps_input)

        # --- Brightness Control ---
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 255) # Common range for brightness
        self.brightness_slider.setTickPosition(QSlider.TicksBelow)
        self.brightness_slider.setTickInterval(25)
        self.brightness_slider.valueChanged.connect(self._update_brightness_value)

        self.brightness_value_label = QLabel("0")
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_value_label)
        form_layout.addRow("Brightness:", brightness_layout)


        main_layout.addLayout(form_layout)

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_settings)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def load_current_settings(self):
        """Loads current camera properties into the UI."""
        if self._initial_props:
            self.width_input.setText(str(self._initial_props.width))
            self.height_input.setText(str(self._initial_props.height))
            self.fps_input.setText(f"{self._initial_props.fps:.1f}") # Format to 1 decimal place

            # Brightness
            if self._initial_props.brightness != -1: # -1 indicates not set or supported
                self.brightness_slider.setValue(self._initial_props.brightness)
                self.brightness_value_label.setText(str(self._initial_props.brightness))
            else:
                self.brightness_slider.setEnabled(False) # Disable if brightness is not supported
                self.brightness_value_label.setText("N/A")
        else:
            # Set default/placeholder values if no initial props available
            self.width_input.setText("640")
            self.height_input.setText("480")
            self.fps_input.setText("30.0")
            self.brightness_slider.setValue(128)
            self.brightness_value_label.setText("128")
            self.brightness_slider.setEnabled(True) # Re-enable for manual setting if desired

    def _update_brightness_value(self, value):
        self.brightness_value_label.setText(str(value))

    def _validate_and_update_value(self, line_edit: QLineEdit):
        # This function ensures that if a user types an invalid value and tabs out,
        # it reverts to the last valid or a default, or simply keeps the old value
        # if the new one is completely unparseable.
        text = line_edit.text()
        validator = line_edit.validator()
        if isinstance(validator, QIntValidator):
            try:
                value = int(text)
                if validator.bottom() <= value <= validator.top():
                    line_edit.setText(str(value)) # Ensure it's correctly formatted
                else:
                    # Value out of range, revert to initial or a safe value
                    line_edit.setText(str(self._initial_props.width if line_edit == self.width_input else \
                                        self._initial_props.height if line_edit == self.height_input else 0))
            except ValueError:
                # Invalid input, revert to initial or a safe value
                 line_edit.setText(str(self._initial_props.width if line_edit == self.width_input else \
                                        self._initial_props.height if line_edit == self.height_input else 0))
        elif isinstance(validator, QDoubleValidator):
            try:
                value = float(text)
                if validator.bottom() <= value <= validator.top():
                    line_edit.setText(f"{value:.1f}") # Format to 1 decimal place
                else:
                    line_edit.setText(f"{self._initial_props.fps:.1f}" if line_edit == self.fps_input else "30.0")
            except ValueError:
                line_edit.setText(f"{self._initial_props.fps:.1f}" if line_edit == self.fps_input else "30.0")


    def apply_settings(self):
        """Collects settings from UI and emits them."""
        try:
            new_width = int(self.width_input.text())
            new_height = int(self.height_input.text())
            new_offsetX = 0,
            new_offsetY = 0,
            new_fps = float(self.fps_input.text())
            new_brightness = self.brightness_slider.value() if self.brightness_slider.isEnabled() else -1

            new_props = CameraProperties(
                width=new_width,
                height=new_height,
                offsetX = new_offsetX,
                offsetY = new_offsetY,
                fps=new_fps,
                brightness=new_brightness
            )
            self.settings_applied.emit(new_props)
            self.accept() # Close dialog with accepted result
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Please enter valid numeric values for all settings: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error Applying Settings", f"An unexpected error occurred: {e}")

    def cancel_settings(self):
        """Closes the dialog without applying settings."""
        self.reject() # Close dialog with rejected result


# --- Example Usage (for testing camera_settings_gui.py in isolation) ---
if __name__ == '__main__':
    # Mock implementations for testing purposes
    class MockCameraGrabber(CameraGrabberInterface):
        def __init__(self):
            self._is_open = False
            self._props = CameraProperties(640, 480, 0, 0, 30.0, 100) # Initial mock properties

        def open(self, camera_index: int, desired_props: CameraProperties) -> CameraProperties:
            print(f"MockGrabber: Opening with desired: {desired_props}")
            # Simulate setting some properties
            if desired_props.width > 0: self._props.width = desired_props.width
            if desired_props.height > 0: self._props.height = desired_props.height
            if desired_props.fps > 0: self._props.fps = desired_props.fps
            if desired_props.brightness != -1: self._props.brightness = desired_props.brightness
            self._is_open = True
            print(f"MockGrabber: Opened with actual: {self._props}")
            return self._props

        def get_frame(self) -> Union[np.ndarray, None]:
            if not self._is_open: return None
            # Return a dummy frame
            return np.zeros((self._props.height, self._props.width, 3), dtype=np.uint8)

        def get_property(self, prop_id: int) -> Union[float, None]:
            if prop_id == cv2.CAP_PROP_FRAME_WIDTH: return float(self._props.width)
            if prop_id == cv2.CAP_PROP_FRAME_HEIGHT: return float(self._props.height)
            if prop_id == cv2.CAP_PROP_FPS: return self._props.fps
            if prop_id == cv2.CAP_PROP_BRIGHTNESS: return float(self._props.brightness)
            return -1.0 # Indicate not found/supported

        def set_property(self, prop_id: int, value: float) -> bool:
            if prop_id == cv2.CAP_PROP_FRAME_WIDTH: self._props.width = int(value)
            if prop_id == cv2.CAP_PROP_FRAME_HEIGHT: self._props.height = int(value)
            if prop_id == cv2.CAP_PROP_FPS: self._props.fps = float(value)
            if prop_id == cv2.CAP_PROP_BRIGHTNESS: self._props.brightness = int(value)
            print(f"MockGrabber: Set prop {prop_id} to {value}")
            return True

        def release(self): self._is_open = False
        def is_opened(self): return self._is_open
        def detect_cameras(self): return ["Mock Camera 0"]

    class MockFrameAcquisitionThread(QThread):
        camera_initialized = pyqtSignal(CameraProperties)
        frame_ready = pyqtSignal(np.ndarray)
        error_occurred = pyqtSignal(str)

        def __init__(self, grabber_instance: CameraGrabberInterface, camera_index: int, desired_props: CameraProperties):
            super().__init__()
            self._grabber = grabber_instance
            self._camera_index = camera_index
            self._desired_props = desired_props
            self._running = True

        def run(self):
            actual_props = self._grabber.open(self._camera_index, self._desired_props)
            self.camera_initialized.emit(actual_props)
            while self._running:
                frame = self._grabber.get_frame()
                if frame is not None:
                    self.frame_ready.emit(frame)
                self.msleep(100) # Simulate frame rate
        def stop(self):
            self._running = False
            self.quit()
            self.wait()


    app = QApplication(sys.argv)

    mock_grabber = MockCameraGrabber()
    initial_camera_props = mock_grabber.open(0, CameraProperties(640, 480, 0, 0, 30.0, 150)) # Simulate opening a camera
    mock_acquisition_thread = MockFrameAcquisitionThread(mock_grabber, 0, initial_camera_props)


    def on_settings_applied(new_props: CameraProperties):
        print(f"Settings Applied: {new_props}")
        # In a real app, you would restart the camera with these new_props
        # mock_acquisition_thread.stop()
        # new_thread = MockFrameAcquisitionThread(mock_grabber, 0, new_props)
        # new_thread.start()

    def on_settings_window_closed():
        print("Settings window closed.")


    settings_window = SettingsWindow(
        acquisition_thread_instance=mock_acquisition_thread,
        grabber_instance=mock_grabber,
        initial_props=initial_camera_props, # Pass the initial properties
    )
    settings_window.settings_applied.connect(on_settings_applied)
    settings_window.accepted.connect(on_settings_window_closed) # Connect accepted signal
    settings_window.rejected.connect(on_settings_window_closed) # Connect rejected signal


    settings_window.show()
    sys.exit(app.exec_())