import argparse
import json
import datetime
import re
import os
import logging
import sys
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import whisper_timestamped as whisper

TMP_DIR = "./tmp/"

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

def convert_to_ms(timestamp):
    if timestamp is None:
        return None

    parts = list(map(int, timestamp.split(':')))
    parts.reverse()  # Reverse to ensure hours are optional

    multipliers = [1000, 60000, 3600000]  # multipliers for seconds, minutes, hours to milliseconds
    return sum(value * multiplier for value, multiplier in zip(parts, multipliers))

def format_duration(ms):
    """
    Convert duration from milliseconds to a formatted string: "hh:mm:ss".
    
    :param ms: Duration in milliseconds.
    :type ms: int
    :return: Formatted duration.
    :rtype: str
    """
    if ms < 0:
        raise ValueError("Duration must be non-negative.")

    # Convert milliseconds to seconds, then compute hours, minutes, and seconds
    seconds = ms // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format the result as "hh:mm:ss"
    formatted_duration = f"{hours:02}{minutes:02}{seconds:02}"

    return formatted_duration

def parse_segments(segments_str, total_duration_ms):
    segments = []
    overlapping_segments = []
    segment_parts = segments_str.split(',')

    logging.info("Parsing segments...")
    segment_list = segments_str.split(',')
    for i, segment in enumerate(segment_list, start=1):
        print(f"{i}: {segment.strip()}")

    for index, segment in enumerate(segment_parts):
        segment = segment.strip()
        if index == 0 and segment.startswith(':'):
            # If the first segment starts with ':', it implies a start at 0.
            start_ms = 0
            end_str = segment.lstrip(':')  # Remove the ':' to get the end time.
            end_ms = convert_to_ms(end_str) if end_str else total_duration_ms  # If no end time, use the audio duration.
        else:
            start, sep, end = segment.partition('-')
            if not sep or not end:
                # If the separator '-' is not found or the end is not defined, this segment is malformed (excluding the last segment).
                if index == len(segment_parts) - 1 and not sep:
                    # For the last segment, if there is no '-', consider the whole part as the start.
                    start_ms = convert_to_ms(start)
                    end_ms = total_duration_ms  # The end of the last segment is the audio duration.
                else:
                    raise ValueError(f"Segment {index + 1} is malformed, segments (except the first and last) must have both start and end defined.")
            else:
                start_ms = convert_to_ms(start)
                end_ms = convert_to_ms(end) if end else total_duration_ms  # If no end time, it's the audio duration.

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

def process_audio_segments(input_audio, segments_to_process, audio_language, model, output_json_template):
    # This function assumes the existence of a 'whisper' module and 'model' variable.
    # These are not standard Python or known third-party libraries as of the last update in 2022.
    # Ensure your environment contains these, or replace them with the actual modules and methods you're using for audio processing.

    segment_number = 1

    for segment_to_process in segments_to_process:
        # Convert the checkpoint to milliseconds
        segment_start = segment_to_process[0]
        segment_end = segment_to_process[1]
        logging.info(f"Processing segment {segment_number} starting at {format_duration(segment_start)} and ending at {format_duration(segment_end)}")

        # Create the audio segment
        audio_segment = input_audio[segment_start:segment_end]

        # Save the audio segment to a temporary file
        logging.info("Creating tmp audio segment...")
        output_format = "mp3"
        if not os.path.exists(TMP_DIR):
            os.makedirs(TMP_DIR)
        temp_audio_file = f"{TMP_DIR}temp_segment_{segment_number}.{output_format}"
        audio_segment.export(temp_audio_file, format=output_format)
        logging.info("Created temporary audio segment.")

        # Transcribe the audio segment
        logging.info("Transforming speech segment to text...")
        segment_audio = whisper.load_audio(temp_audio_file)
        result = whisper.transcribe(model, segment_audio, language=audio_language)
        logging.info("Transformed speech segment to text. Writing to tmp JSON file...")

        # Save the result to a JSON file
        output_json_file = output_json_template.format(format_duration(segment_start) + "_" + format_duration(segment_end))
        with open(output_json_file, 'w', encoding='utf-8') as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        logging.info(f'Content has been written to the file {output_json_file}')

        # Remove the temporary audio file
        os.remove(temp_audio_file)

        logging.info(f"Completed processing for segment {segment_number}")

        # Prepare for the next segment
        segment_number += 1  # Adjusted from 1000 to 1 for logical sequencing

