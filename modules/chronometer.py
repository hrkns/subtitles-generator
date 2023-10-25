# chronometer.py
import time

def seconds_to_formatted_string(total_seconds):
    # Calculate the hours, minutes, and seconds.
    hours = total_seconds // 3600  # Note: // is the integer division operator.
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    # Construct the formatted string.
    formatted_string = ""

    # Add hours, if any.
    if hours > 0:
        formatted_string += f"{int(hours)} hours"

    # Add minutes, if any.
    if minutes > 0:
        # Add a comma if there are already hours specified.
        if formatted_string:
            formatted_string += ", "
        formatted_string += f"{int(minutes)} minutes"

    # Add seconds, if any.
    if seconds > 0 or (hours == 0 and minutes == 0):  # Add seconds if it's the only non-zero component.
        # Add a comma if there are already hours or minutes specified.
        if formatted_string:
            formatted_string += ", "
        formatted_string += f"{int(seconds)} seconds"

    # Return the final formatted string.
    return formatted_string

class Chronometer:
    def __init__(self):
        self._start_time = None
        self._end_time = None

    def start(self):
        """Start the chronometer."""
        self._start_time = time.time()
        self._end_time = None  # Reset end time if the chronometer is restarted.

    def stop(self):
        """Stop the chronometer."""
        if self._start_time is None:
            raise ValueError("You must start the chronometer before stopping it.")
        self._end_time = time.time()

    def get_duration(self):
        """Retrieve the total duration for which the chronometer ran."""
        if self._start_time is None:
            raise ValueError("You must start the chronometer before getting the duration.")
        if self._end_time is None:
            # If stop was not called, calculate the duration up to the current time.
            return time.time() - self._start_time
        # Otherwise, calculate the duration between start and stop times.
        return self._end_time - self._start_time

    def print_duration(self):
        """Print the duration in a human-readable format."""
        print(f"Total execution time: {seconds_to_formatted_string(self.get_duration())}")

