import re

def convert_to_srt(filename):
    # Read the data from the file
    with open(filename, 'r', encoding='utf-8') as file:
        data = file.read()

    # Split the data into individual subtitles
    compressed_subs = data.split('|')

    # Prepare a list for the processed subtitles
    subtitles = []

    # Process each subtitle
    for idx, sub in enumerate(compressed_subs):
        # Split each subtitle into its components
        parts = re.split(',', sub, maxsplit=2)  # Split only on the first two commas

        # Check if the subtitle has at least 3 parts (start time, end time, text)
        if len(parts) >= 3:
            start, end, text = parts[0], parts[1], ','.join(parts[2:])  # Reconstruct the text with commas if necessary

            # Convert the subtitle time to SRT format
            start_time = f"{int(start)//3600000:02d}:{(int(start)//60000)%60:02d}:{(int(start)//1000)%60:02d},{int(start)%1000:03d}"
            end_time = f"{int(end)//3600000:02d}:{(int(end)//60000)%60:02d}:{(int(end)//1000)%60:02d},{int(end)%1000:03d}"

            # Build the subtitle text
            subtitle_text = f"{idx+1}\n{start_time} --> {end_time}\n{text}\n"

            # Add to the list of subtitles
            subtitles.append(subtitle_text)

            # Print the subtitle in the console in the desired format
            console_output = f"{start_time}-{end_time}-{text}"

    # Join all subtitles into a single string
    srt_content = "\n".join(subtitles)

    # Write the content to the SRT file
    with open("Z:\\video_edition\\hzd-serie\\output\\episode-01-survive\\ep01-survive.from-audio-rewritten.es.srt", 'w') as file:
        file.write(srt_content)

    print("The conversion to SRT was successfully completed.")

# Use the function with your .txt file
convert_to_srt('compressed_subtitles.txt')
