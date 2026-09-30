import pytest

from health_data_parser.gui.settings import app_settings


@pytest.fixture(autouse=True)
def clean_settings(qapp):
    """Each test starts with no saved settings (the file lives under the
    throwaway HOME, through QStandardPaths test mode)."""
    settings = app_settings()
    settings.clear()
    settings.sync()
    yield
    settings.clear()
    settings.sync()


@pytest.fixture
def settings():
    return app_settings()
