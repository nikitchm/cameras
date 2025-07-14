import ctypes
import numpy as np
import time
from typing import List, Union, Dict, Optional
from datetime import datetime
import os

# Assuming camera_interface.py is in a parent directory or accessible
from ..camera_interface import CameraGrabberInterface, CameraProperties

# --- PCO SDK ctypes Definitions ---
# This section requires careful mapping from PCO SDK header files or documentation.
# The types defined here are based on common C types and SDK documentation.
# You might need to adjust them based on your specific SDK version and platform.

# Common PCO_ERROR (DWORD)
PCO_NOERROR = 0x00000000

# Constants for property IDs (add more as needed)
PCO_PROPERTY_WIDTH = 1
PCO_PROPERTY_HEIGHT = 2
PCO_PROPERTY_FPS = 3

# Define the PCO SDK DLL path
# IMPORTANT: Adjust this path to your actual PCO SDK installation
# For Windows: SC2_Cam.dll
# For Linux/macOS: libSC2_Cam.so or libSC2_Cam.dylib (if available)
if os.name == 'nt': # Windows
    PCO_SDK_DLL_PATH = "C:\\Program Files\\PCO\\SDK\\SC2_Cam.dll" # Example path, verify yours
elif os.uname().sysname == 'Linux': # Linux
    PCO_SDK_DLL_PATH = "/usr/local/lib/libSC2_Cam.so" # Example path, verify yours
else:
    PCO_SDK_DLL_PATH = None # Placeholder for other OS

if not PCO_SDK_DLL_PATH or not os.path.exists(PCO_SDK_DLL_PATH):
    print(f"WARNING: PCO SDK DLL not found at {PCO_SDK_DLL_PATH}. Please set PCO_SDK_DLL_PATH correctly.")


# Define common PCO SDK data types
WORD = ctypes.c_ushort
DWORD = ctypes.c_ulong
LONG = ctypes.c_long
HANDLE = ctypes.c_void_p
BOOL = ctypes.c_int # PCO uses int for BOOL (0 for FALSE, non-zero for TRUE)

# PCO Structures (these need to be accurate based on the SDK PDF)
# Example: PCO_Description
class PCO_Description(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wSize", WORD),
        ("wSensorType", WORD),
        ("wSensorSubType", WORD),
        ("wSensorFormat", WORD),
        ("wDynResDESC", WORD),
        ("wMaxHorzRes", WORD),
        ("wMaxVertRes", WORD),
        ("wMinHorzRes", WORD),
        ("wMinVertRes", WORD),
        ("wRoiHorzRes", WORD),
        ("wRoiVertRes", WORD),
        ("wMaxBinHorz", WORD),
        ("wMaxBinVert", WORD),
        ("wActualRate", WORD),
        ("wCameraType", WORD),
        ("wCameraRevision", WORD),
        ("wCameraVariant", WORD),
        ("wNrOfOutputChannels", WORD),
        ("dwMinExposureDESC", DWORD),
        ("dwMaxExposureDESC", DWORD),
        ("dwMinDelayDESC", DWORD),
        ("dwMaxDelayDESC", DWORD),
        ("dwMinPeriodDESC", DWORD),
        ("dwMaxPeriodDESC", DWORD),
        ("wDoubleImage", WORD),
        ("wDoubleImage", WORD),
        ("wGlobalShutter", WORD),
        ("wRollingShutter", WORD),
        ("wMinPeriodFPS", WORD),
        ("wMaxPeriodFPS", WORD),
        ("wMinPeriodFPS_pco", WORD), # Placeholder, verify actual name
        ("wMaxPeriodFPS_pco", WORD), # Placeholder, verify actual name
        # ... many more fields according to PCO_CAMDESC in SC2_SDK.H or SDK documentation
        # Ensure all fields are exactly as defined in the SDK header
        ("wMinHorzResBin", WORD),
        ("wMinVertResBin", WORD),
        ("wReserved", WORD * 18), # Filler for alignment/future use, check SDK
    ]

