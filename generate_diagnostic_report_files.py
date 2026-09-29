"""Compatibility entry point; the CLI lives in health_data_parser.cli.diagnostic_reports."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from health_data_parser.cli.diagnostic_reports import main  # noqa: E402

if __name__ == "__main__":
    main()
