import re
import sys
import os
import logging
import time

# Setup logging configuration
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
    blocks = re.split(r'\n\n', srt_content.strip())  # Split the subtitles into blocks
    segments = []

    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            # Extract the start and end times
            times = lines[1]
            start, end = times.split(' --> ')
            start_millis = sum(x * int(t) for x, t in zip([3600000, 60000, 1000, 1], re.split(r'[:,]', start)))
            end_millis = sum(x * int(t) for x, t in zip([3600000, 60000, 1000, 1], re.split(r'[:,]', end)))

            # Extract and process the subtitle text
            content = ' '.join(lines[2:]).replace('\n', '<br>').replace('|', '')
            
            # Append the segment to the list
            segments.append({
                "start_time": start_millis,
                "end_time": end_millis,
                "text": content
            })

    logging.info(f"Total segments created: {len(segments)}")
    return segments

def translate_segments(segments, model_name='Helsinki-NLP/opus-mt-en-es'):
    """Translates the text of each segment using a specified translation model."""
    logging.info(f"Loading translation model '{model_name}'")
    from transformers import MarianMTModel, MarianTokenizer

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)

    translated_segments = []

    start_time = time.time()
    total_segments = len(segments)
    logging.info(f"Translating {total_segments} segments...")

    logging.info("Translating segments...")
    for idx, segment in enumerate(segments):
        src_text = [segment['text']]
        
        # Start translation time
        segment_start_time = time.time()
        
        translated = model.generate(**tokenizer(src_text, return_tensors="pt", padding=True))
        translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)
        
        translated_segments.append({
            "start_time": segment['start_time'],
            "end_time": segment['end_time'],
            "text": translated_text.replace('<br>', '\n')  # Replace back '<br>' with newlines
        })

        # Calculate progress
        elapsed_time = time.time() - start_time
        percentage_done = (idx + 1) / total_segments * 100
        estimated_total_time = elapsed_time / (idx + 1) * total_segments
        estimated_remaining_time = estimated_total_time - elapsed_time
        
        # Format times
        elapsed_time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        estimated_remaining_time_str = time.strftime("%H:%M:%S", time.gmtime(estimated_remaining_time))
        segment_start_time_str = time.strftime("%H:%M:%S", time.gmtime(segment_start_time))
        segment_end_time_str = time.strftime("%H:%M:%S", time.gmtime(time.time()))

        # Log the progress, original text, and translated text
        sys.stdout.write(f"\rTranslating segment {idx + 1}/{total_segments} "
                        f"({percentage_done:.2f}% done) - "
                        f"Elapsed: {elapsed_time_str} - "
                        f"Remaining: {estimated_remaining_time_str} - "
                        f"Started: {segment_start_time_str} - "
                        f"Ended: {segment_end_time_str}\n"
                        f"Original: {segment['text'][:50]}... "
                        f"Translated: {translated_text[:50]}... ")
        sys.stdout.flush()

    print()
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

if __name__ == "__main__":
    if len(sys.argv) < 4:
        logging.error("Usage: python srt_translator.py <srt_file> <source_language> <target_language>")
        sys.exit(1)

    srt_file = sys.argv[1]
    source_language = sys.argv[2]
    target_language = sys.argv[3]

    # Validate the languages
    valid_languages = ["en", "es"]
    if source_language not in valid_languages or target_language not in valid_languages:
        logging.error(f"Invalid language. Only 'en' (English) and 'es' (Spanish) are allowed.")
        sys.exit(1)

    if source_language == target_language:
        logging.error("Source and target languages cannot be the same.")
        sys.exit(1)

    if not os.path.isfile(srt_file):
        logging.error(f"Error: File '{srt_file}' does not exist.")
        sys.exit(1)

    logging.info(f"Processing file '{srt_file}' from '{source_language}' to '{target_language}'")
    srt_content = read_srt(srt_file)
    segments = compress_and_split_srt(srt_content)
    translated_segments = translate_segments(segments)

    output_file = os.path.splitext(srt_file)[0] + ".translated.srt"
    save_translated_srt(translated_segments, output_file)
    logging.info("Script execution completed successfully.")
