# Subtitle Generator

Subtitle Generator is a tool designed to generate subtitles (SRT files) from audio files (MP3 format). It leverages advanced processing to interpret audio content and create time-stamped subtitles that can be used for a wide range of applications. It's built onto the **[`whisper_timestamped`](https://github.com/linto-ai/whisper-timestamped)** package.

## Features

- Support for input in MP3 audio format.
- Customizable checkpoints for subtitle segments.
- Ability to specify specific audio segments for processing.
- Language specification for the audio content.
- Control over the output file path and naming.

## Requirements

- Python 3.x

## Installation

- This application relies on **[`whisper_timestamped`](https://github.com/linto-ai/whisper-timestamped)** for working properly so refer to its [installation](https://github.com/linto-ai/whisper-timestamped#installation) instructions for enabling it into the system.

- Clone this repository or download the source code. Install the other required packages by running either `install_dependencies.cmd` or `install_dependencies.sh`.

## Usage

The application is command-line based and can be initiated with specific parameters detailed below:

### Mandatory Arguments:

- `-i` or `--input`: The path to the input audio file in MP3 format. This argument is required.
  - The final result will be more accurate if the input audio is clean and contains only voices. For cleaning audio before passing it to the tool, use software like **[UVR](https://github.com/Anjok07/ultimatevocalremovergui)**. As a future feature this audio cleaning will be integrated automatically into this tool. For now is a pending TODO.

- `-o` or `--output`: The path where the SRT file will be saved. If only a directory path is provided, the application will save the output with a default name. If not provided at all, then the output location will be the same one as the input.

### Optional Arguments:

- `-c` or `--checkpoints`: Specific times (checkpoints) for subtitle segmentation, provided in a comma-separated list in the format `hh:mm:ss` or a single value in format `{number}{s|m|h}` (for example, `5h` for expressing checkpoints every five hours). Hours and minutes are optional in the `hh:mm:ss` format. Checkpoints usage increase the accuracy of the final result. This is something related to how [`whisper_timestamped`](https://github.com/linto-ai/whisper-timestamped) package works and we hope to solve it in the future so this input is no longer required.

- `-s` or `--segments`: Specific segments of the audio file to process, provided in the format start-end (e.g., 00:50-13:57) or a single value in format `{number}{s|m|h}` (for example, `5h` for expressing segments of five hours each). Segments are used for re-generate subtitles for the specified intervals and these results can either be put in a new SRT file or merged into an existing one with the merge flag (`-m` or `--merge`).

- `-m` or `--merge`: Merge the output of the process into an existing SRT file either indicated with the output input flag or implicitly inferred from the input path.

- `-l` or `--language`: The language of the audio content. This information will be used for speech recognition purposes. Supported languages and how the Whisper AI models perform for each one can be found [here](https://github.com/openai/whisper#available-models-and-languages). If no value provided, then the default one will be `en` (English).

### Examples:

1. Basic usage with mandatory parameters:

```
python main.py -i /path/to/audio.mp3
```

2. Indicating output explicitly:

```
python main.py -i /path/to/audio.mp3 -o /path/to/output.srt
```

3. Including checkpoints in `hh:mm:ss` format:

```
python main.py -i /path/to/audio.mp3 -c 00:30,05:00,10:00
```

4. Including checkpoints in periodic format (every five minutes):

```
python main.py -i /path/to/audio.mp3 -c 5m
```

5. Specifying segments:

```
python main.py -i /path/to/audio.mp3 -s 00:50-13:57
```

6. Specifying segments with periodic format (segments of five minutes each):

```
python main.py -i /path/to/audio.mp3 -s 5m
```

7. Setting the language:

```
python main.py -i /path/to/audio.mp3 -l en
```

## Contributing

Contributions, issues, and feature requests are welcome!

## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)

## TODO

- Allow other audio formats as input.
- Allow video as input.
- Automatically clean input audio before applying speech detection.
- Enable translation of generated subtitles to other languages.
- GUI that allows to do all the same operations and also save projects
