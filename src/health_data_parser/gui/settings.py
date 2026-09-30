import os

from PySide6.QtCore import QSettings, QStandardPaths

MAX_RECENT_EXPORT_DIRS = 10


def app_settings():
    """The app's settings, in an INI file in the per-user app config location.

    INI rather than the platform default (the registry on Windows) so the
    location comes from QStandardPaths, which Qt's test mode redirects.
    """
    directory = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return QSettings(os.path.join(directory, "settings.ini"), QSettings.Format.IniFormat)


def string_list(settings, key):
    """A list of strings stored with setValue(key, list)."""
    value = settings.value(key, [])
    # INI files give back a lone entry as a str, and an empty list as None
    if isinstance(value, str):
        value = [value]
    return [item for item in (value or []) if item]


def recent_export_dirs(settings):
    return string_list(settings, "recent_export_dirs")


def remember_export_dir(settings, path):
    """Put `path` first in the recent export directories."""
    directories = [path] + [d for d in recent_export_dirs(settings) if d != path]
    settings.setValue("recent_export_dirs", directories[:MAX_RECENT_EXPORT_DIRS])
