"""Compatibility entry point; the GUI lives in health_data_parser.gui.app."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from health_data_parser.gui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
