"""
IMPORTANT: The environment below must be set at module load time, before any
project module or matplotlib is imported. Project modules create their loggers
(and so their log files) at import, and matplotlib reads its config and cache
locations once, at import. Any nested conftest.py must not import either
ahead of this file.
"""
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent


def _is_isolation_sensitive(name, module):
    if name == "matplotlib" or name.split(".")[0] == "health_data_parser":
        return True
    # Anything else loaded from the repo, e.g. the root compatibility scripts.
    # Namespace packages have __path__ but no __file__.
    locations = [getattr(module, "__file__", None), *(getattr(module, "__path__", None) or [])]
    for loc in locations:
        if not loc:
            continue
        path = Path(loc).resolve()
        if path.is_relative_to(REPO_ROOT) and not path.is_relative_to(TESTS_DIR):
            return True
    return False


_already_imported = sorted(name for name, module in list(sys.modules.items())
                           if _is_isolation_sensitive(name, module))
if _already_imported:
    raise RuntimeError("Imported before tests/conftest.py could isolate them from user "
                       f"config and caches: {', '.join(_already_imported)}")

# A throwaway home for the session: everything resolved from the user's home or
# app-data directories (the app's log directory, reportlab user settings, any
# future cache/config) lands here, never in the real profile.
TEST_HOME = Path(tempfile.mkdtemp(prefix="health_data_parser_tests_"))
for _var, _subdir in [("HOME", ""), ("USERPROFILE", ""),
                      ("APPDATA", "AppData/Roaming"), ("LOCALAPPDATA", "AppData/Local"),
                      ("XDG_CONFIG_HOME", ".config"), ("XDG_CACHE_HOME", ".cache"),
                      ("XDG_DATA_HOME", ".local/share")]:
    _path = TEST_HOME / _subdir
    _path.mkdir(parents=True, exist_ok=True)
    os.environ[_var] = str(_path)

# English messages whatever the developer's locale: the translation module reads
# LANG once, at import
os.environ["LANG"] = "en_US.UTF-8"

# Matplotlib: headless backend, built-in default rcParams (no user matplotlibrc or
# styles), and a config/cache dir owned by the tests. That dir is kept between
# runs so the font cache is not rebuilt every session.
os.environ["MPLBACKEND"] = "Agg"
os.environ.pop("MATPLOTLIBRC", None)
MPL_CONFIG_DIR = Path(tempfile.gettempdir()) / "health_data_parser_tests_mplconfig"
MPL_CONFIG_DIR.mkdir(exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)

# Qt: no display needed, and the Qt binding matplotlib's Qt backend uses
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_API"] = "pyside6"

import pytest
from PySide6.QtCore import QStandardPaths

# Qt's per-user locations (QSettings files included) move to a test location
# under the throwaway HOME
QStandardPaths.setTestModeEnabled(True)


def pytest_sessionfinish(session, exitstatus):
    # Close the app's log files first so the directory can be removed on Windows
    for logger in list(logging.Logger.manager.loggerDict.values()):
        if not isinstance(logger, logging.Logger):
            continue
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler):
                handler.close()
                logger.removeHandler(handler)
    shutil.rmtree(TEST_HOME, ignore_errors=True)


def repoint_singleton_bindings(monkeypatch, attr_name, old_obj, new_obj):
    """Repoint every imported module's module-level binding of *old_obj* to
    *new_obj* (undone automatically by monkeypatch at test teardown).

    A module that does `from some.module import some_singleton` holds its own
    reference, so patching only the source module leaves that binding stale.
    Sweeping sys.modules catches every such binding; the identity comparison
    guarantees only bindings to the exact old object are touched, and modules
    imported later get the new object through the patched source module.
    """
    for module in list(sys.modules.values()):
        try:
            if getattr(module, attr_name, None) is old_obj:
                monkeypatch.setattr(module, attr_name, new_obj)
        except Exception:
            continue


@pytest.fixture(scope="session")
def test_home():
    return TEST_HOME


@pytest.fixture(scope="session")
def mpl_config_dir():
    return MPL_CONFIG_DIR


