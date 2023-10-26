import logging
import shutil
from modules import Chronometer, execution_args
from process_input import process_input
from generate_output import generate_output

# Create and start the chronometer
chrono = Chronometer()
chrono.start()

TMP_DIR = "./tmp/"

# Set up logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    try:
        args = execution_args()
        process_input(args)
        generate_output(args)
    except Exception as e:
        logging.error(f"An error occurred while running process: {str(e)}", exc_info=True)
    finally:
        shutil.rmtree(TMP_DIR)
        logging.info("Clean exit.")
        chrono.stop()
        chrono.print_duration()

# TODO: when provided input is video, extract audio from it
# TODO: implement unit tests
# TODO: record demo video and put it in README.md (youtube link?)
# TODO: clean input audio file
# TODO: translate generated srt to other languages
