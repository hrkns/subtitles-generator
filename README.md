# Subtitle Generator

Subtitle Generator is a tool designed to generate subtitles (SRT files) from audio files (MP3 format). It leverages advanced processing to interpret audio content and create time-stamped subtitles that can be used for a wide range of applications. It's built onto the **[`whisper_timestamped`](https://github.com/linto-ai/whisper-timestamped)** package.

## Features

- Support for input in MP3 audio format.
- Customizable checkpoints for subtitle segments.
- Ability to specify specific audio segments for processing.
- Language specification for the audio content.
- Control over the output file path and naming.
- Option to bypass the speech recognition phase.

## Requirements

- Python 3.x
- Necessary Python packages (see `requirements.txt`)

## Installation

Clone this repository or download the source code. Install the required packages by running:

```
pip install -r requirements.txt
```

## Usage

The application is command-line based and can be initiated with specific parameters detailed below:

### Mandatory Arguments:

- `-i` or `--input`: The path to the input audio file in MP3 format. This argument is required.

- `-o` or `--output`: The path where the SRT file will be saved. If only a directory path is provided, the application will save the output with a default name. This argument is required.

### Optional Arguments:

- `-c` or `--checkpoints`: Specific times (checkpoints) for subtitle segmentation, provided in a comma-separated list in the format hh:mm:ss. Hours and minutes are optional. Checkpoints usage increase the accuracy of the final result. This is something related to how [`whisper_timestamped`](https://github.com/linto-ai/whisper-timestamped) package works and we hope to solve it in the future so this input is no longer required.

- `-s` or `--segments`: Specific segments of the audio file to process, provided in the format start-end (e.g., 00:50-13:57). Segments are used for re-generate subtitles for the specified intervals and these results can either be put in a new SRT file or merged into an existing one.

- `-l` or `--language`: The language of the audio content. This information will be used for speech recognition purposes. Supported languages and how the Whisper AI models perform for each one can be found [here](https://github.com/openai/whisper#available-models-and-languages).

### Examples:

1. Basic usage with mandatory parameters:

```
python main.py -i /path/to/audio.mp3 -o /path/to/output.srt
```

2. Including checkpoints:

```
python main.py -i /path/to/audio.mp3 -o /path/to/output.srt -c 00:30,05:00,10:00
```

3. Specifying segments:

```
python main.py -i /path/to/audio.mp3 -o /path/to/output.srt -s 00:50-13:57
```

4. Setting the language:

```
python main.py -i /path/to/audio.mp3 -o /path/to/output.srt -l en
```

## Contributing

Contributions, issues, and feature requests are welcome!

## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
