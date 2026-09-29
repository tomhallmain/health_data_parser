"""End-to-end runs of DataParser over a small synthetic export.

The PDF step is replaced by a recording stub everywhere except
test_real_pdf_report: pdf_creator only defines fonts for Windows and macOS,
and those tests pin down the data files the PDF is built from.
"""
import csv
import json
import sys

import pytest

from health_data_parser.options import HealthDataParseArgs
from health_data_parser.pipeline import DataParser
from health_data_parser.analysis.summary import lab_result_rows, summarize, vital_sign_rows

SYMPTOM_CSV = (
    "Symptom/Condition,Onset/Time of Diagnosis,Conclusion,Medications,Stimulants,Comment,Severity\n"
    "Headache,2021-02,2021-06,Medication A,Stimulant A,,2\n"
    "Fatigue,2020-03,,Medication A,,,1\n"
)
FOOD_CSV = (
    "logDateTime,logType,mealType,foodName,foodPrep,foodServingSize,categories,okDiets,warningDiets,dangerDiets\n"
    "2022-03-11 08:00:00,meal,Breakfast,Oats,Boiled,Huge,,,Low FODMAP,\n"
    "2022-03-12 12:30:00,meal,Lunch,Rice,Steamed,Huge,,,,\n"
)


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

        def create_pdf(self, json_data, data, symptom_data, pulse_stats_graph, food_data):
            created.append(json_data)

    monkeypatch.setattr("health_data_parser.reporting.outputs.Report", _RecordingReport)
    return created


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def vital(json_data, name):
    return next(v for v in json_data["vitalSigns"] if v["vital"] == name)


@pytest.fixture
def run_output(pipeline_export, pdf_reports):
    DataParser(HealthDataParseArgs(str(pipeline_export))).run()
    json_data = json.loads((pipeline_export / "observations.json").read_text(encoding="utf-8"))
    return pipeline_export, json_data


class TestFullRun:
    def test_pdf_is_requested_once(self, run_output, pdf_reports):
        assert len(pdf_reports) == 1

    def test_json_meta(self, run_output):
        _, json_data = run_output
        meta = json_data["meta"]
        assert meta["observationCount"] == 3
        assert meta["mostRecentResult"] == "2023-04-05"
        assert meta["earliestResult"] == "2023-01-10"
        assert meta["heartRateMonitoringWearableDetected"] is False

    def test_json_abnormal_results(self, run_output):
        _, json_data = run_output
        abnormal = json_data["abnormalResults"]
        assert abnormal["meta"]["totalAbnormalResultsCount"] == 2
        assert abnormal["meta"]["codesWithAbnormalResultsCount"] == 2
        assert abnormal["codesWithAbnormalResults"] == {
            "Glucose": ["HIGH OUT OF RANGE"], "Hemoglobin": ["Low in range"]}

    def test_json_observations(self, run_output):
        _, json_data = run_output
        observations = json_data["observations"]
        assert [o["date"] for o in observations] == ["2023-04-05", "2023-04-05", "2023-01-10"]
        assert {o["testMeta"]["testDescription"] for o in observations} == {"Glucose", "Hemoglobin"}

    def test_json_vital_signs(self, run_output):
        _, json_data = run_output
        assert vital(json_data, "Height")["avg"] == pytest.approx(180)
        assert vital(json_data, "Weight")["avg"] == pytest.approx(180)
        assert vital(json_data, "BMI")["mostRecent"]["value"] == pytest.approx(25.2, abs=0.01)
        assert vital(json_data, "Temperature")["avg"] == pytest.approx(37.0)
        assert vital(json_data, "Pulse")["count"] == 1
        assert vital(json_data, "Blood Pressure")["avg"] == [120.0, 80.0]
        assert "Steps" not in {v["vital"] for v in json_data["vitalSigns"]}
        # Per-reading lists are only kept with --json_add_all_vitals
        assert all("list" not in v for v in json_data["vitalSigns"])

    def test_temperature_unit_matches_normalized_values(self, run_output):
        _, json_data = run_output
        assert vital(json_data, "Temperature")["unit"] == "C"

    def test_abnormal_results_by_code_text(self, run_output):
        export, _ = run_output
        text = (export / "abnormal_results_by_code.txt").read_text(encoding="utf-8")
        assert "Abnormal results found for code Glucose:" in text
        assert "2023-04-05: HIGH OUT OF RANGE - observed 105 mg/dL - range 70.0 - 99.0" in text
        assert "2023-04-05: Low in range - observed 13.6 g/dL - range 13.5 - 17.5" in text

    def test_abnormal_results_by_interpretation_csv(self, run_output):
        export, _ = run_output
        rows = read_csv(export / "abnormal_results_by_interpretation.csv")
        assert rows[0][1:] == ["LOW OUT OF RANGE", "Low in range", "Non-negative result",
                               "High in range", "HIGH OUT OF RANGE"]
        assert rows[1:] == [["Glucose", "", "", "", "", "+++"], ["Hemoglobin", "", "--", "", "", ""]]

    def test_abnormal_results_csv(self, run_output):
        export, _ = run_output
        rows = read_csv(export / "abnormal_results.csv")
        assert rows[0][1:] == ["2023-04-05"]
        assert rows[1:] == [["Glucose", "105 mg/dL +++"], ["Hemoglobin", "13.6 g/dL --"]]

    @pytest.mark.parametrize("name", ["observations.csv", "abnormal_results.csv",
                                      "abnormal_results_by_interpretation.csv"])
    def test_csv_row_endings(self, run_output, name):
        export, _ = run_output
        assert b"\r\r\n" not in (export / name).read_bytes()

    def test_observations_csv(self, run_output):
        export, _ = run_output
        rows = read_csv(export / "observations.csv")
        assert rows[0][1:] == ["2023-04-05 range", "2023-04-05 result",
                               "2023-01-10 range", "2023-01-10 result"]
        stripped = [[cell.strip() for cell in row] for row in rows[1:]]
        assert stripped == [
            ["Glucose", "70-99 mg/dL", "105 mg/dL +++", "70-99 mg/dL", "90 mg/dL"],
            ["Hemoglobin", "13.5-17.5 g/dL", "13.6 g/dL --", "", ""],
        ]


