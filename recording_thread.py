import cv2
import numpy as np
import time
import os
import collections

# --- CORRECTED: Changed from PyQt6.QtCore to PyQt5.QtCore ---
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

class RecordingThread(QThread):
    recording_status_changed = pyqtSignal(bool, bool) # is_recording, is_paused
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._is_paused = False
        self._frame_queue = collections.deque()
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()
        self._video_writer = None
        self._output_path = ""
        self._width = 0
        self._height = 0
        self._fps = 0
        self._start_time = 0
        self._pause_time = 0
        self._elapsed_paused_time = 0

        print("RecordingThread: Not currently recording.")


    def set_video_properties(self, width: int, height: int, fps: float):
        self._mutex.lock()
        self._width = width
        self._height = height
        self._fps = fps
        print(f"RecordingThread: Video properties set to {width}x{height}@{fps}fps")
        self._mutex.unlock()

    def is_video_properties_set(self) -> bool:
        return self._width > 0 and self._height > 0 and self._fps > 0

    def start_recording(self, output_path: str) -> bool:
        self._mutex.lock()
        if self._is_recording:
            self._mutex.unlock()
            return False

        if not self.is_video_properties_set():
            self._mutex.unlock()
            self.error_occurred.emit("Video properties not set. Cannot start recording.")
            return False

        self._output_path = output_path
        
        # Define the codec and create VideoWriter object
        # For .mp4 (H.264), 'mp4v' or 'XVID' can be used widely. 'avc1' is also common.
        # Ensure 'libx264' or 'XVID' codec is available in your OpenCV build.
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        
        try:
            self._video_writer = cv2.VideoWriter(
                self._output_path, 
                fourcc, 
                self._fps, 
                (self._width, self._height)
            )
            if not self._video_writer.isOpened():
                raise IOError(f"VideoWriter could not be opened for path: {output_path}. Check codec support or path.")
        except Exception as e:
            self._mutex.unlock()
            self.error_occurred.emit(f"Failed to initialize video writer: {e}")
            return False

        self._is_recording = True
        self._is_paused = False
        self._start_time = time.time()
        self._elapsed_paused_time = 0
        self._frame_queue.clear() # Clear any old frames
        self.start() # Start the QThread's run method
        self._mutex.unlock()
        self.recording_status_changed.emit(True, False)
        print(f"RecordingThread: Started recording to {output_path}")
        return True

    def pause_recording(self):
        self._mutex.lock()
        if self._is_recording and not self._is_paused:
            self._is_paused = True
            self._pause_time = time.time()
            self.recording_status_changed.emit(True, True)
            print("RecordingThread: Paused.")
        self._mutex.unlock()

    def resume_recording(self):
        self._mutex.lock()
        if self._is_recording and self._is_paused:
            self._is_paused = False
            self._elapsed_paused_time += (time.time() - self._pause_time)
            self._wait_condition.wakeAll() # Wake up the writing thread
            self.recording_status_changed.emit(True, False)
            print("RecordingThread: Resumed.")
        self._mutex.unlock()

    def stop_recording(self) -> bool:
        self._mutex.lock()
        if not self._is_recording:
            self._mutex.unlock()
            return False

        self._is_recording = False
        self._is_paused = False
        self._wait_condition.wakeAll() # Wake up the writing thread to finish up
        self._mutex.unlock()
        self.wait() # Wait for the run loop to finish
        
        self._release_writer()
        self._frame_queue.clear()
        self.recording_status_changed.emit(False, False)
        print("RecordingThread: Stopped recording.")
        return True

    def enqueue_frame(self, frame: np.ndarray):
        self._mutex.lock()
        if self._is_recording and not self._is_paused:
            self._frame_queue.append(frame)
            self._wait_condition.wakeOne() # Wake one waiting thread (the run method)
        self._mutex.unlock()

    def is_recording(self) -> bool:
        self._mutex.lock()
        status = self._is_recording
        self._mutex.unlock()
        return status

    def is_paused(self) -> bool:
        self._mutex.lock()
        status = self._is_paused
        self._mutex.unlock()
        return status
    
    def is_recording_active(self) -> bool:
        """Returns True if recording is active (started and not stopped), even if paused."""
        self._mutex.lock()
        status = self._is_recording
        self._mutex.unlock()
        return status

    def get_elapsed_time(self) -> float:
        self._mutex.lock()
        if self._is_recording:
            if self._is_paused:
                elapsed = (self._pause_time - self._start_time) - self._elapsed_paused_time
            else:
                elapsed = (time.time() - self._start_time) - self._elapsed_paused_time
        else:
            elapsed = 0
        self._mutex.unlock()
        return elapsed


    def run(self):
        while True:
            self._mutex.lock()
            while self._is_recording and self._is_paused:
                self._wait_condition.wait(self._mutex) # Release mutex and wait
            
            if not self._is_recording and not self._frame_queue: # Ensure queue is empty before exiting
                self._mutex.unlock()
                break # Exit thread cleanly

            if self._frame_queue:
                frame = self._frame_queue.popleft()
                self._mutex.unlock() # Release mutex while writing frame (can be time-consuming)
                if self._video_writer and self._video_writer.isOpened():
                    try:
                        self._video_writer.write(frame)
                    except Exception as e:
                        self.error_occurred.emit(f"Error writing frame to video file: {e}")
                        self.stop_recording() # Attempt to stop on error
            else:
                self._mutex.unlock()
                time.sleep(0.001) # Small sleep if queue is empty to avoid busy-waiting

        print("RecordingThread: run method finished.") # Indicate run loop completion

    def _release_writer(self):
        if self._video_writer:
            if self._video_writer.isOpened():
                self._video_writer.release()
                print("RecordingThread: Video writer released.")
            self._video_writer = None

    def __del__(self):
        self.wait() # Ensure the thread finishes its execution
        self._release_writer()