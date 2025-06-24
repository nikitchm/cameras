import numpy as np
import cv2 # Added: Import OpenCV for image processing
from typing import List, Union, Type # Import Type for type hints
from enum import IntEnum

# Assuming camera_interface.py and CameraProperties are available
from ..camera_interface import CameraGrabberInterface, CameraProperties
import sys, traceback


def printm(s: str):
    print(f"pycapture2_grabber: {s}")

# --- PyCapture2 Import Guard ---
_PYCAPTURE2_AVAILABLE = False
try:
    import PyCapture2 as fc2
    _PYCAPTURE2_AVAILABLE = True
except ImportError:
    printm("Warning: PyCapture2 library (fc2) not found. PyCapture2Grabber functionality will be disabled.")
except Exception as e: # Catch other potential issues during import (e.g., missing DLLs or environment issues)
    printm(f"Warning: Failed to import PyCapture2: {e}. PyCapture2Grabber functionality will be disabled.")

def vdir(obj):
    # get object member names excluding the 'magic' members starting with __
    return [attr for attr in dir(obj) if not attr.startswith('__')]

if _PYCAPTURE2_AVAILABLE:
    
    # --- Original PyCapture2Grabber Implementation (only runs if PyCapture2 is available) ---
    class PyCapture2Grabber(CameraGrabberInterface):
        """
        Implementation of CameraGrabberInterface using PyCapture2 for FLIR cameras.
        """
        def __init__(self):
            self.bus = fc2.BusManager()
            self.cam: Union[fc2.Camera, None] = None
            self._actual_props = CameraProperties(width=0, height=0, fps=0.0, brightness=-1)
            self.name = "" # name of the connected camera

        def open(self, camera_index: int, desired_props: CameraProperties) -> CameraProperties:
            """
            Initializes and opens the FLIR camera at the given index. If the index is larger than 1000, 
            it's treated as the camera's serial number.
            Attempts to set desired properties (width, height, fps, brightness).
            Returns the actual properties the camera was initialized with.
            """
            self.release() # Ensure any previous camera is released
            try:
                if camera_index > 1000:
                    # assume camera_index is the camera's serial number
                    pgrGuid = self.bus.getCameraFromSerialNumber(camera_index)
                else:
                    # connect to the camera_index camera from the list of found cameras
                    num_cameras = self.bus.getNumOfCameras()
                    if camera_index >= num_cameras:
                        raise ValueError(f"Camera index {camera_index} out of range. Only {num_cameras} cameras found.")
                    pgrGuid = self.bus.getCameraFromIndex(camera_index)
                # printm(f'pgrGuid = {pgrGuid}')
                self.cam = fc2.Camera()
                self.cam.connect(pgrGuid)
                cam_info = self.cam.getCameraInfo()
                # self.name = f"{cam_info.vendorName} {cam_info.modelName} (SN: {cam_info.serialNumber})"
                self.name = f"{cam_info.modelName} (SN: {cam_info.serialNumber})"

                # set which values of properties to return
                self.get_props = ['present','absControl','absValue',
                                'onOff','autoManualMode',
                                'valueA','valueB']
                
                fmts = {prop:getattr(fc2.PIXEL_FORMAT,prop) 
                        for prop in dir(fc2.PIXEL_FORMAT) 
                        if not prop.startswith('_')}
                        
                self.pixel_formats = IntEnum('pixel_formats',fmts)


                # set standard device configuration
                config = self.cam.getConfiguration()
                config.grabTimeout = 1000 # in ms. Time (in milliseconds) that camera.retrieveBuffer() and camera.waitForBufferEvent() will wait for an image before timing out and returning.
                config.highPerformanceRetrieveBuffer = True  # This attribute enables retrieveBuffer to run in high performance mode.
                self.cam.setConfiguration(config)

                # ensure camera is in Format7,Mode 0 custom image mode
                fmt7_info, fmt7_supported = self.cam.getFormat7Info(0)
                if fmt7_supported:
                    try:
                        printm(f'Initializing to Format7, desired_props={desired_props}...')
                        mode = desired_props.other['mode'] if 'mode' in desired_props.other else 0
                        image_settings = fc2.Format7ImageSettings(mode,
                                                                  desired_props.offsetX,
                                                                  desired_props.offsetY,
                                                                  desired_props.width,
                                                                  desired_props.height,
                                                                  self.pixel_formats['MONO8'].value)
                        self._set_format7_config(image_settings)
                    except Exception as e:
                        # if the desired_props didn't work, try default values: mode=0, full sensor size
                        printm(f"Couldn't initialize with the desired_props. Error: {e}")
                        camprops_print = CameraProperties(fmt7_info.maxWidth, fmt7_info.maxHeight, 0.0, -1, other={'mode':0})
                        printm(f'Initializing to default Format7, Mode 0 configuration: {camprops_print}...')
                        image_settings = fc2.Format7ImageSettings(0,
                                                                  0,
                                                                  0,
                                                                  fmt7_info.maxWidth,
                                                                  fmt7_info.maxHeight,
                                                                  self.pixel_formats['MONO8'].value)
                        self._set_format7_config(image_settings)

                    
                else:
                    msg = """Camera does not support Format7, Mode 0 custom image
                    configuration. This driver is therefore not compatible, as written."""
                    raise RuntimeError(msg)
        
                self.cam.startCapture()
                printm('Started Capturing')

                if True:
                    # --- Get actual properties after capture starts ---
                    actual_width, actual_height, actual_offsetX, actual_offsetY = 0, 0, 0, 0
                    actual_fps = 0.0

                    image_mode_conf = self.cam.getFormat7Configuration()[0]
                    image_mode_attrs = vdir(image_mode_conf)
                    image_mode = {}
                    for image_mode_attr in image_mode_attrs:
                        image_mode[image_mode_attr] = getattr(image_mode_conf, image_mode_attr)

                    # The most reliable way to get actual dimensions is from a retrieved buffer
                    # using PyCapture2's getCols() and getRows() methods.
                    try:
                        image = self.cam.retrieveBuffer()
                        actual_width = image.getCols()
                        actual_height = image.getRows()
                        # printm(f"Retrieved actual dimensions from buffer: {actual_width}x{actual_height}")
                    except Exception as e:
                        printm(f"Error retrieving buffer for actual dimensions: {e}. Using those from the format7 configuration inquiry.")
                        actual_width = image_mode['width']
                        actual_height = image_mode['height']

                   # Get actual offsetX
                    try:
                        actual_offsetX = image_mode['offsetX']
                        actual_offsetY = image_mode['offsetY']
                    except Exception as e:
                        printm(f"Error trying to get offsets from the format 7 configuration: {e}")
  
                    # Get actual FPS
                    try:
                        prop = self.cam.getProperty(fc2.PROPERTY_TYPE.FRAME_RATE)
                        actual_fps = prop.absValue
                        # printm(f"Actual FPS from property: {actual_fps}")
                    except fc2.Fc2error:
                        printm(f"Warning: Could not get FRAME_RATE property. Falling back to configured/desired FPS.")
                        # Fallback to what was attempted to be set, or desired_props.fps
                        actual_fps = desired_props.fps if desired_props.fps > 0 else 30.0
                    if actual_fps == 0.0: # Final fallback if still 0
                        actual_fps = desired_props.fps if desired_props.fps > 0 else 30.0

                    actual_brightness = -1
                    try:
                        prop = self.cam.getProperty(fc2.PROPERTY_TYPE.BRIGHTNESS)
                        actual_brightness = int(prop.absValue)
                    except fc2.Fc2error:
                        pass # Brightness property might not be supported

                    self._actual_props = CameraProperties(width=actual_width, height=actual_height,
                                                          offsetX=actual_offsetX, offsetY=actual_offsetY,
                                                          fps=actual_fps, brightness=actual_brightness)
                    # printm(f"Camera {self.name} opened. Actual Props: {self._actual_props}")
                    return self._actual_props
                else:
                    return desired_props

            except fc2.Fc2error as e:
                printm(f"PyCapture2Grabber Error (Fc2error): {e}")
                traceback.print_exc(file=sys.stdout)
                self.release()
                return CameraProperties(0, 0, 0, 0, 0.0, -1)
            except Exception as e:
                printm(f"PyCapture2Grabber Error (General): {e}")
                traceback.print_exc(file=sys.stdout)
                self.release()
                return CameraProperties(0, 0, 0, 0, 0.0, -1)

        def get_frame(self) -> Union[np.ndarray, None]:
            """
            Reads a single frame from the FLIR camera.
            Converts the PyCapture2 image to an OpenCV (BGR) NumPy array.
            """
            if self.cam and self.is_opened():
                try:
                    image = self.cam.retrieveBuffer()
                    
                    # Convert to BGR format using PyCapture2's internal conversion.
                    converted_image = image.convert(fc2.PIXEL_FORMAT.BGR)
                    
                    # Get dimensions of the converted image using PyCapture2's methods
                    rows = converted_image.getRows()
                    cols = converted_image.getCols()
                    
                    # Reshape the 1D raw data into a 3-channel BGR NumPy array.
                    # The size of converted_image.getData() will be rows * cols * 3
                    # if the BGR conversion was successful.
                    frame = np.array(converted_image.getData(), dtype=np.uint8).reshape((rows, cols, 3))

                    # The resizing check below is still useful if the actual captured
                    # resolution (from getRows/getCols) is different from what's needed
                    # by the rest of the application (self._actual_props).
                    # This would happen if the camera is set to a specific mode (e.g., 2048x2048)
                    # but the application wants a downscaled 640x480 view.
                    if frame.shape[1] != self._actual_props.width or frame.shape[0] != self._actual_props.height:
                        printm(f"PyCapture2Grabber Warning: Frame dimensions ({frame.shape[1]}x{frame.shape[0]}) mismatch actual properties ({self._actual_props.width}x{self._actual_props.height}). Auto-resizing for consistency.")
                        frame = cv2.resize(frame, (self._actual_props.width, self._actual_props.height))

                    return frame

                except fc2.Fc2error as e:
                    printm(f"PyCapture2Grabber Error retrieving frame: {e}")
                    return None
                except Exception as e:
                    printm(f"PyCapture2Grabber General error processing frame: {e}")
                    return None
            return None

        def get_property(self, prop_id: int) -> Union[float, None]:
            """
            Gets a camera property.
            Maps OpenCV CAP_PROP_IDs to PyCapture2 properties.
            """
            if not self.cam or not self.is_opened():
                return None

            try:
                if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
                    return float(self._actual_props.width)
                elif prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
                    return float(self._actual_props.height)
                elif prop_id == cv2.CAP_PROP_FPS:
                    # Attempt to get from camera's reported frame rate property if available
                    prop = self.cam.getProperty(fc2.PROPERTY_TYPE.FRAME_RATE)
                    return float(prop.absValue)
                elif prop_id == cv2.CAP_PROP_BRIGHTNESS:
                    prop = self.cam.getProperty(fc2.PROPERTY_TYPE.BRIGHTNESS)
                    return float(prop.absValue)
                # Add more mappings as needed for other OpenCV CAP_PROP_IDs
                else:
                    printm(f"Unsupported property ID requested: {prop_id}")
                    return None
            except fc2.Fc2error as e:
                printm(f"Error getting property {prop_id}: {e}")
                return None
            except Exception as e:
                printm(f"General error getting property {prop_id}: {e}")
                return None

        def set_property(self, prop_id: int, value: float) -> bool:
            """
            Sets a camera property.
            Maps OpenCV CAP_PROP_IDs to PyCapture2 properties.
            Note: Setting resolution/FPS often requires stopping/restarting capture.
            """
            if not self.cam or not self.is_opened():
                return False

            try:
                if prop_id == cv2.CAP_PROP_BRIGHTNESS:
                    prop = self.cam.getProperty(fc2.PROPERTY_TYPE.BRIGHTNESS)
                    prop.absValue = float(value)
                    # Clamp value to camera's supported range
                    prop_info = self.cam.getPropertyInfo(fc2.PROPERTY_TYPE.BRIGHTNESS)
                    if prop.absValue < prop_info.absMin: prop.absValue = prop_info.absMin
                    if prop.absValue > prop_info.absMax: prop.absValue = prop_info.absMax
                    self.cam.setProperty(prop)
                    return True
                # For resolution (FRAME_WIDTH, FRAME_HEIGHT) and FPS,
                # it's generally recommended to call `cam.setVideoModeAndFrameRate()`
                # This is best handled by restarting the acquisition thread with new desired_props
                # rather than direct property setting mid-stream via `set_property`.
                # Returning False for these to indicate they aren't directly settable here.
                elif prop_id == cv2.CAP_PROP_FRAME_WIDTH or prop_id == cv2.CAP_PROP_FRAME_HEIGHT or prop_id == cv2.CAP_PROP_FPS:
                    printm(f"Setting resolution/FPS via set_property is not directly supported. Restart camera with new desired_props.")
                    return False
                else:
                    printm(f"Unsupported property ID for setting: {prop_id}")
                    return False
            except fc2.Fc2error as e:
                printm(f"Error setting property {prop_id}: {e}")
                return False
            except Exception as e:
                printm(f"General error setting property {prop_id}: {e}")
                return False

        def release(self):
            """
            Stops capture and disconnects the FLIR camera.
            """
            if self.cam:
                try:
                    if self.is_opened(): # Check if capture is actually running
                        self.cam.stopCapture()
                        printm(f"Stopped capture for camera {self.name}.")
                        self.cam.disconnect()
                        printm(f"Disconnected camera {self.name}.")
                except fc2.Fc2error as e:
                    printm(f"PyCapture2Grabber Error during release: {e}")
                finally:
                    self.cam = None
                    self.name = ""

        def is_opened(self) -> bool:
            """
            Checks if the FLIR camera is connected and capturing.
            """
            if self.cam:
                try:
                    # In some PyCapture2 versions, isConnected might be a property (bool) not a method.
                    # The error 'bool' object is not callable suggests this.
                    # We'll try to access it as a property.
                    return self.cam.isConnected # Removed parentheses
                except Exception as e: # Catch broader exceptions if self.cam is in a bad state
                    printm(f"Error checking if camera is connected: {e}")
                    return False
            return False

        def detect_cameras(self) -> List[str]:
            """
            Detects available FLIR cameras using PyCapture2's BusManager.
            Returns a list of camera names (e.g., "FLIR Camera (SN: 12345678)").
            """
            detected_camera_names = []
            try:
                num_cameras = self.bus.getNumOfCameras()
                printm(f"Detected {num_cameras} FLIR cameras.")
                for i in range(num_cameras):
                    pgrGuid = self.bus.getCameraFromIndex(i)
                    cam = fc2.Camera()
                    try:
                        cam.connect(pgrGuid)
                        camera_info = cam.getCameraInfo()
                        name = f"{camera_info.vendorName} {camera_info.modelName} (SN: {camera_info.serialNumber})"
                        detected_camera_names.append(name)
                        printm(f"Found: {name}")
                    except fc2.Fc2error as e:
                        printm(f"Could not connect to camera at index {i}: {e}")
                    finally:
                        if cam:
                            try:
                                cam.disconnect()
                            except fc2.Fc2error:
                                pass # Already disconnected or error during disconnect
            except fc2.Fc2error as e:
                printm(f"Error during camera detection (BusManager): {e}")
            except Exception as e:
                printm(f"General error during camera detection: {e}")
                
            return detected_camera_names if detected_camera_names else ["No FLIR cameras detected"]
        