# Example: PCO_CameraSetup (Simplified, only showing relevant parts for this example)
class PCO_CameraSetup(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wSize", WORD),
        ("wCameraType", WORD),
        ("wCameraRevision", WORD),
        ("wCameraVariant", WORD),
        ("dwSerialNumber", DWORD),
        ("dwFirmwareVersion", DWORD),
        ("wHardwareVersion", WORD),
        ("wCPLDVersion", WORD),
        ("wSensorType", WORD),
        ("wSensorSubType", WORD),
        ("wSensorFormat", WORD),
        ("wResolution", WORD),
        ("wReserved", WORD * 3),
        ("wExtTriggerMode", WORD),
        ("wDelayTime", WORD),
        ("wExposureTime", WORD),
        ("wConversionFactor", WORD),
        ("wPixelRate", WORD),
        ("wOffset", WORD),
        ("wNoise", WORD),
        ("wCoolingSetPoint", WORD),
        ("wCoolingStatus", WORD),
        ("wIRFilter", WORD),
        ("wHotPixelCorrection", WORD),
        ("wBadPixelCorrection", WORD),
        ("wDisplayMode", WORD),
        ("wDoubleImage", WORD),
        ("wGlobalShutter", WORD),
        ("wRollingShutter", WORD),
        ("wActualRate", WORD),
        ("wReserved2", WORD * 16), # Placeholder, verify actual size
    ]

# Example: PCO_ROI
class PCO_ROI(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wSize", WORD),
        ("wRoiX0", WORD),
        ("wRoiY0", WORD),
        ("wRoiX1", WORD),
        ("wRoiY1", WORD),
        ("wReserved", WORD * 4), # Filler
    ]

# Example: PCO_Timing
class PCO_Timing(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wSize", WORD),
        ("dwDelay", DWORD),
        ("dwExposure", DWORD),
        ("dwPeriod", DWORD),
        ("wTimeBaseDelay", WORD),
        ("wTimeBaseExposure", WORD),
        ("wTimeBasePeriod", WORD),
        ("wReserved", WORD * 4) # Filler
    ]

