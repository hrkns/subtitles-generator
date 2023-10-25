import logging
import os
import sys
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

logging.basicConfig(level=logging.INFO)

def validate_audio_file(file_path):
    # TODO: Expand validation to support more audio formats.
    if not os.path.exists(file_path):
        logging.error("The provided audio file does not exist.")
        sys.exit(1)

    if not file_path.lower().endswith('.mp3'):
        logging.error("Unsupported file format. Currently only MP3 is supported.")
        sys.exit(1)

    try:
        audio = AudioSegment.from_mp3(file_path)
        return audio
    except CouldntDecodeError:
        logging.error("Could not decode audio file. Please ensure it's a valid MP3 file.")
        sys.exit(1)
