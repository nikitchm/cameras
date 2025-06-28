import numpy as np
import win32api
import win32con
import win32file  # Correct module for file mapping functions
import win32event # Correct module for mutex functions
import struct
import time

class SharedMemoryFrameSender:
    """
    Manages a Memory-Mapped File (MMF) to share NumPy array frames
    and a named Mutex for synchronization on Windows.
    """
    def __init__(self, name: str, mutex_name: str, max_buffer_size: int):
        self.name = name
        self.mutex_name = mutex_name
        self.max_buffer_size = max_buffer_size
        self.mmf_handle = None
        self.mmf_view = None
        self.mutex_handle = None
        self.is_initialized = False

        self._create_shared_memory()

    def _create_shared_memory(self):
        try:
            self.header_size = struct.calcsize("IIII") # Width, Height, Channels, Frame ID

            # Corrected: Use win32file.CreateFileMapping
            self.mmf_handle = win32file.CreateFileMapping(
                win32file.INVALID_HANDLE_VALUE,  # Use pagefile for anonymous mapping
                None,  # Default security
                win32con.PAGE_READWRITE,  # Read/write access
                0, self.max_buffer_size + self.header_size, # Max size of the MMF
                self.name  # Name of the mapping object
            )

            # Corrected: Use win32file.MapViewOfFile
            self.mmf_view = win32file.MapViewOfFile(
                self.mmf_handle,
                win32con.FILE_MAP_ALL_ACCESS, # All access (read, write, copy)
                0, 0,  # Offset high, Offset low (start from beginning)
                self.max_buffer_size + self.header_size # Size of the view
            )

            # Correct: win32event.CreateMutex
            self.mutex_handle = win32event.CreateMutex(None, 0, self.mutex_name)

            self.is_initialized = True
            print(f"SharedMemoryFrameSender: MMF '{self.name}' and Mutex '{self.mutex_name}' created/opened successfully.")

        except Exception as e:
            print(f"SharedMemoryFrameSender Error: Failed to create MMF or Mutex: {e}")
            self.release() # Clean up any partially created resources

    def write_frame(self, frame: np.ndarray, frame_id: int = 0):
        """
        Writes a NumPy array frame into the shared memory.
        The frame should be a flattened byte array (e.g., from .tobytes()).
        Includes a simple header (width, height, channels, frame_id).
        """
        if not self.is_initialized or self.mmf_view is None or self.mutex_handle is None:
            return False

        # Ensure frame is C-contiguous for tobytes() efficiency
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)

        frame_bytes = frame.tobytes()
        frame_size = len(frame_bytes)

        if frame_size > self.max_buffer_size:
            print(f"SharedMemoryFrameSender Warning: Frame size {frame_size} exceeds max buffer size {self.max_buffer_size}. Not writing.")
            return False

        # Acquire the mutex to ensure exclusive access
        # Wait for 100ms (max_timeout) for the mutex. If it times out, skip writing this frame.
        # Correct: win32event.WaitForSingleObject
        wait_result = win32event.WaitForSingleObject(self.mutex_handle, 100) # 100ms timeout
        if wait_result == win32con.WAIT_OBJECT_0: # Mutex acquired
            try:
                # Write header (width, height, channels, frame_id)
                header_data = struct.pack("IIII", frame.shape[1], frame.shape[0], frame.shape[2] if frame.ndim == 3 else 1, frame_id)
                
                # Corrected: Use win32file.WriteFile for writing to the MMF view
                # The MMF view is essentially a file-like object returned by MapViewOfFile
                # The first argument to WriteFile is the handle/view, second is data, third is offset
                win32file.WriteFile(self.mmf_view, header_data, 0) # Write header at offset 0
                
                # Write frame data immediately after the header
                win32file.WriteFile(self.mmf_view, frame_bytes, self.header_size)

                # print(f"SharedMemoryFrameSender: Frame {frame_id} written to MMF. Size: {frame_size} bytes.")
                return True
            except Exception as e:
                print(f"SharedMemoryFrameSender Error: Failed to write frame to MMF: {e}")
                return False
            finally:
                # Corrected: Use win32event.ReleaseMutex
                win32event.ReleaseMutex(self.mutex_handle) # Release the mutex
        elif wait_result == win32con.WAIT_TIMEOUT:
            # print("SharedMemoryFrameSender Warning: Mutex acquisition timed out. Skipping frame write.")
            return False
        else:
            print(f"SharedMemoryFrameSender Error: Mutex acquisition failed with code {wait_result}")
            return False

    def release(self):
        """
        Releases the shared memory and mutex resources.
        """
        if self.mmf_view:
            try:
                # Corrected: Use win32file.UnmapViewOfFile
                win32file.UnmapViewOfFile(self.mmf_view)
                self.mmf_view = None
                # print(f"SharedMemoryFrameSender: Unmapped view for '{self.name}'.")
            except Exception as e:
                print(f"SharedMemoryFrameSender Error: Failed to unmap view: {e}")
        
        if self.mmf_handle:
            try:
                # Correct: win32api.CloseHandle
                win32api.CloseHandle(self.mmf_handle)
                self.mmf_handle = None
                # print(f"SharedMemoryFrameSender: Closed handle for MMF '{self.name}'.")
            except Exception as e:
                print(f"SharedMemoryFrameSender Error: Failed to close MMF handle: {e}")
        
        if self.mutex_handle:
            try:
                # Correct: win32api.CloseHandle
                win32api.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
                # print(f"SharedMemoryFrameSender: Closed handle for Mutex '{self.mutex_name}'.")
            except Exception as e:
                print(f"SharedMemoryFrameSender Error: Failed to close Mutex handle: {e}")
        
        self.is_initialized = False
        print(f"SharedMemoryFrameSender: Resources for '{self.name}' released.")