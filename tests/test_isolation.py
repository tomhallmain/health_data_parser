"""Checks that the conftest bootstrap keeps tests away from the user's real
profile: home/app-data directories, log files, and matplotlib config/cache."""
import logging
import os
from pathlib import Path

import matplotlib

import health_data_parser.model.units  # noqa: F401  (creates a project logger with a file handler)


def test_home_directories_are_redirected(test_home):
    assert Path.home() == test_home
    assert Path(os.path.expanduser("~")) == test_home
    for var in ["APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"]:
        assert Path(os.environ[var]).is_relative_to(test_home), var


def test_log_files_are_written_under_test_home(test_home):
    file_handlers = [
        handler
        for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    ]
    assert file_handlers
    for handler in file_handlers:
        assert Path(handler.baseFilename).is_relative_to(test_home), handler.baseFilename


def test_matplotlib_uses_test_config_and_defaults(mpl_config_dir):
    # matplotlib resolves these paths, so compare resolved forms (macOS /var symlink,
    # Windows 8.3 short names in TEMP)
    assert Path(matplotlib.get_configdir()).resolve() == mpl_config_dir.resolve()
    assert Path(matplotlib.get_cachedir()).resolve() == mpl_config_dir.resolve()
    assert matplotlib.get_backend().lower() == "agg"
    # No user matplotlibrc: the rc file in use is the one bundled with matplotlib
    assert Path(matplotlib.matplotlib_fname()).resolve().parent == Path(matplotlib.get_data_path()).resolve()
