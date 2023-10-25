import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)

def validate_output(path):
    """
    Validate the provided path depending on whether it's an SRT file or a directory.

    :param path: Path to the SRT file or directory.
    :type path: str
    :return: True if the destination location exists (and warns about potential overwrite); False if output directory doesn't exist.
    :rtype: bool
    """
    if not path:
        raise ValueError("Output path must not be empty")

    # Check if path is a directory or a file
    if os.path.isdir(path):
        # The path is a directory; check if it exists
        if os.path.exists(path):
            return os.path.join(path, "output.srt")
        else:
            raise Exception(f"Output directory does not exist: {path}")
    else:
        # Expecting the path to be an SRT file from this point onwards
        if not path.lower().endswith('.srt'):
            raise ValueError("Invalid output file type. Please provide a path to an '.srt' file.")

        # Determine the output directory
        output_directory = os.path.dirname(path)

        # Check if the output directory exists
        if not os.path.exists(output_directory):
            raise Exception(f"Output directory does not exist: {path}")

        # Check if the file itself exists
        if os.path.exists(path):
            logging.warning(f"The file {path} already exists and will be overwritten.")

        return path
