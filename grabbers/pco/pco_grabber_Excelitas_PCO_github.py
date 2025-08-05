import numpy as np
import time
from typing import List, Union, Dict, Optional
from datetime import datetime
import ctypes

# Assuming camera_interface.py is in a parent directory or accessible
from ..camera_interface import CameraGrabberInterface, CameraProperties, Source

# Import the official PCO Python SDK
try:
    import pco
    # You might also need specific modules if they are structured that way,
    # e.g., from pco import Camera, Recorder etc.
    # Check the pco.python documentation/examples.
except ImportError:
    print("WARNING: PCO Python SDK 'pco' not found. Please install it (e.g., pip install pco) or ensure it's in your PATH.")
    pco = None # Mark pco as None if import fails


class PCOCameraGrabber(CameraGrabberInterface):
    def __init__(self):
        super().__init__()
        self.pco_camera: Optional[pco.Camera] = None # Will hold the PCO Camera object
        self._is_initialized = pco is not None
        self._recorder = None # The recorder object if you use PCO's recorder
        self._image_width = 0
        self._image_height = 0
        self._pixel_dtype = np.uint16 # PCO cameras often output 16-bit

        if not self._is_initialized:
            print("PCOCameraGrabber cannot function as 'pco' SDK is not available.")

    def detect_cameras(self) -> List[str]:
        if not self._is_initialized:
            return []
        
        detected_cameras = []
        try:
            # The pco.Camera() constructor without arguments might detect the first camera,
            # or there might be a pco.list_cameras() function.
            # Refer to pco.python documentation for exact detection method.
            # Example (conceptual, verify with actual SDK):
            # If PCO SDK provides an iterator or list of camera objects/names
            # for i in range(pco.get_num_cameras()):
            #     detected_cameras.append(f"PCO Camera {i}")
            
            # A common pattern for high-level APIs is that Camera() itself finds the first.
            # If not, you might have to call pco.sdk.something_to_list_devices()
            # For this example, let's assume it detects automatically or by trying index 0.
            # The pypi example shows `with pco.Camera() as cam:` which implies it finds one.
            # If you need to detect multiple or by ID, you'll need to consult the specific API.
            
            # From the PyPI info, `with pco.Camera() as cam:` implies it implicitly opens/detects.
            # To just detect without opening, you might need a different function or an iterator.
            # For now, let's assume if it can instantiate, a camera is detectable.
            
            # A more direct way to get detectable cameras might involve a lower-level call accessible via pco.sdk
            # Example based on pylablib search result (might not be directly from pco.python):
            # from pylablib.devices import PCO
            # detected_cameras = [f"PCO Camera {i}" for i in range(PCO.get_cameras_number())]

            # Let's use a simpler heuristic for a high-level API: Assume opening "0" works if a camera is present.
            # This is a placeholder; consult pco.python's exact detection method.
            try:
                temp_cam = pco.Camera()
                # If temp_cam can be instantiated, assume camera 0 is detected.
                # You might need to query cam.sdk for a more unique identifier.
                cam_name = f"PCO Camera 0" # Or query temp_cam.sdk.get_camera_name()
                detected_cameras.append(cam_name)
                temp_cam.close() # Close immediately after detection
            except Exception as e:
                self.print(f"No PCO camera detected at index 0 or error during detection: {e}")

        except Exception as e:
            self.print(f"Error during PCO camera detection: {e}")
        return detected_cameras

    # def open(self, index: str, self._src.settings: CameraProperties) -> CameraProperties:
    def open(self, src: Union[Source, None]=None) -> Source:
        if src:
            self._src = src

        if not self._is_initialized:
            raise RuntimeError("PCO Python SDK not initialized. Cannot open camera.")

        if self.is_opened():
            self.release()

        # The 'index' might be used to select a specific camera if multiple are present
        # The `pco.Camera()` constructor might accept an index or a serial number.
        # Check `pco.python` documentation. For now, assume it handles the default camera.
        try:
            self.pco_camera = pco.Camera() # This might open the first available camera by default
            self._is_opened = True
            self.print(f"PCO Camera opened successfully.")

            # Set desired properties using high-level API
            if self._src.settings.width > 0 and self._src.settings.height > 0:
                # pco.python might have a set_roi(x0, y0, width, height) or set_resolution()
                # Example:
                # self.pco_camera.set_roi(self._src.settings.offsetX, self._src.settings.offsetY, self._src.settings.width, self._src.settings.height)
                # Or, using the lower-level sdk object if needed:
                # self.pco_camera.sdk.PCO_SetROI(...)
                pass # You'll need to implement actual property setting based on pco.python API

            if self._src.settings.fps > 0:
                # Example: self.pco_camera.set_frame_rate(self._src.settings.fps)
                pass # Implement setting FPS

            # After setting, arm/configure the camera (high-level API usually handles this implicitly or via a method call)
            # The pco.python PyPI example has `cam.record()` which handles configuration.

            # Get actual properties after opening/setting
            actual_props = CameraProperties()
            # Example:
            # actual_props.width = self.pco_camera.get_width()
            # actual_props.height = self.pco_camera.get_height()
            # actual_props.fps = self.pco_camera.get_frame_rate()
            # If using `cam.image()` in PyPI example, it returns image and meta, use that to get size.
            
            # Let's get the size from the SDK after a conceptual arm/config
            # This is where `pco.sdk.PCO_GetSizes` might be accessed via the wrapper.
            # Placeholder for getting actual width/height
            
            # The pco.python PyPI example shows getting image.shape to get resolution
            # If we call cam.record() and then cam.image(), we can get resolution from image.shape
            
            # For simplicity for now, let's assume we can get these from `self.pco_camera.sdk`
            # You will need to check how the actual pco.python API exposes these.
            wXRes = ctypes.c_ushort()
            wYRes = ctypes.c_ushort()
            # This line assumes pco.camera.sdk gives direct access to the ctypes-wrapped PCO_GetSizes
            # It's more likely to be a high-level `get_resolution()` method in pco.python
            if hasattr(self.pco_camera, 'sdk') and hasattr(self.pco_camera.sdk, 'PCO_GetSizes'):
                 result = self.pco_camera.sdk.PCO_GetSizes(self.pco_camera.handle, ctypes.byref(wXRes), ctypes.byref(wYRes))
                 if self._check_error(result, "PCO_GetSizes (via pco.sdk)"):
                     self._image_width = wXRes.value
                     self._image_height = wYRes.value
            elif hasattr(self.pco_camera, 'get_resolution'): # Example high-level method
                # This is more likely how pco.python exposes it
                res = self.pco_camera.get_resolution() # Might return (width, height) tuple
                if res and len(res) == 2:
                    self._image_width, self._image_height = res
            else:
                 self.print("Could not determine image resolution from pco.python API.")
                 # Fallback or error

            actual_props.width = self._image_width
            actual_props.height = self._image_height
            # For FPS, check if a high-level get_frame_rate exists
            if hasattr(self.pco_camera, 'get_exposure_time'):
                # FPS is often derived from exposure time and readout time
                # The pco.python PyPI example does set_exposure_time.
                # You'll need to figure out how to derive actual FPS if not directly available.
                # Or if PCO exposes get_frame_rate() directly.
                actual_props.fps = self._src.settings.fps # Placeholder, get actual value from camera

            self._actual_camera_properties = actual_props
            return actual_props

        except Exception as e:
            self.print(f"Error opening PCO camera: {e}")
            if self.pco_camera:
                self.pco_camera.close()
            self._is_opened = False
            self.pco_camera = None
            return CameraProperties() # Return empty properties on failure

    def is_opened(self) -> bool:
        # PCO.python's Camera object might have an is_opened() method, or you check if self.pco_camera is not None
        return self._is_opened and self.pco_camera is not None

    def get_frame(self) -> Union[None, dict]:
        if not self.is_opened():
            self.print("Camera not opened.")
            return None

        try:
            # PCO.python documentation (PyPI) shows: image, meta = cam.image()
            # This method usually handles the internal buffer management
            
            # Before calling image(), ensure recording is enabled.
            # The pco.python `record()` method typically starts the acquisition loop.
            # If not already recording, start it.
            if self._recorder is None:
                 # `cam.record()` on PyPI example
                 self.pco_camera.record(number_of_images=0xFFFFFFFF, mode='ring buffer') # Non-blocking ring buffer
                 # Store the recorder object if `record()` returns one
                 self._recorder = True # Mark as recording, actual object might be internal to pco.Camera
            
            image_array, metadata = self.pco_camera.image() # Gets the latest image as numpy array

            # The pco.python SDK might return actual width/height based on the image itself
            if self._image_width == 0: # First frame, get dimensions
                self._image_height, self._image_width = image_array.shape[0:2] # Assuming grayscale or (H,W) or (H,W,C)

            # Metadata object can contain hardware timestamp
            timestamp = datetime.now() # Fallback to system time
            if 'timestamp' in metadata: # Check metadata keys provided by pco.python
                # Convert metadata timestamp to datetime object if needed
                timestamp = metadata['timestamp'] # Example: metadata['timestamp_seconds']
            
            return {'frame': image_array, 'timestamp': timestamp}

        except Exception as e:
            self.print(f"Error grabbing frame: {e}")
            return None

    def release(self):
        if not self._is_initialized:
            return

        if self.pco_camera:
            self.print("Releasing PCO camera resources via pco.python SDK...")
            try:
                # Stop recording if it was started
                if self._recorder:
                    self.pco_camera.stop()
                    self._recorder = None
                
                self.pco_camera.close()
                self.pco_camera = None
                self._is_opened = False
                self.print("PCO camera released.")
            except Exception as e:
                self.print(f"Error releasing PCO camera: {e}")
        else:
            self.print("No PCO camera handle to release.")

    def get_property(self, prop_id: Union[int, str]) -> Union[float, int, None]:
        if not self.is_opened():
            return None

        try:
            if prop_id == "width":
                return self._image_width
            elif prop_id == "height":
                return self._image_height
            elif prop_id == "fps":
                # pco.python might have cam.get_frame_rate() or similar
                # Or you might need to query the SDK object directly
                # Example:
                # return self.pco_camera.get_frame_rate()
                # Or from cached properties:
                if self._actual_camera_properties:
                    return self._actual_camera_properties.fps
                return None
            elif prop_id == "brightness":
                # This usually maps to gain or exposure time for PCO cameras
                # Check pco.python for methods like cam.get_gain() or cam.get_exposure_time()
                # If you implement brightness, you might need to map it to a meaningful range (0-255, 0-100%)
                # Example:
                # return self.pco_camera.get_gain()
                pass
            elif prop_id == "offsetX":
                # Check for pco.python's ROI methods, e.g., cam.get_roi()
                # which might return (x0, y0, width, height)
                pass
            elif prop_id == "offsetY":
                pass
            # Add other properties as exposed by pco.python
            else:
                self.print(f"Unsupported property ID: {prop_id}")
                return None
        except Exception as e:
            self.print(f"Error getting property {prop_id}: {e}")
            return None

    def set_property(self, prop_id: Union[int, str], value: Union[float, int]) -> bool:
        if not self.is_opened():
            return False

        try:
            if prop_id == "width" or prop_id == "height" or prop_id == "offsetX" or prop_id == "offsetY":
                # Setting resolution/ROI might require stopping, setting, and re-arming the camera
                # Check pco.python for methods like cam.set_roi(x0, y0, width, height)
                # You'll likely need to read current ROI, modify it, then set it back.
                # Example (conceptual):
                # current_x0, current_y0, current_width, current_height = self.pco_camera.get_roi()
                # if prop_id == "width": new_width = int(value)
                # ...
                # self.pco_camera.set_roi(new_x0, new_y0, new_width, new_height)
                # self.pco_camera.arm() # Re-arm if needed by SDK
                # Also, update cached _image_width, _image_height
                self.print(f"Setting ROI/resolution properties (width, height, offsetX, offsetY) requires specific implementation with PCO.python's API. Not fully implemented in this skeleton.")
                return False # Placeholder
            elif prop_id == "fps":
                # Example: self.pco_camera.set_frame_rate(float(value))
                self.pco_camera.set_exposure_time(1.0/float(value), 's') # pco.python pypi example sets exposure time. FPS is often tied to this.
                if self._actual_camera_properties:
                    self._actual_camera_properties.fps = float(value)
                return True
            elif prop_id == "brightness":
                # Example: self.pco_camera.set_gain(int(value))
                self.print(f"Setting brightness (gain/exposure) requires specific implementation with PCO.python's API. Not fully implemented in this skeleton.")
                return False # Placeholder
            # Add other properties as exposed by pco.python
            else:
                self.print(f"Unsupported property ID for setting: {prop_id}")
                return False
        except Exception as e:
            self.print(f"Error setting property {prop_id}: {e}")
            return False

    def print(self, s: str):
        print(f"PCO Grabber (pco.python): {s}")