##################################################################
        def _set_format7_config(self, format7_config):
            """Validates and sets the provided Format7 configuration.
            """
            try:            
                fmt7PktInfo, valid = self.cam.validateFormat7Settings(format7_config)
                if valid:
                    self.cam.setFormat7ConfigurationPacket(fmt7PktInfo.recommendedBytesPerPacket, format7_config)
                else:
                    printm(f"Image config    {format7_config}    isn't valid")
            except fc2.Fc2error as e:
                raise RuntimeError(f"Couldn't configure format7 settings: {e}")
            
else:
    # --- Dummy PyCapture2Grabber Implementation (used if PyCapture2 is NOT available) ---
    class PyCapture2Grabber(CameraGrabberInterface):
        """
        Dummy PyCapture2Grabber class, used when PyCapture2 library is not available.
        Raises an error if any camera-related methods are called.
        """
        def __init__(self):
            self.error_message = "PyCapture2 library is not installed or configured correctly on this system."
            printm(f"Initialized dummy grabber. {self.error_message}")
            self.cam = None # Maintain attribute for type consistency
            self.name = ""
            self._actual_props = CameraProperties(0,0,0,0,0,0) # Maintain attribute for type consistency

        def _raise_error(self, method_name: str):
            raise RuntimeError(f"Cannot call PyCapture2Grabber.{method_name}: {self.error_message}")

        def open(self, camera_index: int, desired_props: CameraProperties) -> CameraProperties:
            self._raise_error("open")
            return CameraProperties(0,0,0,0,0,0) # For type hint consistency

        def get_frame(self) -> Union[np.ndarray, None]:
            self._raise_error("get_frame")
            return None

        def get_property(self, prop_id: int) -> Union[float, None]:
            self._raise_error("get_property")
            return None

        def set_property(self, prop_id: int, value: float) -> bool:
            self._raise_error("set_property")
            return False

        def release(self):
            printm(f"Attempted to release (dummy). {self.error_message}")

        def is_opened(self) -> bool:
            return False

        def detect_cameras(self) -> List[str]:
            return [f"PyCapture2 not available ({self.error_message})"]


