from modules import Chronometer, validate_audio_file, convert_hhmmss_to_ms, format_ms_duration

# Create and start the chronometer
chrono = Chronometer()
chrono.start()

import argparse
import json
import datetime
import re
import os
import logging
import whisper_timestamped as whisper
import shutil

TMP_DIR = "./tmp/"

# Set up logging
logging.basicConfig(level=logging.INFO)

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

def process_audio_segments(input_audio, segments_to_process, audio_language, model, output_json_template):
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

def speech_to_text(args):
    checkpoints = args.checkpoints
    segments = args.segments
    input_audio_path = args.input
    audio_language = args.language or 'en'
    output_path = args.output

    if checkpoints and segments:
        raise ValueError("Cannot specify both checkpoints and segments simultaneously.")

    input_audio = validate_audio_file(input_audio_path)

    validate_output(output_path)

    # Get the total duration of the audio in milliseconds
    total_duration_ms = len(input_audio)

    segments_to_process = []

    if checkpoints:
        segments_to_process = generate_segments_from_checkpoints(checkpoints, total_duration_ms)
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

        return path

def convert_to_srt_time(time_in_seconds):
    formatted_time = datetime.timedelta(seconds=time_in_seconds)
    hours, remainder = divmod(formatted_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    hours += formatted_time.days * 24  # add days to hours if there are any
    milliseconds = formatted_time.microseconds // 1000
    return "{:02}:{:02}:{:02},{:03}".format(hours, minutes, seconds, milliseconds)

def generate_subtitle_entry(index, start_time, end_time, text):
    """Generate a subtitle entry."""
    start_srt = convert_to_srt_time(start_time)
    end_srt = convert_to_srt_time(end_time)
    return f"{index}\n{start_srt} --> {end_srt}\n{text}\n\n"

def create_srt_content(json_files):
    segments = []
    for json_file in json_files:
        with open(f"{TMP_DIR}{json_file}", 'r', encoding='utf-8') as file:
            data = json.load(file)
            offset = extract_time_from_filename(json_file)
            if offset is not None:
                for segment in data['segments']:
                    segment['start'] += offset
                    segment['end'] += offset
            segments.extend(data['segments'])

    index = 1
    current_text = None
    start_time = None
    end_time = None
    entries = []

    for segment in segments:
        if current_text is not None and current_text != segment['text']:
            entries.append(generate_subtitle_entry(index, start_time, end_time, current_text))
            index += 1
            current_text = segment['text']
            start_time = segment['start']
            end_time = segment['end']
        else:
            if current_text is None:
                current_text = segment['text']
                start_time = segment['start']
            end_time = segment['end']

    if current_text is not None:
        entries.append(generate_subtitle_entry(index, start_time, end_time, current_text))

    return ''.join(entries)

class Subtitle:
    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end = end
        self.text = text

    @classmethod
    def from_srt_block(cls, block):
        lines = block.strip().split("\n")
        index = lines[0]
        start, end = cls.parse_time_range(lines[1])
        text = "\n".join(lines[2:]).strip()
        return cls(index, start, end, text)

    @staticmethod
    def parse_time_range(time_range):
        time_format = '%H:%M:%S,%f'
        start_str, end_str = time_range.split(" --> ")
        start = datetime.datetime.strptime(start_str.strip(), time_format).time()
        end = datetime.datetime.strptime(end_str.strip(), time_format).time()
        return start, end

    @staticmethod
    def time_to_str(time):
        return time.strftime('%H:%M:%S,%f')[:-3]  # remove last three digits (micro -> milliseconds)

    def to_srt_block(self):
        start_str = self.time_to_str(self.start)
        end_str = self.time_to_str(self.end)
        return f"{self.index}\n{start_str} --> {end_str}\n{self.text}\n"

def parse_srt(srt_content):
    blocks = srt_content.split("\n\n")
    return [Subtitle.from_srt_block(block) for block in blocks if block.strip()]

def merge_srt_content(srt1_content, srt2_content):
    subtitles1 = parse_srt(srt1_content)
    subtitles2 = parse_srt(srt2_content)

    # Logic for replacing the content from srt1 with srt2 based on the time range.
    merged_subtitles = subtitles1
    for sub2 in subtitles2:
        # Remove any overlapping subtitles from srt1
        merged_subtitles = [sub for sub in merged_subtitles if not (sub.start < sub2.end and sub2.start < sub.end)]
        # Merge the subtitles list while maintaining the order
        merged_subtitles = sorted(merged_subtitles + [sub2], key=lambda sub: sub.start)
        # Re-index the subtitles
        i = 1  # subtitle index for the new merged content
        for sub in merged_subtitles:
            sub.index = i
            i += 1

    # Convert the merged subtitles back to SRT format
    merged_srt_content = "\n\n".join(sub.to_srt_block() for sub in merged_subtitles)
    return merged_srt_content

def extract_time_from_filename(filename):
    """
    Extract the time information from the file name and convert it to seconds.

    :param filename: str, the file name which contains the time information
    :return: time_in_seconds, the float time in seconds format or None if there is a format mismatch
    """
    
    # Use regex to find the time pattern in the filename.
    match = re.search(r'(\d{6})_(\d{6})\.json$', filename)
    
    if match:
        # If a matching segment is found, isolate the required time segment (the second group in this case).
        time_segment = match.group(1)  # e.g., "004408"

        # Split the time segment into hours, minutes, and seconds.
        # We're assuming here that the time is represented in a 'hhmmss' format.
        hours, remainder = divmod(int(time_segment), 10000)
        minutes, seconds = divmod(remainder, 100)

        formatted_time = hours * 3600 + minutes * 60 + seconds
        return formatted_time
    else:
        # If the regex finds no match, there's a format mismatch. Handle as appropriate.
        logging.info("The filename does not match the expected format.")
        return None

def process_directory(output_path, merge_subtitles=False):
    # Gather all JSON files in the directory
    json_files = sorted([file for file in os.listdir(TMP_DIR) if file.endswith('.json')])
    logging.info(f"Found {len(json_files)} speech recognition JSON file(s) for processing.")

    try:
        logging.info(f"Processing speech recognition JSON files")
        srt_content = create_srt_content(json_files)
        logging.info(f"Completed processing speech recognition JSON files")

        if merge_subtitles and os.path.exists(output_path):
            # If the merge flag is set, merge the new subtitles with the existing ones.
            logging.info(f"Merging generated subtitles with existing ones")
            with open(output_path, 'r', encoding='utf-8') as file:
                existing_srt_content = file.read()
            srt_content = merge_srt_content(existing_srt_content, srt_content)

        srt_output_file = open(output_path, 'w', encoding='utf-8')
        logging.info(f"Writing to output file: {output_path}")
        srt_output_file.write(srt_content.strip())
        srt_output_file.close()
    except Exception as e:
        logging.error(f"An error occurred while processing speech recognition JSON files: {str(e)}", exc_info=True)

    logging.info("All files have been processed.")

def srt_generation(args):
    output_path = args.output or os.path.dirname(args.input)
    output_path = validate_output(output_path)
    merge_subtitles = args.merge
    process_directory(output_path, merge_subtitles)

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Process audio segments.")
        parser.add_argument('-i', '--input', required=True, help="Input audio file (MP3 format).")
        parser.add_argument('-c', '--checkpoints', type=str, help="Checkpoints, either in comma-separated format hh:mm:ss (hours and minutes optional) or using pattern (ie 5s, 10m, 1h).")
        parser.add_argument('-s', '--segments', type=str, help="Segments to process in start-end format (00:50-13:57) or using pattern (ie 5s, 10m, 1h).")
        parser.add_argument('-l', '--language', type=str, help="Language of the audio.")
        parser.add_argument('-o', '--output', type=str, help="Output SRT file path (if no name is given and only a path, then a default name will be used). If not provided at all, then the output location will be the same one as the input.")
        parser.add_argument('-m', '--merge', action='store_true', help='If defined, it includes the new generated subtitles into the existing SRT file defined in the output parameter (if provided).')
        args = parser.parse_args()
        speech_to_text(args)
        srt_generation(args)
    except Exception as e:
        logging.error(f"An error occurred while processing the audio file: {str(e)}", exc_info=True)
    finally:
        shutil.rmtree(TMP_DIR)
        logging.info("Clean exit.")
        chrono.stop()
        chrono.print_duration()

# TODO: modularize code
# TODO: implement unit tests
# TODO: record demo video and put it in README.md (youtube link?)
# TODO: when provided input is video, extract audio from it
# TODO: clean input audio file
# TODO: translate generated srt to other languages
