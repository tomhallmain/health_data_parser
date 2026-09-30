import pytest

from health_data_parser.errors import HealthDataParseError
from health_data_parser.gui.main_window import MainWindow
from health_data_parser.gui.settings import recent_export_dirs
from health_data_parser.gui.worker import RunWorker
from health_data_parser.options import ParseOptions
from health_data_parser.pipeline import DataParser
from health_data_parser.utils.translations import _

RUN_TIMEOUT_MS = 60_000


@pytest.fixture
def window(qtbot, monkeypatch):
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    errors = []
    monkeypatch.setattr(main_window, "show_error",
                        lambda title, message, details="": errors.append((message, details)))
    main_window.errors = errors
    return main_window


def run_to_completion(window, qtbot):
    window.start_run()
    assert window.is_running
    qtbot.waitUntil(lambda: not window.is_running, timeout=RUN_TIMEOUT_MS)


def test_run_is_blocked_until_the_options_are_valid(window, pipeline_export):
    assert not window.run_button.isEnabled()
    window.start_run()
    assert not window.is_running

    window.panel.export_dir.set_path(str(pipeline_export))

    assert window.run_button.isEnabled()


def test_full_run_fills_the_results(window, qtbot, pipeline_export, pdf_reports, settings):
    window.panel.export_dir.set_path(str(pipeline_export))

    run_to_completion(window, qtbot)

    assert window.errors == []
    assert len(pdf_reports) == 1
    assert window.status_label.text() == _("Report generated.")
    assert window.progress.value() == window.progress.maximum()
    assert window.output_dir == str(pipeline_export)
    assert window.pdf_path == str(pipeline_export / "HealthReport-stub.pdf")
    assert _("Total Observations: {0}").format(3) in window.summary_text.toPlainText()
    assert window.lab_model.rowCount() == 3
    assert window.vitals_model.rowCount() > 0
    assert window.open_folder_button.isEnabled()
    assert recent_export_dirs(settings) == [str(pipeline_export)]
    assert window.run_button.isEnabled()


def test_run_logs_reach_the_log_panel(window, qtbot, pipeline_export, pdf_reports):
    window.panel.export_dir.set_path(str(pipeline_export))

    run_to_completion(window, qtbot)

    qtbot.waitUntil(lambda: "HealthReport-stub.pdf" in window.log_view.toPlainText())


def test_options_are_restored_in_a_new_window(window, qtbot, pipeline_export, pdf_reports):
    window.panel.export_dir.set_path(str(pipeline_export))
    window.panel.start_year.setValue(2022)
    run_to_completion(window, qtbot)

    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened.panel.options() == window.panel.options()
    assert reopened.panel.export_dir.history() == [str(pipeline_export)]


class _FailingParser:
    error = HealthDataParseError("Nothing to report")

    def __init__(self, options):
        pass

    def run(self, progress=None, is_cancelled=None):
        raise self.error


def test_parse_error_is_shown(window, qtbot, pipeline_export, monkeypatch):
    monkeypatch.setattr("health_data_parser.gui.worker.DataParser", _FailingParser)
    window.panel.export_dir.set_path(str(pipeline_export))

    run_to_completion(window, qtbot)

    assert window.errors == [("Nothing to report", "")]
    assert window.status_label.text() == "Nothing to report"
    assert window.run_button.isEnabled()


def test_unexpected_error_is_shown_with_its_traceback(window, qtbot, pipeline_export, monkeypatch):
    monkeypatch.setattr(_FailingParser, "error", ValueError("bad value"))
    monkeypatch.setattr("health_data_parser.gui.worker.DataParser", _FailingParser)
    window.panel.export_dir.set_path(str(pipeline_export))

    run_to_completion(window, qtbot)

    [(message, details)] = window.errors
    assert message == _("Unexpected error: {0}").format("bad value")
    assert "Traceback" in details and "ValueError: bad value" in details


def test_worker_cancelled_before_it_starts(qtbot, pipeline_export, pdf_reports):
    worker = RunWorker(ParseOptions(str(pipeline_export)))
    worker.cancel()

    with qtbot.waitSignal(worker.signals.cancelled):
        worker.run()

    assert pdf_reports == []


def test_load_results(window, pipeline_export, pdf_reports, monkeypatch):
    DataParser(ParseOptions(str(pipeline_export))).run()
    monkeypatch.setattr(window, "ask_results_dir", lambda: str(pipeline_export))

    window.load_results_dialog()

    assert window.lab_model.rowCount() == 3
    assert window.output_dir == str(pipeline_export)


def test_load_results_without_observations_json(window, tmp_path, monkeypatch):
    monkeypatch.setattr(window, "ask_results_dir", lambda: str(tmp_path))

    window.load_results_dialog()

    assert window.lab_model.rowCount() == 0
    assert "observations.json" in window.summary_text.toPlainText()


def test_manage_symptoms_starts_a_file_in_the_user_data_dir(window, tmp_path, monkeypatch):
    data_dir = tmp_path / "my_data"
    monkeypatch.setattr("health_data_parser.gui.main_window.default_user_data_dir", lambda: data_dir)

    window.manage_symptoms()

    path = data_dir / "symptom_set.csv"
    assert path.exists()
    assert window.panel.symptom_csv.path() == str(path)
    assert window.symptoms.path == str(path)
    assert window.tabs.currentIndex() == window.symptoms_tab_index


def test_manage_symptoms_opens_the_chosen_file(window, tmp_path):
    path = tmp_path / "symptoms.csv"
    path.write_text("Name,Start Date,End Date,Medications,Stimulants,Comment,Severity\n"
                    "Cough,2022-01,,,,,2\n", encoding="utf-8")
    window.panel.symptom_csv.set_path(str(path))

    window.manage_symptoms()

    assert [s.name for s in window.symptoms.model.symptoms] == ["Cough"]


def test_close_is_cancelled_by_unsaved_symptoms(window, monkeypatch):
    # The first close is cancelled at the unsaved-changes prompt
    answers = iter([False])
    monkeypatch.setattr(window.symptoms, "maybe_save", lambda: next(answers, True))

    assert not window.close()
    assert window.close()
