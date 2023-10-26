import argparse

def execution_args():
  parser = argparse.ArgumentParser(description="Tool for automatic generation of subtitles provided an audio/video input.")
  parser.add_argument('-v', '--version', action='store_true', help="Prints the version of the tool and exits.")
  parser.add_argument('-i', '--input', type=str, help="Input file path (MP3 audio file or video file).")
  parser.add_argument('-c', '--checkpoints', type=str, help="Checkpoints, either in comma-separated format hh:mm:ss (hours and minutes optional) or using pattern (ie 5s, 10m, 1h).")
  parser.add_argument('-s', '--segments', type=str, help="Segments to process in start-end format (00:50-13:57) or using pattern (ie 5s, 10m, 1h).")
  parser.add_argument('-l', '--language', type=str, help="Language of the audio.")
  parser.add_argument('-o', '--output', type=str, help="Output SRT file path (if no name is given and only a path, then a default name will be used). If not provided at all, then the output location will be the same one as the input.")
  parser.add_argument('-m', '--merge', action='store_true', help='If defined, it includes the new generated subtitles into the existing SRT file defined in the output parameter (if provided).')
  return parser.parse_args()