# Load the DLL
try:
    pcosdk = ctypes.CDLL(PCO_SDK_DLL_PATH)

    # --- Define function prototypes ---
    # Functions from PCO SDK (adjust argtypes and restype as per SDK PDF)

    # PCO_OpenCamera(phCam: LPHANDLE, wCamNum: WORD)
    pcosdk.PCO_OpenCamera.argtypes = [ctypes.POINTER(HANDLE), WORD]
    pcosdk.PCO_OpenCamera.restype = DWORD

    # PCO_CloseCamera(hCam: HANDLE)
    pcosdk.PCO_CloseCamera.argtypes = [HANDLE]
    pcosdk.PCO_CloseCamera.restype = DWORD

    # PCO_GetCameraDescription(hCam: HANDLE, psDescription: LP_PCO_DESCRIPTION)
    pcosdk.PCO_GetCameraDescription.argtypes = [HANDLE, ctypes.POINTER(PCO_Description)]
    pcosdk.PCO_GetCameraDescription.restype = DWORD

    # PCO_GetSizes(hCam: HANDLE, wXRes: LPWORD, wYRes: LPWORD)
    pcosdk.PCO_GetSizes.argtypes = [HANDLE, ctypes.POINTER(WORD), ctypes.POINTER(WORD)]
    pcosdk.PCO_GetSizes.restype = DWORD

    # PCO_SetROI(hCam: HANDLE, wX0: WORD, wY0: WORD, wX1: WORD, wY1: WORD)
    pcosdk.PCO_SetROI.argtypes = [HANDLE, WORD, WORD, WORD, WORD]
    pcosdk.PCO_SetROI.restype = DWORD

    # PCO_GetROI(hCam: HANDLE, wX0: LPWORD, wY0: LPWORD, wX1: LPWORD, wY1: LPWORD)
    pcosdk.PCO_GetROI.argtypes = [HANDLE, ctypes.POINTER(WORD), ctypes.POINTER(WORD), ctypes.POINTER(WORD), ctypes.POINTER(WORD)]
    pcosdk.PCO_GetROI.restype = DWORD

    # PCO_GetFrameRate(hCam: HANDLE, psTiming: LP_PCO_TIMING)
    pcosdk.PCO_GetFrameRate.argtypes = [HANDLE, ctypes.POINTER(PCO_Timing)]
    pcosdk.PCO_GetFrameRate.restype = DWORD

    # PCO_SetFrameRate(hCam: HANDLE, psTiming: LP_PCO_TIMING)
    pcosdk.PCO_SetFrameRate.argtypes = [HANDLE, ctypes.POINTER(PCO_Timing)]
    pcosdk.PCO_SetFrameRate.restype = DWORD

    # PCO_AllocateBuffer(hCam: HANDLE, piBufferNr: LPINT, pBuffer: LPVOID, dwBufferSize: DWORD, phEvent: LPHANDLE)
    pcosdk.PCO_AllocateBuffer.argtypes = [HANDLE, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_void_p), DWORD, ctypes.POINTER(HANDLE)]
    pcosdk.PCO_AllocateBuffer.restype = DWORD

    # PCO_FreeBuffer(hCam: HANDLE, iBufferNr: INT)
    pcosdk.PCO_FreeBuffer.argtypes = [HANDLE, ctypes.c_int]
    pcosdk.PCO_FreeBuffer.restype = DWORD

    # PCO_AddBufferEx(hCam: HANDLE, dwEntryAddr: DWORD, dwEntryLen: DWORD, iBufferNr: INT, wXRes: WORD, wYRes: WORD, wBitRes: WORD)
    pcosdk.PCO_AddBufferEx.argtypes = [
        HANDLE, DWORD, DWORD, ctypes.c_int, WORD, WORD, WORD
    ]
    pcosdk.PCO_AddBufferEx.restype = DWORD

    # PCO_WaitforBuffer(hCam: HANDLE, iBufferNr: INT, piActStatus: LPINT, dwTimeOut: DWORD)
    pcosdk.PCO_WaitforBuffer.argtypes = [HANDLE, ctypes.c_int, ctypes.POINTER(ctypes.c_int), DWORD]
    pcosdk.PCO_WaitforBuffer.restype = DWORD

    # PCO_SetRecordingState(hCam: HANDLE, wState: WORD)
    pcosdk.PCO_SetRecordingState.argtypes = [HANDLE, WORD]
    pcosdk.PCO_SetRecordingState.restype = DWORD

    # PCO_ArmCamera(hCam: HANDLE)
    pcosdk.PCO_ArmCamera.argtypes = [HANDLE]
    pcosdk.PCO_ArmCamera.restype = DWORD

    # PCO_CancelImages(hCam: HANDLE)
    pcosdk.PCO_CancelImages.argtypes = [HANDLE]
    pcosdk.PCO_CancelImages.restype = DWORD

    # PCO_GetErrorText(dwError: DWORD, pszText: LPSTR, dwLen: DWORD)
    pcosdk.PCO_GetErrorText.argtypes = [DWORD, ctypes.c_char_p, DWORD]
    pcosdk.PCO_GetErrorText.restype = DWORD

except OSError as e:
    print(f"Error loading PCO SDK DLL: {e}. Please ensure the DLL path is correct and the SDK is installed.")
    pcosdk = None # Mark pcosdk as None if loading fails

