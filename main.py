import logging
import os
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
        if not args.version:
            process_input(args)
            generate_output(args)
        else:
            logging.info("Version 0.1.0")
    except Exception as e:
        logging.error(f"An error occurred while running process: {str(e)}", exc_info=True)
    finally:
        if os.path.exists(TMP_DIR):
            shutil.rmtree(TMP_DIR)
        logging.info("Clean exit.")
        chrono.stop()
        chrono.print_duration()

# TODO: clean input audio file
# TODO: implement unit tests
# TODO: record demo video and put it in README.md (youtube link?)
# TODO: translate generated srt to other languages