def validate_and_order_checkpoints(checkpoints_str, total_audio_duration_ms):
    # Convert the total audio duration from milliseconds to a hh:mm:ss format.
    hours, remainder = divmod(total_audio_duration_ms // 1000, 3600)
    minutes, seconds = divmod(remainder, 60)
    max_time_str = f"{hours:02}:{minutes:02}:{seconds:02}"

    # Validate the format of the checkpoints and convert to a list of strings.
    checkpoint_strings = checkpoints_str.split(',')
    valid_time_format = re.compile(r'^(\d+:)?(\d+:)?\d+$')  # Pattern to match times in hh:mm:ss format where hh: and mm: are optional.

    # Print the received checkpoints in list format, indexed from 1.
    print("Received checkpoints:")
    for i, checkpoint in enumerate(checkpoint_strings, start=1):
        print(f"{i}: {checkpoint.strip()}")

    checkpoints = []
    for checkpoint_str in checkpoint_strings:
        checkpoint_str = checkpoint_str.strip()

        if not valid_time_format.match(checkpoint_str):
            raise ValueError(f"Invalid time format for checkpoint '{checkpoint_str}'. Expected format is hh:mm:ss, where 'ss' is mandatory and others are optional.")

        # Convert the checkpoint to a comparable format, ensuring it's within the audio duration bounds.
        checkpoint_ms = convert_to_ms(checkpoint_str)
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

def speech_to_text(args):
    checkpoints = args.checkpoints
    segments = args.segments
    input_audio_path = args.input
    audio_language = args.language or 'en'
    output_path = args.output

    if checkpoints and segments:
        logging.error("Cannot specify both checkpoints and segments simultaneously.")
        sys.exit(1)

    input_audio = validate_audio_file(input_audio_path)

    validate_output(output_path)

    # Get the total duration of the audio in milliseconds
    total_duration_ms = len(input_audio)

    segments_to_process = []
    if checkpoints:
        checkpoints = validate_and_order_checkpoints(checkpoints, total_duration_ms)

        # Convert checkpoint times to a list of milliseconds
        checkpoints = [convert_to_ms(cp) for cp in checkpoints]
        
        # Add the start of the first segment (0 ms)
        segments_to_process.append((0, checkpoints[0]))

        # Build segments from the checkpoints
        for start, end in zip(checkpoints, checkpoints[1:]):
            segments_to_process.append((start, end))

        # Add the end of the last segment based on the total audio duration
        segments_to_process.append((checkpoints[-1], total_duration_ms))
    elif segments:
        segments_to_process = parse_segments(segments, total_duration_ms)
    else:
        segments_to_process = [(0, total_duration_ms)]  # If no segments/checkpoints, process entire audio

    logging.info("Loading speech recognition model...")
    model = whisper.load_model("tiny")
    logging.info("Speech recognition model loaded.")

    output_json_template = TMP_DIR + "speech_recognition_result_segment_{}.json"
    process_audio_segments(input_audio, segments_to_process, audio_language, model, output_json_template)

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

        return True  # Output directory exists, proceed with operation

def convert_to_srt_time(time, extra_time=None):
    formatted_time = datetime.timedelta(seconds=time)
    if extra_time:
        extra_time_in_seconds = extra_time / 1000  # 'extra_time' is in milliseconds
        extra_time_delta = datetime.timedelta(seconds=extra_time_in_seconds)
        formatted_time += extra_time_delta  # add the extra time
    hours, remainder = divmod(formatted_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    hours += formatted_time.days * 24  # add days to hours if there are any
    milliseconds = formatted_time.microseconds // 1000
    return "{:02}:{:02}:{:02},{:03}".format(hours, minutes, seconds, milliseconds)

def create_srt_content(json_file, extra_time_str=None, base_index=0):
    extra_time = None
    if extra_time_str:
        extra_time = convert_to_ms(extra_time_str)
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
    segments = data['segments']
    entries = []
    for i, segment in enumerate(segments):
        # Apply extra time to start and end
        start = convert_to_srt_time(segment['start'], extra_time)
        end = convert_to_srt_time(segment['end'], extra_time)
        text = segment['text']
        entry = "{}\n{} --> {}\n{}\n".format(base_index + i + 1, start, end, text.strip())
        entries.append(entry)
    srt_content = "\n".join(entries)
    return (srt_content, len(segments))

def extract_time_from_filename(filename):
    """
    Extract the time information from the file name and convert it to the format "hh:mm:ss".

    :param filename: str, the file name which contains the time information
    :return: str, the time in "hh:mm:ss" format or None if there is a format mismatch
    """
    
    # Use regex to find the time pattern in the filename.
    match = re.search(r'(\d{6})_(\d{6})\.json$', filename)
    
    if match:
        # If a matching segment is found, isolate the required time segment (the second group in this case).
        time_segment = match.group(2)  # e.g., "004408"

        # Split the time segment into hours, minutes, and seconds.
        # We're assuming here that the time is represented in a 'hhmmss' format.
        hours, remainder = divmod(int(time_segment), 10000)
        minutes, seconds = divmod(remainder, 100)

        # Format the time in 'hh:mm:ss' format and return.
        formatted_time = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
        return formatted_time
    else:
        # If the regex finds no match, there's a format mismatch. Handle as appropriate.
        print("The filename does not match the expected format.")
        return None

def process_directory(output_path):
    directory_path = TMP_DIR

    # Gather all JSON files in the directory
    json_files = sorted([file for file in os.listdir(directory_path) if file.endswith('.json')])

    logging.info(f"Found {len(json_files)} speech recognition JSON file(s) for processing.")

    base_index = 0
    previous_segment_end_time = "00:00:00"  # Initialize with zero for the first file.

    srt_output_file = open(output_path, 'w', encoding='utf-8')

    for file_name in json_files:
        file_path = os.path.join(directory_path, file_name)
        
        try:
            logging.info(f"Processing speech recognition JSON file: {file_name}")

            # Create SRT content and get the new index base
            srt_content, num_segments_processed = create_srt_content(file_path, previous_segment_end_time, base_index)

            srt_output_file.write(srt_content.strip() + "\n\n")

            # Update for next iteration
            base_index += num_segments_processed
            previous_segment_end_time = extract_time_from_filename(file_name)

            logging.info(f"Completed processing for file: {file_name}")
        except Exception as e:
            logging.error(f"An error occurred while processing file {file_name}: {str(e)}", exc_info=True)

    srt_output_file.close()

    logging.info("All files have been processed.")

def srt_generation(args):
    output_path = args.output
    output_path = validate_output(output_path)
    process_directory(output_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process audio segments.")
    parser.add_argument('-i', '--input', required=True, help="Input audio file (MP3 format).")
    parser.add_argument('-c', '--checkpoints', type=str, help="Checkpoints, comma-separated, in format hh:mm:ss (hours and minutes optional).")
    parser.add_argument('-s', '--segments', type=str, help="Segments to process in start-end format (00:50-13:57).")
    parser.add_argument('-l', '--language', type=str, help="Language of the audio.")
    parser.add_argument('-o', '--output', required=True, help="Output SRT file path (if no name is given and only a path, then a default name will be used).")
    args = parser.parse_args()

    speech_to_text(args)

    srt_generation(args)

# TODO: remove tmp folder after finishing processing
# TODO: run process for sub segments and merge with existing srt and avoiding duplicate subtitles
# TODO: read checkpoint/segments using pattern like "every 5 minutes" or "every 10 minutes"
# TODO: modularize code
# TODO: implement unit tests
# TODO: create dependency installer script
# TODO: print execution time
# TODO: when provided input is video, extract audio from it
# TODO: clean input audio file
# TODO: translate generated srt to other languages
