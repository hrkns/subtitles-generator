import re

def read_srt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def save_segment(data, output_file, separator="\n\n"):
    # Append the segment to the file, followed by the separator.
    with open(output_file, 'a', encoding='utf-8') as file:  # 'a' to append to the file instead of overwriting it
        file.write(data)
        file.write(separator)  # Write the separator after each segment
    print(f"Segment added to file '{output_file}'")

def compress_and_split_srt(srt_content, output_file, max_chars=4000):  # You can adjust the max size here
    # Split the subtitles into blocks
    blocks = re.split(r'\n\n', srt_content.strip())
    segment = ""
    
    # Ensure the output file is empty at the start
    open(output_file, 'w').close()

    for block in blocks:
        lines = block.split('\n')

        if len(lines) >= 3:
            # The first line is the subtitle number, we ignore it.
            # Convert times to milliseconds
            times = lines[1]
            start, end = times.split(' --> ')
            start_millis = sum(x * int(t) for x, t in zip([3600000, 60000, 1000, 1], re.split(r'[:,]', start)))
            end_millis = sum(x * int(t) for x, t in zip([3600000, 60000, 1000, 1], re.split(r'[:,]', end)))

            # The remaining lines are the subtitle content
            content = ' '.join(lines[2:]).replace('\n', '<br>').replace('|', '')  # Replace line breaks with '<br>'

            # Build the compressed string
            compressed_sub = f"{start_millis},{end_millis},{content}|"

            # Check if adding this block exceeds the maximum character limit
            if len(segment) + len(compressed_sub) > max_chars:
                save_segment(segment.strip('|'), output_file)
                segment = ""

            segment += compressed_sub

    # Save the last segment if it contains data
    if segment.strip('|'):
        save_segment(segment.strip('|'), output_file)

# Use the function on an SRT file
srt_content = read_srt("Z:\\video_edition\\hzd-serie\\output\\episode-01-survive\\ep01-survive.from-audio-rewritten.en.srt")
output_file = "compressed_subtitles.txt"  # Define your output file name
compress_and_split_srt(srt_content, output_file)
