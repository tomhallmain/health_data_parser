import sys
from types import SimpleNamespace

import pytest

import health_data_parser.reporting.pdf.report as report_module
from health_data_parser.reporting.pdf.report import Report


class RecordingCanvas:
    """Stands in for pdf_creator: records shown text, accepts every other call."""

    def __init__(self):
        self.lines = []

    def show_text(self, text):
        self.lines.extend(text.split("\n"))

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture
def report(monkeypatch, tmp_path):
    # Section builders look up fonts by name only; no font file is loaded here
    monkeypatch.setattr(report_module, "get_font", lambda font=None: ("Helvetica", None))
    monkeypatch.setattr(report_module, "get_bold_font", lambda font=None: ("Helvetica-Bold", None))
    return Report(str(tmp_path), {}, "2024-01-01")


def pulse_graph(in_motion, resting):
    return SimpleNamespace(
        values_in_motion=in_motion, values_resting=resting,
        avg_in_motion=110.0, avg_resting=70.0,
        save_loc_minutes_data="minutes.png", save_loc_dates_data="dates.png",
        pulse_dates=[738000, 738010])


PULSE_JSON = {"vitalSigns": [{"vital": "Pulse", "count": 4, "avg": 80.0, "stDev": 5.0}]}


class TestHeartStatsSection:
    @pytest.mark.xfail(reason="Known bug: percent in motion is in-motion / resting, not "
                              "in-motion / all readings")
    def test_percent_in_motion(self, report):
        canvas = RecordingCanvas()
        report.add_heart_stats(canvas, PULSE_JSON, pulse_graph([110], [60, 70, 80]))
        assert any("Percent in motion: 25%" in line for line in canvas.lines)

    @pytest.mark.xfail(raises=ZeroDivisionError,
                       reason="Known bug: percent in motion divides by the resting count")
    def test_no_resting_readings(self, report):
        canvas = RecordingCanvas()
        report.add_heart_stats(canvas, PULSE_JSON, pulse_graph([110, 120], []))
        assert any("Percent in motion: 100%" in line for line in canvas.lines)


@pytest.mark.skipif(sys.platform != "win32",
                    reason="pdf_creator only defines fonts for Windows and macOS, and the macOS "
                           "font (MesloLGS NF) is not installed by default")
@pytest.mark.xfail(reason="Known bug: show_table draws a table taller than the space left on the "
                          "page past the bottom margin instead of continuing on a new page")
def test_tall_table_stays_above_bottom_margin(tmp_path):
    from health_data_parser.reporting.pdf.canvas import get_font, pdf_creator
    creator = pdf_creator(800, 50, str(tmp_path / "table.pdf"), "footer", False)
    creator.set_font(get_font()[0], 8)
    creator.set_leading(8)
    creator.height = 200
    table = [["Code", "Value"]] + [[f"Test {i}", str(i)] for i in range(80)]

    creator.show_table(table, [], 50)

    assert creator.height >= 50
