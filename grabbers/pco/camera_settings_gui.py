import sys
import numpy as np
from PyQt5.QtWidgets import ( 
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QLineEdit, QPushButton, QFormLayout, QMessageBox, QGridLayout, QSpinBox, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from typing import Union

try:
    from ..camera_interface import CameraProperties, Source
except ValueError:
    import os
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_script_dir)
    sys.path.insert(0, project_root_dir) 
    from camera_interface import CameraProperties, Source

possible_values = {
    # 'min width': cam_description['min width'],
    # 'max width': cam_description['max width'],
    # 'min height': cam_description['min height'],
    # 'max height': cam_description['max height'],
    # 'min exposure time': cam_description['min exposure time'],
    # 'max exposure time': cam_description['max exposure time'],
    'trigger_modes': ['auto sequence', 'software trigger', 'external exposure start & software trigger', 'external exposure control', 
                      'external synchronized', 'fast external exposure control', 'external CDS control', 'slow external exposure control',
                      'external synchronized HDSDI'],
    'set_maximum_fps': ['on', 'off'],   # set the image timing of the camera so that the maximum frame rate and the maximum exposure time for this frame rate is achieved. The maximum image frame rate (FPS = frames per second) depends on the pixel rate and the image area selection.
    'acquire_mode' : ['auto', 'external', 'external modulated'],     # the acquire mode of the camera. Acquire mode can be either [auto], [external] or [external modulate].
    # 'binning' : cam_description['binning horz vec'], 
}
controls_tooltip = {
    'set_maximum_fps': 'set the image timing of the camera so that the maximum frame rate and the maximum exposure time for this frame rate is achieved. The maximum image frame rate (FPS = frames per second) depends on the pixel rate and the image area selection.',
    'acquire_mode': 'the acquire mode of the camera. Acquire mode can be either [auto], [external] or [external modulate].'
}


