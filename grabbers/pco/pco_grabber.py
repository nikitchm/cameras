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

    parameter_constraints = {
        'min width': None,
        'max width': None,
        'min height': None,
        'max height': None,
        'min exposure time': None,
        'max exposure time': None,
        'trigger_modes': ['auto sequence', 'software trigger', 'external exposure start & software trigger', 'external exposure control', 
                        'external synchronized', 'fast external exposure control', 'external CDS control', 'slow external exposure control',
                        'external synchronized HDSDI'],
        'set_maximum_fps': ['on', 'off'],   # set the image timing of the camera so that the maximum frame rate and the maximum exposure time for this frame rate is achieved. The maximum image frame rate (FPS = frames per second) depends on the pixel rate and the image area selection.
        'acquire_mode' : ['auto', 'external', 'external modulated'],     # the acquire mode of the camera. Acquire mode can be either [auto], [external] or [external modulate].
        'binning' : None, 
    }
    parameter_tooltips = {
        'set_maximum_fps': 'set the image timing of the camera so that the maximum frame rate and the maximum exposure time for this frame rate is achieved. The maximum image frame rate (FPS = frames per second) depends on the pixel rate and the image area selection.',
        'acquire_mode': 'the acquire mode of the camera. Acquire mode can be either [auto], [external] or [external modulate].'
    }

    def __init__(self):
        super().__init__()
        self._cam = None
        self._is_opened = False
        self._buffer_size = 10  # Default ring buffer size
        self._default_exposure_time = 0.01

    def detect_cameras(self, src: Source) -> List[Source]:
        """
        Detects available PCO cameras by attempting to open one.
        The pco package defaults to the first available camera.
        """
        try:
            with pco.Camera() as cam:
                src.id = cam.description['serial']
                src.name = f"{src.cls_name}: {src.id}"
                try:
                    src.settings.other['description'] = cam.description
                except:
                    pass
                try:
                    cam.sdk.arm_camera()
                    src.settings.other['configuration'] = cam.configuration
                except:
                    pass

            return [src]
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
                self._cam.exposure_time = src.settings.other.get('exposure_time', self._default_exposure_time)
                self._cam.sdk.arm_camera()
                self.fps = self.get_fps()

                # get parameter constraints
                self.update_parameter_constraints()
                src.settings.other['parameter_constraints'] = self.parameter_constraints

                # Set up the ring buffer for acquisition.
                self._cam.record(number_of_images=self._buffer_size, mode='ring buffer')
                self._rec_settings = self._cam.rec.get_settings()
                self._is_opened = True

                # Get the actual camera properties after opening.
                src.settings = CameraProperties(
                    width=self._rec_settings['width'],
                    height=self._rec_settings['height'],
                    fps=self.fps,
                    brightness=src.settings.brightness,
                    other=src.settings.other
                )
                time.sleep(.5)  # need to sleep a little before starting recording, getting an error otherwise
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
                # print(meta)
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
        
    def get_fps(self):
        try:
            fps_data = self._cam.sdk.get_frame_rate()
            return fps_data['frame rate mHz']/1000
        except Exception as e:
            return 0
        
    def update_parameter_constraints(self):
        try:
            self.parameter_constraints['min width'] = self._cam_description['min width']
            self.parameter_constraints['max width'] = self._cam_description['max width']
            self.parameter_constraints['min height'] = self._cam_description['min height']
            self.parameter_constraints['max height'] = self._cam_description['max height']
        except:
            pass
        try:
            self.parameter_constraints['binning'] = self._cam_description['binning horz vec']
        except:
            pass
        try:
            self.parameter_constraints['min exposure time'] = self._cam_description['min exposure time']
            self.parameter_constraints['max exposure time'] = self._cam_description['max exposure time']
        except:
            pass
        

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