class PCOCameraGrabber(CameraGrabberInterface):
    def __init__(self):
        super().__init__()
        self.pco_cam_handle: HANDLE = None
        self._is_initialized = False
        self._buffer_info = [] # List to store (buffer_nr, buffer_ptr, buffer_size, hEvent)
        self._current_buffer_idx = 0
        self._num_buffers = 2 # Use a double buffer for continuous acquisition
        self._buffer_allocated = False
        self._image_width = 0
        self._image_height = 0
        self._pixel_bytes = 2 # Assuming 16-bit monochrome, adjust if different (e.g., 1 for 8-bit, 3 for RGB)

        if pcosdk is None:
            print("PCO SDK not loaded. PCOCameraGrabber will not function.")
            return

        self._is_initialized = True

    def _check_error(self, result: DWORD, func_name: str):
        """Helper to check PCO SDK function return codes."""
        if self._is_initialized and result != PCO_NOERROR:
            error_text_buffer = ctypes.create_string_buffer(256)
            pcosdk.PCO_GetErrorText(result, error_text_buffer, ctypes.sizeof(error_text_buffer))
            error_message = error_text_buffer.value.decode('utf-8')
            print(f"PCO SDK Error in {func_name}: {result:#010x} - {error_message}")
            return False
        return True

    def detect_cameras(self) -> List[str]:
        if not self._is_initialized:
            return []

        detected_cameras = []
        # PCO cameras typically connect directly.
        # You can try opening a camera at index 0 and then getting its description.
        # More advanced detection might involve iterating through potential interfaces
        # if the SDK supports it.
        temp_cam_handle = HANDLE()
        result = pcosdk.PCO_OpenCamera(ctypes.byref(temp_cam_handle), WORD(0)) # Try opening camera 0
        if self._check_error(result, "PCO_OpenCamera"):
            desc = PCO_Description(wSize=ctypes.sizeof(PCO_Description))
            result_desc = pcosdk.PCO_GetCameraDescription(temp_cam_handle, ctypes.byref(desc))
            if self._check_error(result_desc, "PCO_GetCameraDescription"):
                # A more robust name might involve serial number or specific model
                detected_cameras.append(f"PCO Camera (Index 0)") # You can improve this name
            pcosdk.PCO_CloseCamera(temp_cam_handle) # Close after detection
        return detected_cameras

    def open(self, index: str, desired_props: CameraProperties) -> CameraProperties:
        if not self._is_initialized:
            raise RuntimeError("PCO SDK not initialized. Cannot open camera.")

        if self.is_opened():
            self.release()

        camera_index = int(index) # PCO typically uses integer indices like 0

        self.pco_cam_handle = HANDLE()
        result = pcosdk.PCO_OpenCamera(ctypes.byref(self.pco_cam_handle), WORD(camera_index))
        if not self._check_error(result, f"PCO_OpenCamera(Index {camera_index})"):
            self.pco_cam_handle = None
            return CameraProperties() # Return empty properties on failure

        self._is_opened = True
        self.print(f"PCO Camera at index {camera_index} opened successfully.")

        # Get initial camera properties
        desc = PCO_Description(wSize=ctypes.sizeof(PCO_Description))
        result = pcosdk.PCO_GetCameraDescription(self.pco_cam_handle, ctypes.byref(desc))
        self._check_error(result, "PCO_GetCameraDescription")

        # Set desired properties
        actual_props = CameraProperties()
        actual_props.width = desc.wMaxHorzRes
        actual_props.height = desc.wMaxVertRes

        # Set ROI if desired
        if desired_props.width > 0 and desired_props.height > 0:
            x0 = desired_props.offsetX
            y0 = desired_props.offsetY
            x1 = x0 + desired_props.width - 1
            y1 = y0 + desired_props.height - 1

            result = pcosdk.PCO_SetROI(self.pco_cam_handle, WORD(x0), WORD(y0), WORD(x1), WORD(y1))
            if not self._check_error(result, "PCO_SetROI"):
                # Attempt to recover or use default if setting ROI fails
                self.print("Failed to set desired ROI, using full frame.")

        # Set FPS if desired
        if desired_props.fps > 0:
            timing_struct = PCO_Timing(wSize=ctypes.sizeof(PCO_Timing))
            # Get current timing to preserve other settings if any
            result_get_timing = pcosdk.PCO_GetFrameRate(self.pco_cam_handle, ctypes.byref(timing_struct))
            if self._check_error(result_get_timing, "PCO_GetFrameRate"):
                # Convert desired FPS to PCO timing units (period, timebase)
                # This calculation depends on camera model and actual possible FPS values.
                # Example: Period = 1 / FPS. You need to map this to PCO_Timing.dwPeriod and wTimeBasePeriod
                # For simplicity, we might just try to set it, but actual values might differ.
                # Consult SDK section 2.6 Timing Control for proper calculation (e.g., dwPeriod/wTimeBasePeriod)
                # For now, let's just attempt to set a 'dummy' period (highly simplified, won't work universally)
                # You'll need to implement the actual conversion from FPS to dwPeriod and wTimeBasePeriod
                # based on your camera's capabilities and SDK examples.
                # For demonstration, setting arbitrary period assuming milliseconds and a timebase of 0 (ns) or 1 (us)
                # E.g., if target FPS is 10, period is 100ms.
                # If wTimeBasePeriod is 1 (microseconds), then dwPeriod = 100 * 1000 = 100000.
                if desired_props.fps > 0:
                    period_us = int(1_000_000 / desired_props.fps) # Convert FPS to period in microseconds
                    timing_struct.dwPeriod = DWORD(period_us)
                    timing_struct.wTimeBasePeriod = WORD(1) # Microseconds

                    result_set_timing = pcosdk.PCO_SetFrameRate(self.pco_cam_handle, ctypes.byref(timing_struct))
                    if not self._check_error(result_set_timing, "PCO_SetFrameRate"):
                        self.print(f"Warning: Could not set desired FPS to {desired_props.fps}.")
            else:
                 self.print("Warning: Could not get current frame rate to set desired FPS.")

        # Arm camera after setting parameters
        result_arm = pcosdk.PCO_ArmCamera(self.pco_cam_handle)
        if not self._check_error(result_arm, "PCO_ArmCamera"):
            self.release() # Release if arming fails
            return CameraProperties()

        # Get actual properties after arming (which might adjust to camera capabilities)
        actual_x_res = WORD()
        actual_y_res = WORD()
        result_get_sizes = pcosdk.PCO_GetSizes(self.pco_cam_handle, ctypes.byref(actual_x_res), ctypes.byref(actual_y_res))
        self._check_error(result_get_sizes, "PCO_GetSizes")
        actual_props.width = actual_x_res.value
        actual_props.height = actual_y_res.value

        actual_timing_struct = PCO_Timing(wSize=ctypes.sizeof(PCO_Timing))
        result_get_timing_final = pcosdk.PCO_GetFrameRate(self.pco_cam_handle, ctypes.byref(actual_timing_struct))
        if self._check_error(result_get_timing_final, "PCO_GetFrameRate"):
            # Convert actual timing to FPS
            # dwPeriod is typically in units of wTimeBasePeriod (0: ns, 1: us, 2: ms)
            if actual_timing_struct.wTimeBasePeriod == 0: # nanoseconds
                period_s = actual_timing_struct.dwPeriod / 1_000_000_000
            elif actual_timing_struct.wTimeBasePeriod == 1: # microseconds
                period_s = actual_timing_struct.dwPeriod / 1_000_000
            elif actual_timing_struct.wTimeBasePeriod == 2: # milliseconds
                period_s = actual_timing_struct.dwPeriod / 1_000
            else:
                period_s = 0 # Unknown timebase

            if period_s > 0:
                actual_props.fps = 1.0 / period_s
            else:
                actual_props.fps = 0.0 # Could not determine FPS

        # Set image size for buffer allocation
        self._image_width = actual_props.width
        self._image_height = actual_props.height

        # Allocate buffers for image acquisition
        self._allocate_buffers()

        self._actual_camera_properties = actual_props
        return actual_props

    def _allocate_buffers(self):
        if self._buffer_allocated:
            return

        image_size_bytes = self._image_width * self._image_height * self._pixel_bytes

        for i in range(self._num_buffers):
            buffer_nr_ptr = ctypes.c_int()
            buffer_ptr = ctypes.c_void_p()
            h_event = HANDLE() # Event handle for asynchronous operations, useful with WaitforBuffer

            result = pcosdk.PCO_AllocateBuffer(
                self.pco_cam_handle,
                ctypes.byref(buffer_nr_ptr),
                ctypes.byref(buffer_ptr),
                DWORD(image_size_bytes),
                ctypes.byref(h_event)
            )

            if not self._check_error(result, f"PCO_AllocateBuffer (buffer {i})"):
                # Clean up any partially allocated buffers
                for buf_nr, _, _, _ in self._buffer_info:
                    pcosdk.PCO_FreeBuffer(self.pco_cam_handle, buf_nr)
                self._buffer_info = []
                raise RuntimeError("Failed to allocate image buffers.")

            self._buffer_info.append((buffer_nr_ptr.value, buffer_ptr, image_size_bytes, h_event))
            self.print(f"Allocated buffer {buffer_nr_ptr.value} at address {hex(buffer_ptr.value)}")

        self._buffer_allocated = True
        self.print(f"Successfully allocated {self._num_buffers} buffers.")

    def is_opened(self) -> bool:
        return self._is_opened and self.pco_cam_handle is not None

    def get_frame(self) -> Union[None, dict]:
        if not self.is_opened():
            self.print("Camera not opened.")
            return None
        if not self._buffer_allocated:
            self.print("Buffers not allocated. Cannot get frame.")
            return None

        # Stop recording before adding a new buffer to ensure it's not currently in use
        result_stop = pcosdk.PCO_SetRecordingState(self.pco_cam_handle, WORD(0x0000)) # Stop
        self._check_error(result_stop, "PCO_SetRecordingState (stop before adding)")

        # Use a circular buffer approach
        current_buffer_nr, current_buffer_ptr, current_buffer_size, _ = self._buffer_info[self._current_buffer_idx]

        # Add the buffer to the acquisition queue
        # wBitRes is the effective bit resolution of the image (e.g., 12 for a 12-bit camera)
        # You need to determine this from PCO_GetCameraDescription or similar.
        # For simplicity, assuming 16-bit for now.
        wBitRes = WORD(self._pixel_bytes * 8) # e.g., 16 for 16-bit, 8 for 8-bit

        result_add = pcosdk.PCO_AddBufferEx(
            self.pco_cam_handle,
            DWORD(ctypes.cast(current_buffer_ptr, ctypes.c_void_p).value), # Address of the buffer
            DWORD(current_buffer_size),
            ctypes.c_int(current_buffer_nr),
            WORD(self._image_width),
            WORD(self._image_height),
            wBitRes
        )
        if not self._check_error(result_add, f"PCO_AddBufferEx (buffer {current_buffer_nr})"):
            return None

        # Start recording
        result_start = pcosdk.PCO_SetRecordingState(self.pco_cam_handle, WORD(0x0001)) # Start
        if not self._check_error(result_start, "PCO_SetRecordingState (start)"):
            return None

        # Wait for the buffer to be filled
        actual_status = ctypes.c_int()
        # Timeout can be adjusted. dwTimeOut=0xFFFFFFFF for infinite wait, or a specific ms value
        result_wait = pcosdk.PCO_WaitforBuffer(self.pco_cam_handle, ctypes.c_int(current_buffer_nr), ctypes.byref(actual_status), DWORD(1000)) # 1000ms timeout
        if not self._check_error(result_wait, f"PCO_WaitforBuffer (buffer {current_buffer_nr})"):
            self.print(f"Warning: Failed to get frame from buffer {current_buffer_nr}. Status: {actual_status.value}")
            return None

        # Extract image data
        try:
            # Create a numpy array view of the buffer
            # Reshape based on width, height, and data type (e.g., np.uint16 for 16-bit)
            image_data = ctypes.cast(current_buffer_ptr, ctypes.POINTER(ctypes.c_ushort * (self._image_width * self._image_height)))
            np_array = np.frombuffer(image_data.contents, dtype=np.uint16).reshape(self._image_height, self._image_width)

            # You might want to copy the array if the buffer is immediately reused by the camera
            # np_array = np_array.copy()

            timestamp = datetime.now() # PCO SDK can provide hardware timestamps, this is a placeholder

            # Move to the next buffer for the next acquisition
            self._current_buffer_idx = (self._current_buffer_idx + 1) % self._num_buffers

            return {'frame': np_array, 'timestamp': timestamp}

        except Exception as e:
            self.print(f"Error processing image buffer: {e}")
            return None

    def release(self):
        if not self._is_initialized:
            return

        if self.pco_cam_handle:
            self.print("Releasing PCO camera resources...")
            # Stop recording
            result_stop = pcosdk.PCO_SetRecordingState(self.pco_cam_handle, WORD(0x0000))
            self._check_error(result_stop, "PCO_SetRecordingState (stop on release)")

            # Cancel any pending images
            result_cancel = pcosdk.PCO_CancelImages(self.pco_cam_handle)
            self._check_error(result_cancel, "PCO_CancelImages")

            # Free allocated buffers
            for buf_nr, _, _, _ in self._buffer_info:
                result_free = pcosdk.PCO_FreeBuffer(self.pco_cam_handle, ctypes.c_int(buf_nr))
                self._check_error(result_free, f"PCO_FreeBuffer (buffer {buf_nr})")
                self.print(f"Freed buffer {buf_nr}.")
            self._buffer_info = []
            self._buffer_allocated = False

            # Close the camera
            result_close = pcosdk.PCO_CloseCamera(self.pco_cam_handle)
            self._check_error(result_close, "PCO_CloseCamera")
            self.pco_cam_handle = None
            self._is_opened = False
            self.print("PCO camera released.")
        else:
            self.print("No PCO camera handle to release.")

    def get_property(self, prop_id: Union[int, str]) -> Union[float, int, None]:
        if not self.is_opened():
            return None

        if prop_id == PCO_PROPERTY_WIDTH or prop_id == "width":
            return self._image_width
        elif prop_id == PCO_PROPERTY_HEIGHT or prop_id == "height":
            return self._image_height
        elif prop_id == PCO_PROPERTY_FPS or prop_id == "fps":
            if self._actual_camera_properties:
                return self._actual_camera_properties.fps
            return None
        # Add more property mappings here using PCO SDK Get functions
        elif prop_id == "offsetX" or prop_id == "offsetY":
            # For ROI, retrieve current ROI and return x0 or y0
            x0, y0, x1, y1 = WORD(), WORD(), WORD(), WORD()
            result = pcosdk.PCO_GetROI(self.pco_cam_handle, ctypes.byref(x0), ctypes.byref(y0), ctypes.byref(x1), ctypes.byref(y1))
            if self._check_error(result, "PCO_GetROI"):
                if prop_id == "offsetX": return x0.value
                if prop_id == "offsetY": return y0.value
            return None
        # Add a way to get 'brightness' if PCO cameras support an equivalent.
        # This would typically be gain or exposure, which PCO SDK has functions for.
        # Example (conceptual):
        # elif prop_id == "brightness":
        #    # Look up PCO_GetGain or similar, map to a 0-100 range if needed
        #    return current_gain_value
        else:
            self.print(f"Unsupported property ID: {prop_id}")
            return None

    def set_property(self, prop_id: Union[int, str], value: Union[float, int]) -> bool:
        if not self.is_opened():
            return False

        success = False
        if prop_id == PCO_PROPERTY_WIDTH or prop_id == "width" or \
           prop_id == PCO_PROPERTY_HEIGHT or prop_id == "height" or \
           prop_id == "offsetX" or prop_id == "offsetY":
            # Setting width/height/offset requires re-setting ROI and re-arming
            # This is complex as it requires current ROI values.
            # Best practice: get current ROI, modify it, set new ROI, then re-arm.
            x0, y0, x1, y1 = WORD(), WORD(), WORD(), WORD()
            result_get = pcosdk.PCO_GetROI(self.pco_cam_handle, ctypes.byref(x0), ctypes.byref(y0), ctypes.byref(x1), ctypes.byref(y1))
            if not self._check_error(result_get, "PCO_GetROI"):
                return False

            new_x0, new_y0, new_x1, new_y1 = x0.value, y0.value, x1.value, y1.value

            if prop_id == "width":
                new_x1 = new_x0 + int(value) - 1
            elif prop_id == "height":
                new_y1 = new_y0 + int(value) - 1
            elif prop_id == "offsetX":
                new_x0 = int(value)
                new_x1 = new_x0 + (x1.value - x0.value) # Maintain width
            elif prop_id == "offsetY":
                new_y0 = int(value)
                new_y1 = new_y0 + (y1.value - y0.value) # Maintain height

            result_set = pcosdk.PCO_SetROI(self.pco_cam_handle, WORD(new_x0), WORD(new_y0), WORD(new_x1), WORD(new_y1))
            success = self._check_error(result_set, "PCO_SetROI")
            if success:
                # Re-arm camera after changing resolution/ROI
                result_arm = pcosdk.PCO_ArmCamera(self.pco_cam_handle)
                success = self._check_error(result_arm, "PCO_ArmCamera (after set_property)")
                if success and self._buffer_allocated:
                    # If buffers were already allocated, they need to be re-allocated for new size
                    self.print("ROI/resolution changed. Re-allocating buffers.")
                    self._free_buffers_internal() # Free old buffers
                    self._image_width = new_x1 - new_x0 + 1
                    self._image_height = new_y1 - new_y0 + 1
                    self._allocate_buffers() # Allocate new ones
                    if self._actual_camera_properties:
                        self._actual_camera_properties.width = self._image_width
                        self._actual_camera_properties.height = self._image_height
                        self._actual_camera_properties.offsetX = new_x0
                        self._actual_camera_properties.offsetY = new_y0

        elif prop_id == PCO_PROPERTY_FPS or prop_id == "fps":
            timing_struct = PCO_Timing(wSize=ctypes.sizeof(PCO_Timing))
            # Get current timing to preserve other settings if any
            result_get_timing = pcosdk.PCO_GetFrameRate(self.pco_cam_handle, ctypes.byref(timing_struct))
            if self._check_error(result_get_timing, "PCO_GetFrameRate"):
                # Convert desired FPS to PCO timing units (period, timebase)
                if value > 0:
                    period_us = int(1_000_000 / value)
                    timing_struct.dwPeriod = DWORD(period_us)
                    timing_struct.wTimeBasePeriod = WORD(1) # Microseconds

                    result_set = pcosdk.PCO_SetFrameRate(self.pco_cam_handle, ctypes.byref(timing_struct))
                    success = self._check_error(result_set, "PCO_SetFrameRate")
                    if success:
                        result_arm = pcosdk.PCO_ArmCamera(self.pco_cam_handle)
                        success = self._check_error(result_arm, "PCO_ArmCamera (after set_property)")
                        if success and self._actual_camera_properties:
                            self._actual_camera_properties.fps = value # Update cached value
                else:
                    self.print(f"Invalid FPS value: {value}. Must be > 0.")
                    success = False
            else:
                self.print("Could not get current frame rate to set desired FPS.")
                success = False

        # Add more property mappings here using PCO SDK Set functions
        # Example (conceptual):
        # elif prop_id == "brightness":
        #     # Look up PCO_SetGain or similar
        #     result = pcosdk.PCO_SetGain(self.pco_cam_handle, WORD(value))
        #     success = self._check_error(result, "PCO_SetGain")
        else:
            self.print(f"Unsupported property ID for setting: {prop_id}")
            success = False

        return success

    def _free_buffers_internal(self):
        """Internal helper to free buffers without full camera release."""
        for buf_nr, _, _, _ in self._buffer_info:
            result_free = pcosdk.PCO_FreeBuffer(self.pco_cam_handle, ctypes.c_int(buf_nr))
            self._check_error(result_free, f"PCO_FreeBuffer (internal for buffer {buf_nr})")
            self.print(f"Internally freed buffer {buf_nr}.")
        self._buffer_info = []
        self._buffer_allocated = False

    def print(self, s: str):
        print(f"PCO Grabber: {s}")

