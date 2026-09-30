import os
import sys

from health_data_parser.errors import HealthDataParseError
from health_data_parser.ingest.custom_observations import generate_diagnostic_report_files
from health_data_parser.utils.logger import setup_logger
from health_data_parser.utils.translations import _

logger = setup_logger('diagnostic_report_generator')


def help_text():
    return _("""
Usage:

   $ health-data-parser-reports path/to/observation_data.csv [options]

Writes the observations in the CSV as DiagnosticReport JSON files next to it.

    -h, --help
        Print this help text

    -v, --verbose
        Run in verbose mode
""")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) < 1:
        print(help_text())
        sys.exit()

    '''
    data_export_dir = sys.argv[1]

    if data_export_dir == None or data_export_dir == "":
        logger.error("Missing Apple Health data export directory path.")
        print(help_text)
        exit(1)
    elif not os.path.exists(data_export_dir) or not os.path.isdir(data_export_dir):
        logger.error("Apple Health data export directory path \"" + data_export_dir + "\" is invalid.")
        print(help_text)
        exit(1)
    '''

    observation_data_csv = argv[0]
    base_dir = os.path.dirname(observation_data_csv)
    COMMANDS = argv[1:]
    verbose = False

    if len(COMMANDS) > 0:
        for command in COMMANDS:
            if command == "-h" or command == "--help":
                print(help_text())
                sys.exit()
            elif command == "-v" or command == "--verbose":
                verbose = True

    try:
        succeeded = generate_diagnostic_report_files(observation_data_csv, base_dir, verbose)
    except HealthDataParseError as e:
        logger.error(str(e))
        print(help_text())
        sys.exit(1)

    if succeeded:
        if verbose:
            logger.info("All requested diagnostic report files generated.")
    else:
        logger.error("An error occurred in writing custom observations data to Diagnostic Report format JSON.")


if __name__ == "__main__":
    main()
