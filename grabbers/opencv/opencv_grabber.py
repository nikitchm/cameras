import cv2
import numpy as np
from ..camera_interface import CameraGrabberInterface, CameraProperties
from typing import List, Tuple, Union

class OpenCVCapture(CameraGrabberInterface):
    """
    Implements CameraGrabberInterface using OpenCV's VideoCapture.
    Handles camera opening, frame grabbing, and property setting.
    """
    def __init__(self):
        self.cap: Union[cv2.VideoCapture, None] = None
        self._camera_index: int = -1

    def open(self, camera_index: int, desired_props: CameraProperties = None) -> CameraProperties:
        """
        Opens the camera specified by index with desired properties.
        Attempts to use DSHOW backend first, then falls back to MSMF.
        Returns the actual properties the camera was opened with.
        """
        self._camera_index = camera_index
        
        # Release any previously opened camera
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None

        actual_props = CameraProperties(0, 0, 0, 0, 0.0, -1) # Default empty properties

        # FIX: Try opening with CAP_DSHOW backend first
        print(f"OpenCVCapture: Attempting to open camera {camera_index} with CAP_DSHOW backend.")
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            print(f"OpenCVCapture: CAP_DSHOW failed for camera {camera_index}. Trying CAP_MSMF backend.")
            # Fallback to MSMF if DSHOW fails
            if self.cap: # Ensure it's not None from previous failed attempt
                self.cap.release()
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)

        if self.cap.isOpened():
            print(f"OpenCVCapture: Camera {camera_index} opened successfully.")
            # Apply desired properties
            if desired_props:
                if desired_props.width > 0:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, desired_props.width)
                if desired_props.height > 0:
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, desired_props.height)
                if desired_props.fps > 0:
                    self.cap.set(cv2.CAP_PROP_FPS, desired_props.fps)
                if desired_props.brightness != -1:
                    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, desired_props.brightness)

            # Get actual properties after opening and setting
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            actual_brightness = int(self.cap.get(cv2.CAP_PROP_BRIGHTNESS))

            # Handle cases where FPS might be reported as 0.0
            if actual_fps == 0.0:
                actual_fps = desired_props.fps if desired_props.fps > 0 else 30.0 # Default to 30 if still 0 or unset

            actual_props = CameraProperties(actual_width, actual_height, 0, 0, actual_fps, actual_brightness)
            print(f"OpenCVCapture: Actual Props: {actual_props}")
        else:
            print(f"OpenCVCapture: Failed to open camera {camera_index} with any backend.")
            self.release() # Ensure release if opening failed
            
        return actual_props

    def get_frame(self) -> Union[np.ndarray, None]:
        """Grabs a single frame from the camera."""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                return frame
            print(f"OpenCVCapture: Failed to read frame from camera {self._camera_index}.")
        return None

    def release(self):
        """Releases the camera resource."""
        if self.cap:
            self.cap.release()
            self.cap = None
            print(f"OpenCVCapture: Camera {self._camera_index} released.")

    def is_opened(self) -> bool:
        """Checks if the camera is currently opened."""
        return self.cap is not None and self.cap.isOpened()

    def get_property(self, prop_id: int) -> Union[float, None]:
        """Gets a camera property by its ID."""
        if self.cap and self.cap.isOpened():
            return self.cap.get(prop_id)
        return None

    def set_property(self, prop_id: int, value: Union[int, float]) -> bool:
        """Sets a camera property by its ID."""
        if self.cap and self.cap.isOpened():
            return self.cap.set(prop_id, value)
        return False

    def detect_cameras(self) -> List[str]:
        """
        Detects available cameras and returns a list of their names (e.g., "Camera 0").
        Prioritizes DSHOW for detection for robustness, then MSMF.
        Stops early on consecutive failures.
        """
        detected_camera_names = []
        max_cameras_to_check = 10 # Still keep a reasonable upper bound for detection
        consecutive_failures = 0
        max_consecutive_failures = 3 # Stop after this many consecutive failed attempts

        print("Detecting cameras...")
        for i in range(max_cameras_to_check):
            cap = None
            is_opened_successfully_this_attempt = False
            try:
                # Try DSHOW first for detection (often more reliable for simple open/close checks)
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    detected_camera_names.append(f"Camera {i}") # Just add the number, backend preference is for 'open'
                    # print(f"Detected Camera {i} using DSHOW (for detection).")
                    is_opened_successfully_this_attempt = True
                    consecutive_failures = 0 # Reset counter on success
                    cap.release()
                    continue # Move to next index if successful

                # If DSHOW fails, try MSMF for detection
                if cap: # Ensure release even if DSHOW failed
                    cap.release()
                cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
                if cap.isOpened():
                    detected_camera_names.append(f"Camera {i}") # Just add the number
                    # print(f"Detected Camera {i} using MSMF (for detection).")
                    is_opened_successfully_this_attempt = True
                    consecutive_failures = 0 # Reset counter on success
                    cap.release()
                else:
                    # Both DSHOW and MSMF failed for this index
                    consecutive_failures += 1 # Increment failure counter
                    if cap: # Ensure release if MSMF also failed
                        cap.release()

            except cv2.error as e:
                # print(f"Warning: OpenCV error during camera detection for index {i}: {e}")
                consecutive_failures += 1 # Increment failure counter
                if cap:
                    cap.release()
            except Exception as e:
                # print(f"Warning: General error during camera detection for index {i}: {e}")
                consecutive_failures += 1 # Increment failure counter
                if cap:
                    cap.release()
            finally:
                # Ensure any remaining unreleased cap is handled
                if cap and not is_opened_successfully_this_attempt:
                    cap.release()

            if consecutive_failures >= max_consecutive_failures:
                print(f"Stopping camera detection after {max_consecutive_failures} consecutive failures.")
                break # Break the loop if too many failures

        print("Camera detection complete.")
        return detected_camera_names