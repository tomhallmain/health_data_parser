from types import SimpleNamespace

import pytest

from health_data_parser.ingest.fhir_json import ObservationRules, parse_observation
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.reporting.pdf import fonts
from health_data_parser.reporting.pdf.canvas import pdf_creator
from health_data_parser.reporting.pdf.fonts import regular_font
from health_data_parser.reporting.pdf.report import Report


class RecordingCanvas:
    """Stands in for pdf_creator: records shown text and tables, accepts every
    other call."""

    def __init__(self):
        self.lines = []
        self.tables = []

    def show_text(self, text):
        self.lines.extend(text.split("\n"))

    def show_table(self, data, extra_style_commands, x):
        self.tables.append(data)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture
def report(tmp_path):
    return Report(str(tmp_path), {}, "2024-01-01")


def pulse_graph(in_motion, resting):
    return SimpleNamespace(
        values_in_motion=in_motion, values_resting=resting,
        avg_in_motion=110.0, avg_resting=70.0,
        save_loc_minutes_data="minutes.png", save_loc_dates_data="dates.png",
        pulse_dates=[738000, 738010])


PULSE_JSON = {"vitalSigns": [{"vital": "Pulse", "count": 4, "avg": 80.0, "stDev": 5.0}]}


class TestHeartStatsSection:
    def test_percent_in_motion(self, report):
        canvas = RecordingCanvas()
        report.add_heart_stats(canvas, PULSE_JSON, pulse_graph([110], [60, 70, 80]))
        assert any("Percent in motion: 25%" in line for line in canvas.lines)

    def test_no_resting_readings(self, report):
        canvas = RecordingCanvas()
        report.add_heart_stats(canvas, PULSE_JSON, pulse_graph([110, 120], []))
        assert any("Percent in motion: 100%" in line for line in canvas.lines)


def lab(make_lab_observation, display, code, date, value, range_text="70-99 mg/dL", unit="mg/dL"):
    return make_lab_observation(display=display, code=code, date=date, value=value, unit=unit,
                                range_text=range_text)


@pytest.fixture
def store(make_lab_observation):
    """Glucose recorded under two LOINC codes (the same description, no shared
    coding), both abnormal, then an abnormal Iron result. With a row per code
    id, Iron's results would be labelled Glucose."""
    store = ObservationStore()
    for obs_id, data in [
        ("g1", lab(make_lab_observation, "Glucose", "2345-7", "2023-01-10", 150)),
        ("g2", lab(make_lab_observation, "Glucose", "2339-0", "2023-04-05", 40)),
        ("i1", lab(make_lab_observation, "Iron", "2498-4", "2023-04-05", 200, "60-170 ug/dL", "ug/dL")),
    ]:
        store.add(parse_observation(data, obs_id, store, ObservationRules()))
    return store


class TestByDateTables:
    def test_abnormal_table_has_one_row_per_code(self, report, store):
        assert store.code_ids("Glucose") == ["http://loinc.org2345-7", "http://loinc.org2339-0"]
        canvas = RecordingCanvas()

        report.add_abnormal_observations_by_date_tables(canvas, store)

        [table] = canvas.tables
        # No range is shared across dates here, so the empty Range column is dropped
        assert table[0] == ["Observation Code", "2023-04-05", "2023-01-10"]
        assert table[1:] == [["Glucose", "40\nmg/dL---", "150\nmg/dL+++"],
                             ["Iron", "200\nug/dL+++", ""]]

    def test_all_observations_table(self, report, store):
        canvas = RecordingCanvas()

        report.add_observations_by_date_tables(canvas, store)

        [table] = canvas.tables
        assert table[1:] == [["Glucose", "40\nmg/dL---", "150\nmg/dL+++"],
                             ["Iron", "200\nug/dL+++", ""]]
        assert canvas.lines[0] == "All Lab Observations"

    def test_dates_split_across_tables(self, report, make_lab_observation):
        store = ObservationStore()
        for day in range(1, 12):
            store.add(parse_observation(
                lab(make_lab_observation, "Glucose", "2345-7", f"2023-01-{day:02d}", 90),
                f"g{day}", store, ObservationRules()))
        canvas = RecordingCanvas()

        report.add_observations_by_date_tables(canvas, store)

        # Date columns per table (the first column is the code)
        assert [len(table[0]) - 1 for table in canvas.tables] == [9, 2]
        assert canvas.lines[-1] == "All Lab Observations (continued)"

    def test_all_observations_section_without_abnormal_results(self, report, make_lab_observation, tmp_path,
                                                                monkeypatch):
        store = ObservationStore()
        store.add(parse_observation(lab(make_lab_observation, "Glucose", "2345-7", "2023-01-10", 90),
                                    "g1", store, ObservationRules()))
        canvas = RecordingCanvas()
        monkeypatch.setattr("health_data_parser.reporting.pdf.report.pdf_creator",
                            lambda *args: canvas)
        json_data = {
            "meta": {"description": "Health Records Report", "processTime": "2024-01-01 00:00:00",
                     "observationCount": 1, "vitalSignsObservationCount": 0,
                     "mostRecentResult": "2023-01-10", "earliestResult": "2023-01-10",
                     "heartRateMonitoringWearableDetected": False},
            "observations": [],
        }

        report.create_pdf(json_data, store)

        assert "No abnormal results were found in Apple Health data export." in canvas.lines
        assert "All Lab Observations" in canvas.lines
        assert len(canvas.tables) == 1


def test_tall_table_continues_on_a_new_page(tmp_path):
    creator = pdf_creator(800, 50, str(tmp_path / "table.pdf"), "footer", False)
    creator.set_font(regular_font(), 8)
    creator.set_leading(8)
    creator.height = 200
    table = [["Code", "Value"]] + [[f"Test {i}", str(i)] for i in range(80)]

    creator.show_table(table, [], 50)

    assert creator.height >= 50


class TestFonts:
    @pytest.fixture(autouse=True)
    def clear_font_cache(self):
        fonts.report_fonts.cache_clear()
        yield
        fonts.report_fonts.cache_clear()

    def test_falls_back_to_helvetica(self, monkeypatch):
        monkeypatch.setattr(fonts, "_PLATFORM_FONTS", {
            fonts.sys.platform: (("Missing", "no-such-font.ttf"), ("Missing Bold", "no-such-font-bold.ttf"))})
        assert fonts.report_fonts() == ("Helvetica", "Helvetica-Bold")

    def test_platform_without_configured_fonts(self, monkeypatch):
        monkeypatch.setattr(fonts, "_PLATFORM_FONTS", {})
        assert (fonts.regular_font(), fonts.bold_font()) == ("Helvetica", "Helvetica-Bold")
