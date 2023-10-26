import datetime
import json
import logging
import os
import re
import sys
import magic
from moviepy.editor import AudioFileClip
import whisper_timestamped as whisper
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from config import TMP_DIR
from modules import convert_hhmmss_to_ms, format_ms_duration

# Set up logging
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

def is_video_file(file_path):
    """
    Check if the given file is a video by examining its content.

    :param file_path: str, path to the file.
    :return: bool, True if file is a video, False otherwise.
    """

    # First, check if the file exists.
    if not os.path.exists(file_path):
        print("File does not exist.")
        return False

    # Use python-magic to determine the file's mime type.
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(file_path)

    # Check the mime type for 'video'.
    if mime_type.startswith('video'):
        return True
    else:
        return False

def extract_audio(video_path, audio_path):
    """
    Extract the audio from a video file and save it as an audio file.

    :param video_path: str, The path to the video file.
    :param audio_path: str, The path to save the extracted audio file.
    """
    try:
        video = AudioFileClip(video_path)
        video.write_audiofile(audio_path)
        print(f"Audio extracted and saved to {audio_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def parse_segments(segments_str, total_duration_ms):
    segments = []

    if is_pattern(segments_str):
        segments = generate_segments_from_checkpoints(segments_str, total_duration_ms)
    else:
        segment_parts = segments_str.split(',')

        logging.info("Parsing segments...")
        for i, segment in enumerate(segment_parts, start=1):
            logging.info(f"{i}: {segment.strip()}")

        for index, segment in enumerate(segment_parts):
            segment = segment.strip()
            if index == 0 and segment.startswith(':'):
                # If the first segment starts with ':', it implies a start at 0.
                start_ms = 0
                end_str = segment.lstrip(':')  # Remove the ':' to get the end time.
                end_ms = convert_hhmmss_to_ms(end_str) if end_str else total_duration_ms  # If no end time, use the audio duration.
            else:
                start, sep, end = segment.partition('-')
                if not sep or not end:
                    # If the separator '-' is not found or the end is not defined, this segment is malformed (excluding the last segment).
                    if index == len(segment_parts) - 1 and not sep:
                        # For the last segment, if there is no '-', consider the whole part as the start.
                        start_ms = convert_hhmmss_to_ms(start)
                        end_ms = total_duration_ms  # The end of the last segment is the audio duration.
                    else:
                        raise ValueError(f"Segment {index + 1} is malformed, segments (except the first and last) must have both start and end defined.")
                else:
                    start_ms = convert_hhmmss_to_ms(start)
                    end_ms = convert_hhmmss_to_ms(end) if end else total_duration_ms  # If no end time, it's the audio duration.

            if end_ms < start_ms:
                raise ValueError(f"Segment {index + 1} ({segments_str[index + 1]}) is invalid as the end time is minor than the start time")

            segments.append((start_ms, end_ms))

        # After all segments are collected, check for order and overlap.

        previous_end = 0
        for index, (start, end) in enumerate(segments):
            if start < previous_end:
                # Segments are not in order if the current start is before the previous end.
                logging.warning(f"Segments are out of order. Segment {index + 1} ({segments_str[index]}) starts before the previous segment ends.")

            previous_end = end  # Update the end time marker for the next iteration.

        # Check for overlapping segments by comparing all pairs of segments.
        overlap_segments = []
        for i in range(len(segments)):
            for j in range(i+1, len(segments)):
                # Overlapping occurs if the start of one segment is between the start and end of another segment.
                if segments[j][0] < segments[i][1] and segments[i][0] < segments[j][1]:
                    overlap_segments.append((segments[i], segments[j]))
                    logging.warning(f"Segments {i+1} and {j+1} are overlapping.")

        # Optionally, you can handle or display overlapping segments.
        if overlap_segments:
            logging.warning(f"Overlapping segments detected: {overlap_segments}")

    return segments

def process_audio_segments(input_audio, segments_to_process, audio_language, speech_to_text_model, output_json_template):
    # This function assumes the existence of a 'whisper' module and 'model' variable.
    # These are not standard Python or known third-party libraries as of the last update in 2022.
    # Ensure your environment contains these, or replace them with the actual modules and methods you're using for audio processing.

    segment_number = 1

    for segment_to_process in segments_to_process:
        # Convert the checkpoint to milliseconds
        segment_start = segment_to_process[0]
        segment_end = segment_to_process[1]
        logging.info(f"Processing segment {segment_number} starting at {format_ms_duration(segment_start, use_separator=True)} and ending at {format_ms_duration(segment_end, use_separator=True)}")

        # Create the audio segment
        audio_segment = input_audio[segment_start:segment_end]

        # Save the audio segment to a temporary file
        # TODO: if a single segment is provided, don't create a temporary file, instead use the original input audio file directly, for optimization.
        logging.info("Creating tmp audio segment...")
        output_format = "mp3"
        temp_audio_file = f"{TMP_DIR}temp_segment_{segment_number}.{output_format}"
        audio_segment.export(temp_audio_file, format=output_format)
        logging.info("Created temporary audio segment.")

        # Transcribe the audio segment
        logging.info("Transforming speech segment to text...")
        segment_audio = whisper.load_audio(temp_audio_file)
        logging.info("Loaded audio segment. Transcribing...")
        try:
            result = whisper.transcribe(speech_to_text_model, segment_audio, language=audio_language)
        except Exception as e:
            raise RuntimeError(f"An error occurred while transcribing the audio segment #{segment_number}: {str(e)}")
        logging.info("Transformed speech segment to text. Writing to tmp JSON file...")

        # Save the result to a JSON file
        output_json_file = output_json_template.format(format_ms_duration(segment_start) + "_" + format_ms_duration(segment_end))
        with open(output_json_file, 'w', encoding='utf-8') as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        logging.info(f'Content has been written to the file {output_json_file}')

        # Remove the temporary audio file
        os.remove(temp_audio_file)

        logging.info(f"Completed processing for segment {segment_number}")

        # Prepare for the next segment
        segment_number += 1  # Adjusted from 1000 to 1 for logical sequencing

def generate_time_checkpoints(pattern, total_milliseconds):
    """
    Generate time checkpoints based on a specified interval pattern and total time.

    Args:
        pattern (str): A string pattern like '5h', '3s', or '5m'.
        total_milliseconds (int): Total time in milliseconds.

    Returns:
        list: A list of time checkpoints in 'hh:mm:ss' format.
    """

    # Determine the interval in seconds
    number = int(re.search(r'\d+', pattern).group())
    unit = pattern[-1]

    if unit == 'h':
        interval_seconds = number * 3600
    elif unit == 'm':
        interval_seconds = number * 60
    elif unit == 's':
        interval_seconds = number
    else:
        raise ValueError("Invalid time unit in pattern. Only 'h', 'm', and 's' are supported.")

    # Calculate the total time in seconds
    total_seconds = total_milliseconds // 1000

    # Generate checkpoints
    checkpoints = []
    current_seconds = interval_seconds
    while current_seconds <= total_seconds:
        # Convert current time to 'hh:mm:ss' format
        formatted_time = str(datetime.timedelta(seconds=current_seconds))
        checkpoints.append((current_seconds * 1000, formatted_time))

        # Move to the next checkpoint
        current_seconds += interval_seconds

    if len(checkpoints) == 0:
        checkpoints.append((total_seconds, str(datetime.timedelta(seconds=total_seconds))))

    return checkpoints

def is_pattern(str):
    return re.search(r'^[1-9]\d*[hms]$', str)

def validate_and_order_checkpoints(checkpoints_str, total_audio_duration_ms):
    # Convert the total audio duration from milliseconds to a hh:mm:ss format.
    hours, remainder = divmod(total_audio_duration_ms // 1000, 3600)
    minutes, seconds = divmod(remainder, 60)
    max_time_str = f"{hours:02}:{minutes:02}:{seconds:02}"

    checkpoints = []
    if is_pattern(checkpoints_str):
        checkpoints = generate_time_checkpoints(checkpoints_str, total_audio_duration_ms)
    else:
        # Validate the format of the checkpoints and convert to a list of strings.
        checkpoint_strings = checkpoints_str.split(',')
        valid_time_format = re.compile(r'^(\d+:)?(\d+:)?\d+$')  # Pattern to match times in hh:mm:ss format where hh: and mm: are optional.

        # Print the received checkpoints in list format, indexed from 1.
        logging.info("Received checkpoints:")
        for i, checkpoint in enumerate(checkpoint_strings, start=1):
            logging.info(f"{i}: {checkpoint.strip()}")

        for checkpoint_str in checkpoint_strings:
            checkpoint_str = checkpoint_str.strip()

            if not valid_time_format.match(checkpoint_str):
                raise ValueError(f"Invalid time format for checkpoint '{checkpoint_str}'. Expected format is hh:mm:ss, where 'ss' is mandatory and others are optional.")

            # Convert the checkpoint to a comparable format, ensuring it's within the audio duration bounds.
            checkpoint_ms = convert_hhmmss_to_ms(checkpoint_str)
            if checkpoint_ms < 0 or checkpoint_ms > total_audio_duration_ms:
                raise ValueError(f"Checkpoint '{checkpoint_str}' is out of bounds. Valid checkpoints range from 00:00:00 to {max_time_str}.")

            checkpoints.append((checkpoint_ms, checkpoint_str))  # Store as tuple for sorting.

    # Sort the checkpoints by time and check if they were initially out of order.
    sorted_checkpoints = sorted(checkpoints, key=lambda x: x[0])
    if sorted_checkpoints != checkpoints:
        logging.warning("Checkpoints were out of order and have been sorted.")

    # Extract the sorted, valid checkpoint strings for return.
    ordered_checkpoint_strings = [cp[1] for cp in sorted_checkpoints]
    return ordered_checkpoint_strings

def generate_segments_from_checkpoints(checkpoints, total_duration_ms):
    segments_to_process = []

    checkpoints = validate_and_order_checkpoints(checkpoints, total_duration_ms)

    # Convert checkpoint times to a list of milliseconds
    checkpoints = [convert_hhmmss_to_ms(cp) for cp in checkpoints]
    
    # Add the start of the first segment (0 ms)
    segments_to_process.append((0, checkpoints[0]))

    # Build segments from the checkpoints
    for start, end in zip(checkpoints, checkpoints[1:]):
        segments_to_process.append((start, end))

    # Add the end of the last segment based on the total audio duration
    segments_to_process.append((checkpoints[-1], total_duration_ms))

    return segments_to_process

def process_input(args):
    # extract command line args and set defaults
    checkpoints = args.checkpoints
    segments = args.segments
    input_path = args.input
    audio_language = args.language or 'en'

    if not input_path:
        raise ValueError("Input file path is required.")

    # checkpoints and segments are mutually exclusive
    if checkpoints and segments:
        raise ValueError("Cannot specify both checkpoints and segments simultaneously.")

    # Create the temporary directory if it doesn't exist
    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR)

    # Extract the audio from the video file if the input is a video
    input_audio_path = ''
    if is_video_file(input_path):
        input_audio_path = TMP_DIR + "input_audio.mp3"
        extract_audio(input_path, input_audio_path)
    # Otherwise, assume the input is an audio file
    else:
        input_audio_path = input_path

    # Validate the input audio file and rewrite path if necessary
    input_audio = validate_audio_file(input_audio_path)

    # Get the total duration of the audio in milliseconds
    total_duration_ms = len(input_audio)

    # Generate the segments to process based on the checkpoints or segments provided
    segments_to_process = []
    if checkpoints:
        segments_to_process = generate_segments_from_checkpoints(checkpoints, total_duration_ms)
    elif segments:
        segments_to_process = parse_segments(segments, total_duration_ms)
    else:
        # If no segments/checkpoints, process entire audio
        segments_to_process = [(0, total_duration_ms)]

    # Load the speech recognition model
    logging.info("Loading speech recognition model...")
    # TODO: be able to specify the model to use in the command line
    speech_to_text_model = whisper.load_model("tiny")
    logging.info("Speech recognition model loaded.")

    # Process the audio segments
    # The speech to text result for each segment will be saved to a JSON file.
    # The content of the generated JSON files is used then in the generate_output.py script as input to generate the final subtitles output.
    output_json_template = TMP_DIR + "speech_recognition_result_segment_{}.json"
    process_audio_segments(input_audio, segments_to_process, audio_language, speech_to_text_model, output_json_template)