class TestStatisticsContract:
    """ui/statistics_data.py reads the observations.json this pipeline writes."""

    def test_summary(self, run_output):
        _, json_data = run_output
        summary = summarize(json_data)
        assert summary["observation_count"] == 3
        assert summary["unique_test_count"] == 2
        assert summary["abnormal_result_count"] == 2

    def test_lab_result_rows(self, run_output):
        _, json_data = run_output
        assert sorted(lab_result_rows(json_data)) == [
            ("2023-01-10", "Glucose", "90 mg/dL", "70-99 mg/dL", "Normal"),
            ("2023-04-05", "Glucose", "105 mg/dL", "70-99 mg/dL", "HIGH OUT OF RANGE"),
            ("2023-04-05", "Hemoglobin", "13.6 g/dL", "13.5-17.5 g/dL", "Low in range"),
        ]

    def test_vital_sign_rows(self, run_output):
        _, json_data = run_output
        rows = {row[0]: row for row in vital_sign_rows(json_data)}
        assert set(rows) == {"Height", "Weight", "BMI", "Temperature", "Pulse",
                             "BP Systolic", "BP Diastolic"}
        assert rows["BP Systolic"][2] == 120.0
        assert rows["Pulse"][3] == "2023-04-05"


class TestCustomDataRuns:
    def test_custom_only_report(self, pipeline_export, pdf_reports):
        symptoms = pipeline_export / "symptoms.csv"
        symptoms.write_text(SYMPTOM_CSV, encoding="utf-8")
        args = HealthDataParseArgs(str(pipeline_export))
        args.symptom_data_csv = str(symptoms)

        DataParser(args).create_custom_report()

        json_data = json.loads((pipeline_export / "observations.json").read_text(encoding="utf-8"))
        assert set(json_data) == {"meta"}
        assert (pipeline_export / "symptoms.png").exists()
        assert (pipeline_export / "symptoms_unresolved.png").exists()
        assert not (pipeline_export / "observations.csv").exists()

    def test_extra_observations_are_merged(self, pipeline_export, pdf_reports):
        extra = pipeline_export / "extra.csv"
        extra.write_text(
            "Subject,Performer,Collection Date,Report Description,LOINC Code,Code Description,Value,Range,Units\n"
            '"Doe, Jane",Organization/ExampleLab,2022-11-20,Iron Panel,2276-4,Ferritin,20,30-400,ng/mL\n',
            encoding="utf-8")
        args = HealthDataParseArgs(str(pipeline_export))
        args.extra_observations_csv = str(extra)

        DataParser(args).run()

        json_data = json.loads((pipeline_export / "observations.json").read_text(encoding="utf-8"))
        assert json_data["meta"]["observationCount"] == 4
        assert json_data["meta"]["earliestResult"] == "2022-11-20"
        assert "Ferritin" in json_data["abnormalResults"]["codesWithAbnormalResults"]


@pytest.mark.skipif(sys.platform != "win32",
                    reason="pdf_creator only defines fonts for Windows and macOS, and the macOS "
                           "font (MesloLGS NF) is not installed by default")
def test_real_pdf_report(pipeline_export):
    (pipeline_export / "symptoms.csv").write_text(SYMPTOM_CSV, encoding="utf-8")
    (pipeline_export / "food.csv").write_text(FOOD_CSV, encoding="utf-8")
    args = HealthDataParseArgs(str(pipeline_export))
    args.symptom_data_csv = str(pipeline_export / "symptoms.csv")
    args.food_data_csv = str(pipeline_export / "food.csv")

    DataParser(args).run()

    [pdf] = pipeline_export.glob("HealthReport*.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")
