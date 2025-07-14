import cv2
import os
import sys
import datetime
import numpy as np
import traceback
from typing import List, Union, Optional, Dict
from ..camera_interface import CameraGrabberInterface, CameraProperties

class CameraGrabberInterface(CameraGrabberInterface):
    def __init__(self):
        self._is_opened = False
        self._actual_camera_properties: Optional[CameraProperties] = None

# OpenCVVideoGrabber
class FileStreaming(CameraGrabberInterface):
    def __init__(self):
        super().__init__()
        self._video_capture: Optional[cv2.VideoCapture] = None
        self._video_path: Optional[str] = None

    def detect_cameras(self) -> List[str]:
        """
        For video files, this method would typically just return a placeholder or
        expect the video path to be known beforehand. We'll return an empty list
        as we don't 'detect' video files in the same way we detect cameras.
        """
        print("Note: detect_cameras is not applicable for video file grabbers.")
        return []

    def open(self, video_path: str, desired_props: CameraProperties = CameraProperties()) -> CameraProperties:
        """
        Opens the video file specified by video_path.
        try/except handling is supposed to be done in the calling script.
        """
        self._video_path = video_path
        self._video_path = r"C:\Users\MaxD2b\Downloads\output.avi"
        print(f"...... self._video_path: {self._video_path}, desired_props: {desired_props}")
        if type(self._video_path) is not str:
            raise TypeError(f"video_path argument must be a string. Provided: {self._video_path}")
        if not os.path.exists(self._video_path):
            # self.print(f"Error: Video file not found at {self._video_path}")
            raise FileNotFoundError(f"Video file does not exist: {self._video_path}")
        if not os.path.isfile(self._video_path):
            # self.print(f"Error: Path is not a file: {self._video_path}")
            raise IsADirectoryError(f"Path is a directory, not a file: {self._video_path}")
        self._video_capture = cv2.VideoCapture(self._video_path)
        if not self._video_capture.isOpened():
            self._is_opened = False
            self._actual_camera_properties = None
            raise IOError(f"Could not open video file: {self._video_path}")

        self._is_opened = True

        # Look for the timestamp file accompanying the video file
        

        # Get actual properties
        actual_width = int(self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._video_capture.get(cv2.CAP_PROP_FPS)

        self._actual_camera_properties = CameraProperties(
            width=actual_width,
            height=actual_height,
            fps=actual_fps,
            # Brightness, offsetX, offsetY are generally not applicable for video files
            brightness=-1,
            offsetX=0,
            offsetY=0,
            other={'video_path': self._video_path}
        )
        self.print(f"........ actual props : {self._actual_camera_properties}")
        return self._actual_camera_properties

    def is_opened(self) -> bool:
        """Returns True if the video file is currently opened."""
        return self._is_opened and self._video_capture is not None and self._video_capture.isOpened()

    def get_frame(self) -> Union[None, dict]:
        """
        Grabs a single frame from the video file.
        Returns a dictionary containing the numpy array (image) and timestamp.
        Returns None if no more frames can be grabbed.
        """
        if not self.is_opened():
            return None

        ret, frame = self._video_capture.read()
        if ret:
            timestamp_ms = self.get_time_stamp()
            # Convert milliseconds to datetime object
            timestamp = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0)
            return {'frame': frame, 'timestamp': timestamp}
        else:
            return None
        
    def get_time_stamp(self):
        # get the timestamp either from the video file,
        # or from the accompaning text file with the timestamps, generated along with recording the video
        # !#fix
        timestamp_ms = self._video_capture.get(cv2.CAP_PROP_POS_MSEC)
        return timestamp_ms

    def release(self):
        """Releases the video capture object and its resources."""
        if self._video_capture:
            self._video_capture.release()
        self._is_opened = False
        self._actual_camera_properties = None
        self._video_path = None

    def get_property(self, prop_id: Union[int, str]) -> Union[float, int, None]:
        """
        Gets a video property.
        prop_id can be an OpenCV CAP_PROP_* constant.
        """
        if not self.is_opened():
            return None
        if isinstance(prop_id, int):
            return self._video_capture.get(prop_id)
        elif isinstance(prop_id, str):
            # You can map string names to CAP_PROP_ constants if needed
            if prop_id == 'width':
                return self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            elif prop_id == 'height':
                return self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            elif prop_id == 'fps':
                return self._video_capture.get(cv2.CAP_PROP_FPS)
            elif prop_id == 'frame_count':
                return self._video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
            elif prop_id == 'pos_msec':
                return self._video_capture.get(cv2.CAP_PROP_POS_MSEC)
            else:
                print(f"Warning: Custom property '{prop_id}' not supported.")
                return None
        return None

    def set_property(self, prop_id: Union[int, str], value: Union[float, int]) -> bool:
        """
        Sets a video property.
        For video files, many properties are read-only.
        Returns True on success, False otherwise.
        """
        if not self.is_opened():
            return False
        if isinstance(prop_id, int):
            # Some properties like current position can be set
            return self._video_capture.set(prop_id, value)
        elif isinstance(prop_id, str):
            if prop_id == 'pos_frames':
                return self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, value)
            elif prop_id == 'pos_msec':
                return self._video_capture.set(cv2.CAP_PROP_POS_MSEC, value)
            else:
                print(f"Warning: Setting custom property '{prop_id}' not supported or read-only for video files.")
                return False
        return False
    
    def print(self, s):
        print(f"file_streamer: {s}")