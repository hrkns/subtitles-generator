import logging
import os
import shutil
from config import APP_VERSION, TMP_DIR
from modules import Chronometer, execution_args
from process_input import process_input
from generate_output import generate_output

# Create and start the chronometer
chrono = Chronometer()
chrono.start()

# Set up logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    try:
        # Parse execution arguments
        args = execution_args()

        # Run the program or print the version
        if not args.version:
            process_input(args)
            generate_output(args)
        else:
            logging.info(f"Version {APP_VERSION}")
    except Exception as e:
        logging.error(f"An error occurred while running process: {str(e)}", exc_info=True)
    finally:
        # Clean up the temporary directory
        if os.path.exists(TMP_DIR):
            shutil.rmtree(TMP_DIR)

        logging.info("Clean exit.")

        # Stop the chronometer and print the duration
        chrono.stop()
        chrono.print_duration()

# TODO: clean input audio file
# TODO: implement unit tests
# TODO: record demo video and put it in README.md (youtube link?)
# TODO: translate generated srt to other languages
