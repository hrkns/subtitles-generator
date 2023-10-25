import logging
import datetime
import json
import os
import re

TMP_DIR = "./tmp/"

# Set up logging
logging.basicConfig(level=logging.INFO)

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

def generate_output(args):
    output_path = args.output or os.path.dirname(args.input)
    output_path = validate_output(output_path)
    merge_subtitles = args.merge
    process_directory(output_path, merge_subtitles)
