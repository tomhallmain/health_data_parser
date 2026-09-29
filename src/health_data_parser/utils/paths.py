from pathlib import Path


def repo_root() -> Path:
    """Root of the source checkout this package runs from.

    Only meaningful when running from a checkout (including an editable
    install): src/health_data_parser/utils/paths.py is three levels below it.
    """
    return Path(__file__).resolve().parents[3]


def default_user_data_dir() -> Path:
    """Default location for the user's own CSVs (gitignored)."""
    return repo_root() / "data" / "my_data"
