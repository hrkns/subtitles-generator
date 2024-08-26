import re
import sys
import os
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_srt(file_path):
    """Reads the content of an SRT file."""
    try:
        logging.info(f"Reading SRT file from '{file_path}'")
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        logging.error(f"The file '{file_path}' was not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An error occurred while reading the file: {e}")
        sys.exit(1)

def compress_and_split_srt(srt_content, max_chars=4000):
    """Compresses and splits SRT content into segments."""
    logging.info("Compressing and splitting the SRT content into segments.")
    blocks = re.split(r'\n\n', srt_content.strip())
    segments = []

    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            times = lines[1]
            start, end = times.split(' --> ')
            start_millis = sum(x * int(t) for x, t in zip([3600000, 60000, 1000, 1], re.split(r'[:,]', start)))
            end_millis = sum(x * int(t) for x, t in zip([3600000, 60000, 1000, 1], re.split(r'[:,]', end)))

            content = ' '.join(lines[2:]).replace('\n', '<br>').replace('|', '')

            segments.append({
                "start_time": start_millis,
                "end_time": end_millis,
                "text": content
            })

    logging.info(f"Total segments created: {len(segments)}")
    return segments

def time_to_seconds(t):
    """Converts a struct_time object to total seconds since midnight."""
    return t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec

def translate_segments(segments, conversation_intervals, source_language, target_language):
    """Translates the text of each segment using a specified translation model."""
    model_name = f'Helsinki-NLP/opus-mt-{source_language}-{target_language}'
    logging.info(f"Loading translation model '{model_name}'")
    from transformers import MarianMTModel, MarianTokenizer

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)

    translated_segments = []
    start_time = time.time()
    total_segments = len(segments)
    logging.info(f"Translating {total_segments} segments...")
    idx = -1
    segments_len = len(segments)

    while idx < segments_len - 1:
        idx += 1
        segment = segments[idx]
        logging.info(f"Processing segment {idx + 1} of {total_segments}...")
        segment_start_seconds = time_to_seconds(time.gmtime(segment['start_time'] / 1000))
        segment_end_seconds = time_to_seconds(time.gmtime(segment['end_time'] / 1000))
        src_text = [segment['text']]

        for interval in conversation_intervals:
            interval_start_seconds = time_to_seconds(interval['start'])
            interval_end_seconds = time_to_seconds(interval['end'])
            if interval_start_seconds <= segment_start_seconds and segment_end_seconds <= interval_end_seconds:
                logging.info(f"Segment {idx + 1} is within the conversation interval {time.strftime('%H:%M:%S', interval['start'])} - {time.strftime('%H:%M:%S', interval['end'])}")
                while (idx + 1 < total_segments):
                    next_segment = segments[idx + 1]
                    next_segment_start_seconds = time_to_seconds(time.gmtime(next_segment['start_time'] / 1000))
                    if interval_start_seconds <= next_segment_start_seconds <= interval_end_seconds:
                        src_text.append(next_segment['text'])
                        idx += 1
                    else:
                        logging.info(f"Conversation interval ended at segment {idx + 1}")
                        break
                break

        translated = model.generate(**tokenizer(src_text, return_tensors="pt", padding=True))
        translated_texts = tokenizer.batch_decode(translated, skip_special_tokens=True)

        for i, text in enumerate(translated_texts):
            translated_segments.append({
                "start_time": segments[idx - len(translated_texts) + i + 1]['start_time'],
                "end_time": segments[idx - len(translated_texts) + i + 1]['end_time'],
                "text": text.replace('<br>', '\n')
            })

        elapsed_time = time.time() - start_time
        percentage_done = (idx + 1) / total_segments * 100
        logging.info(f"Translated {idx + 1}/{total_segments} segments ({percentage_done:.2f}%) - Elapsed time: {time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}")

    logging.info("Translation completed.")
    return translated_segments

def save_translated_srt(translated_segments, output_file):
    """Saves the translated segments back into an SRT file."""
    logging.info(f"Saving translated content to '{output_file}'")
    subtitles = []

    for idx, segment in enumerate(translated_segments):
        start_time = f"{int(segment['start_time'])//3600000:02d}:{(int(segment['start_time'])//60000)%60:02d}:{(int(segment['start_time'])//1000)%60:02d},{int(segment['start_time'])%1000:03d}"
        end_time = f"{int(segment['end_time'])//3600000:02d}:{(int(segment['end_time'])//60000)%60:02d}:{(int(segment['end_time'])//1000)%60:02d},{int(segment['end_time'])%1000:03d}"
        
        subtitle_text = f"{idx+1}\n{start_time} --> {end_time}\n{segment['text']}\n"
        subtitles.append(subtitle_text)

    srt_content = "\n".join(subtitles)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(srt_content)

    logging.info(f"Translation saved successfully to '{output_file}'")

def parse_conversation_intervals(intervals_input):
    """Parses and validates the conversation intervals input."""
    intervals = []
    for interval in intervals_input.split(','):
        try:
            start, end = interval.split('-')
            start_time = time.strptime(start, "%H:%M:%S")
            end_time = time.strptime(end, "%H:%M:%S")

            if start_time > end_time:
                raise ValueError(f"Start time {start} is after end time {end} in interval {interval}.")

            intervals.append({
                "start": start_time,
                "end": end_time
            })
        except ValueError as e:
            logging.error(f"Invalid interval format: {e}")
            sys.exit(1)

    return intervals

if __name__ == "__main__":
    if len(sys.argv) < 5:
        logging.error("Usage: python srt_translation.py <srt_file> <source_language> <target_language> <conversation_intervals>")
        sys.exit(1)

    srt_file = sys.argv[1]
    source_language = sys.argv[2]
    target_language = sys.argv[3]
    conversation_intervals_input = sys.argv[4]

    conversation_intervals = parse_conversation_intervals(conversation_intervals_input)

    if not os.path.isfile(srt_file):
        logging.error(f"Error: File '{srt_file}' does not exist.")
        sys.exit(1)

    logging.info(f"Processing file '{srt_file}' from '{source_language}' to '{target_language}'")
    srt_content = read_srt(srt_file)
    segments = compress_and_split_srt(srt_content)
    translated_segments = translate_segments(segments, conversation_intervals, source_language, target_language)

    output_file = os.path.splitext(srt_file)[0] + ".translated.srt"
    save_translated_srt(translated_segments, output_file)
    logging.info("Script execution completed successfully.")