# Example Usage (for testing purposes, not part of the class itself)
if __name__ == "__main__":
    grabber = PCOCameraGrabber()

    # 1. Detect cameras
    cameras = grabber.detect_cameras()
    if not cameras:
        print("No PCO cameras detected.")
    else:
        print(f"Detected PCO Cameras: {cameras}")
        camera_to_open = cameras[0] # Try to open the first detected camera

        # 2. Open camera with desired properties
        desired_props = CameraProperties(width=1024, height=768, fps=10) # Example: desire 1024x768 at 10 FPS
        actual_props = grabber.open(camera_to_open, desired_props)

        if grabber.is_opened():
            print(f"Camera successfully opened with actual properties: {actual_props}")

            # 3. Get properties
            current_width = grabber.get_property("width")
            current_fps = grabber.get_property("fps")
            print(f"Current width: {current_width}, FPS: {current_fps}")

            # 4. Set a property (e.g., change FPS)
            if grabber.set_property("fps", 5): # Try to set FPS to 5
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

            # 6. Set another property (e.g., change ROI/resolution)
            if actual_props.width > 500 and actual_props.height > 500:
                print(f"Attempting to set ROI to (100, 100) with 500x500 resolution...")
                grabber.set_property("offsetX", 100)
                grabber.set_property("offsetY", 100)
                grabber.set_property("width", 500)
                grabber.set_property("height", 500)
                print(f"New resolution after setting ROI: {grabber.get_property('width')}x{grabber.get_property('height')}")

                print("Grabbing 2 more frames with new ROI...")
                for i in range(2):
                    frame_data = grabber.get_frame()
                    if frame_data:
                        frame = frame_data['frame']
                        print(f"Frame (new ROI) {i+1} grabbed: shape {frame.shape}, dtype {frame.dtype}")
                        # import cv2
                        # cv2.imshow(f"PCO New ROI Frame {i}", frame)
                        # cv2.waitKey(1)
                    time.sleep(0.1)

            # 7. Release camera
            grabber.release()
            print("Camera released.")
        else:
            print("Failed to open PCO camera.")