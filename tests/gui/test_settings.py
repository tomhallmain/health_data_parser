from pathlib import Path

from health_data_parser.gui.settings import (
    MAX_RECENT_EXPORT_DIRS, recent_export_dirs, remember_export_dir, string_list)


def test_settings_file_is_under_test_home(settings, test_home):
    assert Path(settings.fileName()).resolve().is_relative_to(test_home.resolve())


def test_recent_export_dirs_most_recent_first(settings):
    remember_export_dir(settings, "/a")
    remember_export_dir(settings, "/b")
    remember_export_dir(settings, "/a")

    assert recent_export_dirs(settings) == ["/a", "/b"]


def test_recent_export_dirs_are_capped(settings):
    for i in range(MAX_RECENT_EXPORT_DIRS + 3):
        remember_export_dir(settings, f"/export{i}")

    dirs = recent_export_dirs(settings)
    assert len(dirs) == MAX_RECENT_EXPORT_DIRS
    assert dirs[0] == f"/export{MAX_RECENT_EXPORT_DIRS + 2}"


def test_string_lists_survive_the_ini_file(settings):
    settings.setValue("one", ["only"])
    settings.setValue("none", [])
    settings.sync()

    assert string_list(settings, "one") == ["only"]
    assert string_list(settings, "none") == []
    assert string_list(settings, "missing") == []
