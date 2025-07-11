import datetime
from typing import Union, TextIO


class TimestampWriter:
    """
    A class for writing timestamps to a text file in a specified format.
    The file is opened during initialization and timestamps can be provided
    as strings or datetime objects.
    """

    def __init__(self, file_path: str, format_string: str = "%Y-%m-%d %H:%M:%S.%f", enforce_str_input_format: bool=False):
        """
        Initializes the TimestampWriter.

        Args:
            file_path (str): The path to the text file where timestamps will be written.
            format_string (str, optional): The datetime format string to use.
                                           Defaults to "%Y-%m-%d %H:%M:%S.%f".
                                           (e.g., "YYYY-MM-DD HH:MM:SS.microseconds")
                                           For more format codes, refer to
                                           https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
            enforce_str_input_format (bool): Enforce the format on inputs provided by strings (always True for datetime inputs)
        """
        self.file_path = file_path
        self.format_string = format_string
        self.enforce_str_input_format = enforce_str_input_format
        self.file_handle: TextIO = open(file_path, 'a')  # Open in append mode

    def write(self, timestamp: Union[str, datetime.datetime]):
        """
        Writes a timestamp to the file.

        Args:
            timestamp (Union[str, datetime.datetime]): The timestamp to write.
                                                       Can be a string or a datetime object.
        Raises:
            ValueError: If the input timestamp string cannot be parsed into a datetime object.
        """
        if isinstance(timestamp, str):
            if not self.enforce_str_input_format:
                formatted_timestamp = timestamp
            else:
                try:
                    dt_object = datetime.datetime.fromisoformat(timestamp)
                    # Attempt to parse as ISO format first for common cases.
                    # If that fails, or if the string isn't exactly ISO,
                    # the user might expect a different parsing. For more robust string
                    # parsing, especially if the string format varies, consider
                    # using a library like 'dateutil.parser.parse'.
                except ValueError:
                    # If fromisoformat fails, try to parse it with the specified format_string.
                    # This assumes the input string *might* match the output format.
                    # A more robust solution for arbitrary string inputs might involve
                    # more sophisticated parsing or requiring a datetime object as input.
                    try:
                        dt_object = datetime.datetime.strptime(timestamp, self.format_string)
                    except ValueError as e:
                        raise ValueError(f"Could not parse timestamp string '{timestamp}' "
                                        f"with format '{self.format_string}' or as ISO format. Error: {e}") from e
                formatted_timestamp = dt_object.strftime(self.format_string)
                
        elif isinstance(timestamp, datetime.datetime):
            dt_object = timestamp
            formatted_timestamp = dt_object.strftime(self.format_string)
        else:
            raise TypeError("Timestamp must be a string or a datetime.datetime object.")

        self.file_handle.write(formatted_timestamp + "\n")
        self.file_handle.flush()  # Ensure the data is written to disk immediately

    def close(self):
        """ Closes the file handle. """
        if not self.file_handle.closed:
            self.file_handle.close()

    #### The 2 methods below allows using TimestampWriter's object in `with` statements: with TimestampWriter(..) as writer:... 
    def __enter__(self):
        """Context manager entry point. Called when with starts."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point, ensures the file is closed."""
        self.close()


# --- Example Usage ---
if __name__ == "__main__":
    output_file = "timestamps.txt"

    # Example 1: Using the class directly
    print(f"--- Example 1: Writing to {output_file} directly ---")
    writer1 = TimestampWriter(output_file, format_string="%Y-%m-%d %H:%M:%S")
    writer1.write_timestamp(datetime.datetime.now())
    writer1.write_timestamp("2024-01-15 10:30:00")
    writer1.write_timestamp(datetime.datetime(2023, 7, 1, 14, 25, 59, 123456))
    writer1.close()
    print(f"Check '{output_file}' for the written timestamps.")

    # Example 2: Using the class as a context manager (recommended for safety)
    print(f"\n--- Example 2: Writing to {output_file} using a context manager ---")
    with TimestampWriter(output_file, format_string="%Y%m%d_%H%M%S") as writer2:
        writer2.write_timestamp(datetime.datetime.now())
        writer2.write_timestamp("2025-05-20_110000")
        # Simulate an external process providing timestamps
        for i in range(3):
            writer2.write_timestamp(datetime.datetime.now() + datetime.timedelta(seconds=i*10))
    print(f"Check '{output_file}' again for the new timestamps (appended).")

    # Example 3: Demonstrating error handling for invalid string format
    print(f"\n--- Example 3: Demonstrating error handling ---")
    try:
        with TimestampWriter(output_file) as writer3:
            writer3.write_timestamp("this is not a timestamp")
    except ValueError as e:
        print(f"Caught expected error: {e}")

    # You can inspect the content of the file
    print(f"\nContents of '{output_file}':")
    with open(output_file, 'r') as f:
        print(f.read())