@pytest.fixture(autouse=True)
def reset_app_globals():
    """Reset process-wide state before each test so one test's leftovers don't
    pollute the next; the teardown reset keeps a failing test's state from
    leaking too."""
    def _reset():
        # Chart code creates figures through pyplot and never closes them
        if "matplotlib.pyplot" in sys.modules:
            sys.modules["matplotlib.pyplot"].close("all")

    _reset()
    yield
    _reset()


def lab_observation(display="Glucose", code="2345-7", date="2023-04-05", value=105,
                    unit="mg/dL", range_text="70-99 mg/dL", category="Laboratory",
                    subject="Test Subject"):
    """A FHIR Observation shaped like those in an Apple Health clinical-records export."""
    observation = {
        "resourceType": "Observation",
        "category": {"text": category},
        "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}]},
        "effectiveDateTime": date + "T08:00:00Z",
        "subject": {"display": subject},
        "valueQuantity": {"value": value, "unit": unit},
    }
    if range_text is not None:
        observation["referenceRange"] = [{"text": range_text}]
    return observation


def blood_pressure_observation(systolic=120, diastolic=80, date="2023-04-05"):
    """A FHIR vital-signs Observation carrying systolic/diastolic LOINC components."""
    def component(code, value):
        return {"code": {"coding": [{"system": "http://loinc.org", "code": code}]},
                "valueQuantity": {"value": value, "unit": "mm[Hg]"}}
    return {
        "category": {"text": "Vital Signs"},
        "code": {"text": "Blood Pressure"},
        "effectiveDateTime": date + "T08:00:00Z",
        "component": [component("8480-6", systolic), component("8462-4", diastolic)],
    }


@pytest.fixture
def make_lab_observation():
    return lab_observation


@pytest.fixture
def make_blood_pressure_observation():
    return blood_pressure_observation


@pytest.fixture
def write_json():
    def _write(path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path
    return _write


@pytest.fixture
def export_dir(tmp_path, write_json):
    """An export directory whose clinical-records folder holds one lab observation."""
    export = tmp_path / "apple_health_export"
    write_json(export / "clinical-records" / "Observation-1.json", lab_observation())
    return export


# Shared by test_pipeline.py and the GUI run tests
@pytest.fixture
def pipeline_export(tmp_path, write_json, make_lab_observation, make_blood_pressure_observation):
    """Two dates of labs (one high result, one low-in-range) plus a set of vital signs."""
    export = tmp_path / "apple_health_export"
    records = export / "clinical-records"
    observations = [
        make_lab_observation(date="2023-01-10", value=90),
        make_lab_observation(date="2023-04-05", value=105),
        make_lab_observation(display="Hemoglobin", code="718-7", date="2023-04-05", value=13.6,
                             unit="g/dL", range_text="13.5-17.5 g/dL"),
    ]
    vitals = [("Pulse", "8867-4", 62, "/min"), ("Body height", "8302-2", 180, "cm"),
              ("Body weight", "29463-7", 180, "lb"), ("Body temperature", "8310-5", 98.6, "[degF]")]
    for display, code, value, unit in vitals:
        observations.append(make_lab_observation(display=display, code=code, value=value, unit=unit,
                                                 range_text=None, category="Vital Signs"))
    observations.append(make_blood_pressure_observation())
    for i, observation in enumerate(observations):
        write_json(records / f"Observation-{i}.json", observation)
    return export


@pytest.fixture
def pdf_reports(monkeypatch):
    """Replaces the PDF report with a stub; yields the json_data each run passed to it."""
    created = []

    class _RecordingReport:
        def __init__(self, output_path, subject, filename_affix, verbose=False, highlight_abnormal=True):
            self.filename = "HealthReport-stub.pdf"

        def create_pdf(self, json_data, store, vital_stats_graph=None, symptom_charts=None, food_chart=None):
            created.append(json_data)

    monkeypatch.setattr("health_data_parser.reporting.outputs.Report", _RecordingReport)
    return created


@pytest.fixture
def json_parser_args(tmp_path):
    """The subset of ParseOptions that ClinicalRecordsParser reads."""
    base_dir = tmp_path / "clinical-records"
    base_dir.mkdir()
    return SimpleNamespace(
        verbose=False,
        base_dir=str(base_dir),
        subject={},
        start_year=None,
        skip_long_values=False,
        skip_in_range_abnormal_results=False,
        in_range_abnormal_boundary=0.15,
        skip_dates=[],
    )
