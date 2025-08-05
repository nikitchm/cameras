import abc
import dataclasses
# --- Added List from typing module ---
from typing import List, Union, Optional, Dict, Type, TypeVar
import numpy as np
from PyQt5.QtWidgets import QDialog

@dataclasses.dataclass
class CameraProperties:
    width: int = 0
    height: int = 0
    fps: float = 0
    brightness: int = 0 # Using -1 to indicate not supported or not set for brightness
    offsetX : int = 0
    offsetY : int = 0
    other : Dict[str, str] = dataclasses.field(default_factory=dict)

@dataclasses.dataclass
class Grabber:
    """
    This class describes the properties of a particular grabber, s.a., FileStreamer, Opencv, or PyCapture2
    """
    class KNOWN_GRABBERS:               # nicknames for the grabbers. Allow comparing strings via . calls.
        File = "file"
        OPENCV = "opencv"
        PyCapture2 = "pycapture2"
        PCO = "pco"
    cls: Type["CameraGrabberInterface"] = None  # Use Type for class reference. We 
    cls_name: KNOWN_GRABBERS = None
    cam_settings_wnd: Type[QDialog] = None      # Use Type for class reference
    settings: CameraProperties = CameraProperties()           # default settings for different cameras of this grabber
    obj: "CameraGrabberInterface" = None

@dataclasses.dataclass
class Source(Grabber):
    id  : Union[int, str] = None        # The id of the camera by which it's recognized by a particular grabber
    name: str = ""                      # Colloquial name of the frame grabber 


class CameraGrabberInterface(abc.ABC):
    def __init__(self):
        self._is_opened = False
        self._actual_camera_properties: Optional[CameraProperties] = None # Using Optional for clarity

    @abc.abstractmethod
    def detect_cameras(self) -> List[str]:
        """
        Detects available cameras and returns a list of their identifiers.
        E.g., ["Camera 0", "Camera 1"] for OpenCV, or unique names for PyCapture2.
        """
        pass

    @abc.abstractmethod
    # def open(self, src: Source = Source()) -> Source:
    def open(self, src: Source) -> Source:
        """
        Opens the camera defined by the `src` and returns the updated src. 
        """
        pass

    @abc.abstractmethod
    def is_opened(self) -> bool:
        """Returns True if the camera is currently opened."""
        pass

    @abc.abstractmethod
    def get_frame(self) -> Union[None, dict]: # Type hint for np.ndarray
        """
        Grabs a single frame from the camera.
        Returns a dictionary containing the numpy array (image), timestamp, and anything else
        (['frame':'np.ndarray', 'timestamp':'datetime.datetime']) or None if a frame cannot be grabbed.
        """
        pass

    @abc.abstractmethod
    def release(self):
        """Releases the camera and its resources."""
        pass

    @abc.abstractmethod
    def get_property(self, prop_id: Union[int, str]) -> Union[float, int, None]:
        """
        Gets a camera property.
        prop_id can be an OpenCV CAP_PROP_* constant or a string for custom properties.
        """
        pass

    @abc.abstractmethod
    def set_property(self, prop_id: Union[int, str], value: Union[float, int]) -> bool:
        """
        Sets a camera property.
        prop_id can be an OpenCV CAP_PROP_* constant or a string for custom properties.
        Returns True on success, False otherwise.
        """
        pass