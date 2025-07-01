import abc
import dataclasses
# --- Added List from typing module ---
from typing import List, Union, Optional, Dict


@dataclasses.dataclass
class CameraProperties:
    width: int
    height: int
    fps: float
    brightness: int # Using -1 to indicate not supported or not set for brightness
    offsetX : int = 0
    offsetY : int = 0
    other : Dict[str, str] = dataclasses.field(default_factory=dict)



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
    def open(self, index: int, desired_props: CameraProperties) -> CameraProperties:
        """
        Opens the camera at the given index with desired properties and
        returns the actual properties achieved by the camera.
        """
        pass

    @abc.abstractmethod
    def is_opened(self) -> bool:
        """Returns True if the camera is currently opened."""
        pass

    @abc.abstractmethod
    def get_frame(self) -> Union[None, 'numpy.ndarray']: # Type hint for numpy.ndarray
        """
        Grabs a single frame from the camera.
        Returns a numpy array (image) or None if a frame cannot be grabbed.
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