# Example Usage (for testing purposes, same as before)
if __name__ == "__main__":
    if pco is None:
        print("PCO SDK is not available, skipping example usage.")
    else:
        grabber = PCOCameraGrabber()

        # 1. Detect cameras
        cameras = grabber.detect_cameras()
        if not cameras:
            print("No PCO cameras detected. Make sure camera is connected and PCO SDK is installed.")
        else:
            print(f"Detected PCO Cameras: {cameras}")
            camera_to_open = cameras[0] # Try to open the first detected camera

            # 2. Open camera with desired properties
            self._src.settings = CameraProperties(width=1024, height=768, fps=10.0)
            actual_props = grabber.open(camera_to_open, self._src.settings)

            if grabber.is_opened():
                print(f"Camera successfully opened with actual properties: {actual_props}")

                # 3. Get properties
                current_width = grabber.get_property("width")
                current_fps = grabber.get_property("fps")
                print(f"Current width: {current_width}, FPS: {current_fps}")

                # 4. Set a property (e.g., change FPS)
                if grabber.set_property("fps", 5.0): # Try to set FPS to 5
                    print(f"Attempted to set FPS to 5. Actual FPS: {grabber.get_property('fps')}")

                # 5. Get frames
                print("Grabbing 5 frames...")
                for i in range(5):
                    frame_data = grabber.get_frame()
                    if frame_data:
                        frame = frame_data['frame']
                        timestamp = frame_data['timestamp']
                        print(f"Frame {i+1} grabbed: shape {frame.shape}, dtype {frame.dtype}, timestamp {timestamp}")
                        # You can save or display the frame here (e.g., using OpenCV)
                        # import cv2
                        # cv2.imshow(f"PCO Frame {i}", frame)
                        # cv2.waitKey(1)
                    else:
                        print(f"Failed to grab frame {i+1}")
                    time.sleep(0.1) # Simulate some delay

                # 6. Set another property (e.g., change ROI/resolution) - NOTE: This part is highly conceptual
                # and might require more specific pco.python API calls.
                if actual_props.width > 500 and actual_props.height > 500:
                    print(f"Attempting to set ROI to (100, 100) with 500x500 resolution... (Conceptual)")
                    # The implementation for this in set_property is left as a placeholder,
                    # as it's more involved with higher-level APIs.
                    # if grabber.set_property("offsetX", 100) and \
                    #    grabber.set_property("offsetY", 100) and \
                    #    grabber.set_property("width", 500) and \
                    #    grabber.set_property("height", 500):
                    #    print(f"New resolution after setting ROI: {grabber.get_property('width')}x{grabber.get_property('height')}")
                    #    print("Grabbing 2 more frames with new ROI...")
                    #    for i in range(2):
                    #        frame_data = grabber.get_frame()
                    #        if frame_data:
                    #            frame = frame_data['frame']
                    #            print(f"Frame (new ROI) {i+1} grabbed: shape {frame.shape}, dtype {frame.dtype}")
                    #            # import cv2
                    #            # cv2.imshow(f"PCO New ROI Frame {i}", frame)
                    #            # cv2.waitKey(1)
                    #        time.sleep(0.1)
                    # else:
                    #     print("Failed to set new ROI/resolution.")
                    pass

                # 7. Release camera
                grabber.release()
                print("Camera released.")
            else:
                print("Failed to open PCO camera.")