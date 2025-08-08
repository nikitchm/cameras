# --- camera_grabber_pco.py ---
# This file provides a concrete implementation of the CameraGrabberInterface
# for PCO cameras using the 'pco' Python package.

import pco
import numpy as np
from datetime import datetime
import time
from typing import List, Union, Dict
import traceback
import sys
import time

# Assuming the user's camera_interface.py file is accessible
from ..camera_interface import CameraGrabberInterface, Source, CameraProperties, Grabber

# A dummy settings window class for demonstration purposes
class PcoSettingsWindow:
    def show(self):
        print("Showing PCO Camera settings window...")

class PCOCameraGrabber(CameraGrabberInterface):
    """
    PCO camera grabber implementation using the pco Python package.
    """
    def __init__(self):
        super().__init__()
        self._cam = None
        self._is_opened = False
        self._buffer_size = 10  # Default ring buffer size
        self._default_exposure_time = 0.01

    def detect_cameras(self) -> List[str]:
        """
        Detects available PCO cameras by attempting to open one.
        The pco package defaults to the first available camera.
        """
        try:
            with pco.Camera() as cam:
                serial_number = cam.description['serial']
            return [serial_number]
        except Exception as e:
            print(f"Error detecting PCO cameras: {e}")
            return []

    def open(self, src: Source) -> Source:
        """
        Opens the PCO camera and sets up the ring buffer.
        """
        try:
            # The pco.Camera() constructor is called without a camera_id.
            self._cam = pco.Camera()
            self._cam_description = self._cam.description

            if self._cam:
                # Corrected: Call set-_trigger_mode on the 'rec' attribute
                # self._cam.sdk.set_camera_synch_mode('master')
                
                # Corrected: Set exposure_time directly on the Camera object
                self._cam.exposure_time = src.settings.other.get('exposure_time', self._default_exposure_time)

                # Set up the ring buffer for acquisition.
                self._cam.record(number_of_images=self._buffer_size, mode='ring buffer')
                # self._cam.record(4, mode='ring buffer')
                self._rec_settings = self._cam.rec.get_settings()
                self._is_opened = True

                # Get the actual camera properties after opening.
                self._actual_camera_properties = CameraProperties(
                    width=self._rec_settings['width'],
                    height=self._rec_settings['height'],
                    fps=0, # Corrected: fps is a property of the 'rec' attribute
                    brightness=src.settings.brightness,
                    other=src.settings.other
                )
                src.settings = self._actual_camera_properties
                time.sleep(1)
                print(f"Successfully opened PCO camera: {src.name}")
                return src
        except Exception as e:
            print(f"Failed to open PCO camera: {e}")
            traceback.print_exc(file=sys.stdout)
            self._is_opened = False
            self.release()
            return src

    def is_opened(self) -> bool:
        """Returns True if the camera is currently opened."""
        return self._is_opened and self._cam is not None

    def get_frame(self) -> Union[None, Dict[str, Union[np.ndarray, datetime]]]:
        """
        Grabs the next frame from the ring buffer.
        """
        if not self.is_opened():
            return None

        try:
            # We use the image() method to get the next image from the ring buffer.
            # 0xFFFFFFFF for image_number is used to grab the latest image
            # from the recorder buffer.
            # image_array, meta = self._cam.image(image_index=0xFFFFFFFF)
            image_array, meta = self._cam.image()
            # print(meta)
            
            # The metadata returned contains a timestamp.
            try:
                timestamp = datetime.fromtimestamp(meta['timestamp'])
            except KeyError as e:
                # print(e)
                print(meta)
                timestamp = time.time()

            return {'frame': image_array, 'timestamp': timestamp}
        except Exception as e:
            print(f"Error getting frame from ring buffer: {e}")
            traceback.print_exc()
            return None

    def release(self):
        """Releases the camera and its resources."""
        if self._cam:
            try:
                # The pco.Camera class has a stop() and close() method.
                self._cam.stop()
                self._cam.close()
                self._cam = None
            except Exception as e:
                print(f"Error releasing PCO camera: {e}")
        self._is_opened = False

    def get_property(self, prop_id: Union[int, str]) -> Union[float, int, None]:
        """Gets a camera property."""
        if not self.is_opened():
            return None
        
        try:
            if prop_id == 'exposure_time':
                return self._cam.exposure_time
            if prop_id == 'fps':
                return self._cam.rec.fps
            return None
        except Exception as e:
            print(f"Error getting property {prop_id}: {e}")
            return None

    def set_property(self, prop_id: Union[int, str], value: Union[float, int]) -> bool:
        """Sets a camera property."""
        if not self.is_opened():
            return False

        try:
            if prop_id == 'exposure_time':
                self._cam.exposure_time = value
                return True
            if prop_id == 'fps':
                self._cam.rec.fps = value # This is likely a read-only property, so setting it may fail.
                return True
            return False
        except Exception as e:
            print(f"Error setting property {prop_id} to {value}: {e}")
            return False

# Register the PCO grabber with the main grabber list
def register_pco_grabber():
    grabber_entry = Grabber(
        cls=PcoCameraGrabber,
        cls_name=Grabber.KNOWN_GRABBERS.PCO,
        cam_settings_wnd=PcoSettingsWindow
    )
    print("PCO camera grabber registered.")
    return grabber_entry

if __name__ == '__main__':
    # Example usage (for testing purposes)
    register_pco_grabber()
    
    pco_grabber = PcoCameraGrabber()
    cameras = pco_grabber.detect_cameras()
    print(f"Detected cameras: {cameras}")
    
    if cameras:
        source_obj = Source(
            cls=PcoCameraGrabber,
            cls_name=Grabber.KNOWN_GRABBERS.PCO,
            id=0,
            name=cameras[0],
            settings=CameraProperties(other={'exposure_time': 0.05})
        )
        pco_grabber.open(source_obj)
        if pco_grabber.is_opened():
            print("Camera is open.")
            pco_grabber.release()
            print("Camera released.")
    else:
        print("No PCO cameras detected.")