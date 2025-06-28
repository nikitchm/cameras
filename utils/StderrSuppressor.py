import os
import sys

class StderrSuppressor:
    """
    A context manager to temporarily suppress output to stderr by redirecting
    its file descriptor to os.devnull.

    Usage:
    with StderrSuppressor():
        # Code that generates C++ stderr output
        pass
    """
    def __enter__(self):
        """
        Redirects stderr to os.devnull.
        """
        # Save a reference to the original stderr file descriptor
        self._original_stderr_fd = sys.stderr.fileno()
        
        # Open a null device to redirect stderr to
        self._null_fd = os.open(os.devnull, os.O_WRONLY)

        # Duplicate the original stderr_fd to a new file descriptor (_old_stderr_dup)
        # This allows us to restore it later.
        self._old_stderr_dup = os.dup(self._original_stderr_fd) 
        
        # Redirect stderr (file descriptor 2) to the null device's file descriptor.
        os.dup2(self._null_fd, self._original_stderr_fd) 
        os.close(self._null_fd) # Close the null_fd, as original_stderr_fd now points to it

        # Store the original sys.stderr Python object as well, just in case
        # it was modified or replaced by some library (less common after dup2, but safer)
        self._original_sys_stderr = sys.stderr
        
        # Re-assign sys.stderr to a new object associated with the now-redirected fd
        # This might be important if other Python code explicitly uses the sys.stderr object.
        sys.stderr = os.fdopen(self._original_stderr_fd, 'w')


    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Restores the original stderr.
        """
        # Restore the original stderr file descriptor.
        os.dup2(self._old_stderr_dup, self._original_stderr_fd)
        os.close(self._old_stderr_dup) # Close the duplicated file descriptor.
        
        # Restore the original sys.stderr Python object.
        sys.stderr = self._original_sys_stderr

        # Return False to propagate any exceptions that occurred within the 'with' block
        return False 