class SettingsWindow(QDialog): # Inherit from QDialog
    # Signal emitted when settings are applied, carrying CameraProperties object
    settings_applied = pyqtSignal(Source)

    def __init__(self, src: Source, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Settings")
        self.setGeometry(200, 200, 500, 350) # Adjusted geometry

        self.src = src
        self.parameter_constraints = self.src.settings.other['parameter_constraints']

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        grid_layout = QGridLayout()
        
        # Row 0: Titles for the two groups of fields
        grid_layout.addWidget(QLabel("<b>Top-Left Corner</b>"), 0, 0, 1, 2)
        grid_layout.addWidget(QLabel("<b>Dimensions</b>"), 0, 2, 1, 2)
        
        # Row 1: X and Width inputs
        grid_layout.addWidget(QLabel("X:"), 1, 0)
        self.x_spinbox = self.create_spinbox()
        grid_layout.addWidget(self.x_spinbox, 1, 1)

        grid_layout.addWidget(QLabel("Width:"), 1, 2)
        self.width_spinbox = self.create_spinbox(min_val=self.parameter_constraints['min width'], max_val=self.parameter_constraints['max width'])
        grid_layout.addWidget(self.width_spinbox, 1, 3)

        # Row 2: Y and Height inputs
        grid_layout.addWidget(QLabel("Y:"), 2, 0)
        self.y_spinbox = self.create_spinbox()
        grid_layout.addWidget(self.y_spinbox, 2, 1)

        grid_layout.addWidget(QLabel("Height:"), 2, 2)
        self.height_spinbox = self.create_spinbox(min_val=1)
        grid_layout.addWidget(self.height_spinbox, 2, 3)


        # --- Width Control ---
        self.width_input = QLineEdit()
        self.width_input.setValidator(QIntValidator(1, 4096)) # Assuming common max width
        self.width_input.editingFinished.connect(lambda: self._validate_and_update_value(self.width_input))

        # --- Height Control ---
        self.height_input = QLineEdit()
        self.height_input.setValidator(QIntValidator(1, 4096)) # Assuming common max height
        self.height_input.editingFinished.connect(lambda: self._validate_and_update_value(self.height_input))

        # --- FPS Control ---
        self.fps_input = QLineEdit()
        # Allow float values for FPS
        self.fps_input.setValidator(QDoubleValidator(1.0, 1000.0, 2)) # Min 1.0, Max 1000.0, 2 decimal places
        self.fps_input.editingFinished.connect(lambda: self._validate_and_update_value(self.fps_input))

        # --- Brightness Control ---
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 255) # Common range for brightness
        self.brightness_slider.setTickPosition(QSlider.TicksBelow)
        self.brightness_slider.setTickInterval(25)
        self.brightness_slider.valueChanged.connect(self._update_brightness_value)

        # --- Trigger modes ---
        self.trigger_modes = QComboBox()
        for trigger_mode in possible_values['trigger_modes']:
            self.trigger_modes.addItem(trigger_mode)

        # --- Acquire modes ---
        self.acquire_modes = QComboBox()
        for acquire_mode in possible_values['acquire_mode']:
            self.acquire_modes.addItem(acquire_mode)

        # --- set_maximum_fps ---
        self.set_at_maximum_fps = QCheckBox()

        self.brightness_value_label = QLabel("0")
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_value_label)

        form_layout = QFormLayout()
        # form_layout.addRow("Width (pixels):", self.width_input)
        # form_layout.addRow("Height (pixels):", self.height_input)
        form_layout.addRow("Trigger modes:", self.trigger_modes)
        form_layout.addRow("Acquire modes:", self.acquire_modes)
        form_layout.addRow("Set at maximum FPS:", self.set_at_maximum_fps)
        form_layout.addRow("FPS:", self.fps_input)
        form_layout.addRow("Brightness:", brightness_layout)

        # --- Action Buttons ---
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_settings)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(grid_layout)
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def create_spinbox(self, min_val=0, max_val=100000):
        min_val = 0 if min_val is None else min_val
        max_val = 0 if max_val is None else max_val
        spinbox = QSpinBox(self)
        spinbox.setRange(min_val, max_val)
        return spinbox

    def load_current_settings(self):
        """Loads current camera properties into the UI."""
        if self.src:
            self.width_input.setText(str(self.src.settings.width))
            self.height_input.setText(str(self.src.settings.height))
            self.fps_input.setText(f"{self.src.settings.fps:.1f}") # Format to 1 decimal place

            # Brightness
            if self.src.settings.brightness != -1: # -1 indicates not set or supported
                self.brightness_slider.setValue(self.src.settings.brightness)
                self.brightness_value_label.setText(str(self.src.settings.brightness))
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
                    line_edit.setText(str(self.src.settings.width if line_edit == self.width_input else \
                                        self.src.settings.height if line_edit == self.height_input else 0))
            except ValueError:
                # Invalid input, revert to initial or a safe value
                 line_edit.setText(str(self.src.settings.width if line_edit == self.width_input else \
                                        self.src.settings.height if line_edit == self.height_input else 0))
        elif isinstance(validator, QDoubleValidator):
            try:
                value = float(text)
                if validator.bottom() <= value <= validator.top():
                    line_edit.setText(f"{value:.1f}") # Format to 1 decimal place
                else:
                    line_edit.setText(f"{self.src.settings.fps:.1f}" if line_edit == self.fps_input else "30.0")
            except ValueError:
                line_edit.setText(f"{self.src.settings.fps:.1f}" if line_edit == self.fps_input else "30.0")


    def apply_settings(self):
        """Collects settings from UI and emits them."""
        try:
            new_width = int(self.width_input.text())
            new_height = int(self.height_input.text())
            new_offsetX = 0,
            new_offsetY = 0,
            new_fps = float(self.fps_input.text())
            new_brightness = self.brightness_slider.value() if self.brightness_slider.isEnabled() else -1

            self.src.settings = CameraProperties(
                width=new_width,
                height=new_height,
                offsetX = new_offsetX,
                offsetY = new_offsetY,
                fps=new_fps,
                brightness=new_brightness
            )
            self.settings_applied.emit(self.src)
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
    app = QApplication(sys.argv)
    settings_window = SettingsWindow(Source())
    settings_window.show()
    sys.exit(app.exec_())
