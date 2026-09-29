from datetime import datetime
import json

import pytest

from ui.statistics_data import (
    abnormal_counts_by_interpretation, lab_result_rows, load_observations_json,
    observation_counts_by_date, observation_counts_by_year, summarize, summary_lines,
    vital_sign_rows)


def observation(date, test, value_string, reference_range=None):
    result = {"valueString": value_string}
    if reference_range is not None:
        result["referenceRange"] = reference_range
    return {"observationId": f"{date}-{test}", "date": date, "category": "Laboratory",
            "testMeta": {"testDescription": test, "codings": {}}, "observedResult": result}


def reference_range(expected, interpretation=None):
    out = {"expectedValue": expected, "isAbnormal": interpretation is not None,
           "isRangeType": True, "unit": None, "isBinaryType": False}
    if interpretation is not None:
        out["interpretation"] = interpretation
    return out


@pytest.fixture
def json_data():
    """Shaped like Reporter.report_all_data_json_and_pdf output (observations newest first)."""
    return {
        "meta": {
            "description": "Health Records Report",
            "processTime": "2024-01-01 00:00:00.000000",
            "observationCount": 4,
            "vitalSignsObservationCount": 3,
            "mostRecentResult": "2023-04-05",
            "earliestResult": "2022-11-20",
            "heartRateMonitoringWearableDetected": False,
        },
        "vitalSigns": [
            {"vital": "Height", "count": 0, "sum": 0, "avg": None, "max": None, "min": None,
             "mostRecent": None, "unit": "cm"},
            {"vital": "Weight", "count": 2, "avg": 150.25, "max": 151.0, "min": 149.5,
             "mostRecent": {"time": "2023-04-05 08:00:00 +0000", "value": 151.0},
             "unit": "lb", "stDev": 0.75},
            {"vital": "Blood Pressure", "count": 1, "labels": ["BP Systolic", "BP Diastolic"],
             "avg": [120.0, 80.0], "max": [120, 80], "min": [120, 80],
             "mostRecent": {"time": "2023-01-10 08:00:00 +0000", "value": [120, 80]},
             "unit": "mmHg", "stDev": [0.0, 0.0]},
        ],
        "abnormalResults": {
            "meta": {"codesWithAbnormalResultsCount": 2, "totalAbnormalResultsCount": 3,
                     "includesInRangeAbnormalities": True, "inRangeAbnormalBoundary": 0.15},
            "codesWithAbnormalResults": {},
        },
        "observations": [
            observation("2023-04-05", "Glucose", "105 mg/dL", reference_range("70-99 mg/dL", "HIGH OUT OF RANGE")),
            observation("2023-04-05", "Hemoglobin", "13.6 g/dL", reference_range("13.5-17.5 g/dL", "Low in range")),
            observation("2023-01-10", "Glucose", "90 mg/dL", reference_range("70-99 mg/dL")),
            observation("2022-11-20", "Ferritin", "20 ng/mL", reference_range("30-400 ng/mL", "LOW OUT OF RANGE")),
            observation("2022-11-20", "Comment", "See report"),
        ],
    }


class TestLoadObservationsJson:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_observations_json(str(tmp_path)) == {}

    def test_loads_file(self, tmp_path, json_data):
        (tmp_path / "observations.json").write_text(json.dumps(json_data), encoding="utf-8")
        assert load_observations_json(str(tmp_path)) == json_data

    def test_corrupt_file_raises(self, tmp_path):
        (tmp_path / "observations.json").write_text("{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_observations_json(str(tmp_path))


class TestSummary:
    def test_summarize(self, json_data):
        assert summarize(json_data) == {
            "observation_count": 4,
            "vital_signs_observation_count": 3,
            "unique_test_count": 4,
            "earliest_result": "2022-11-20",
            "most_recent_result": "2023-04-05",
            "abnormal_result_count": 3,
            "codes_with_abnormal_results_count": 2,
        }

    def test_summary_of_custom_only_report(self):
        # --custom_only reports carry only "meta" with no observation fields
        summary = summarize({"meta": {"description": "Health Records Report"}})
        assert summary["observation_count"] == 0
        assert summary["abnormal_result_count"] == 0
        assert summary["earliest_result"] is None

    def test_summary_lines_include_date_range_when_known(self, json_data):
        assert "Date Range: 2022-11-20 to 2023-04-05" in summary_lines(json_data)
        assert not any(line.startswith("Date Range") for line in summary_lines({}))


class TestLabResultRows:
    def test_rows(self, json_data):
        assert lab_result_rows(json_data) == [
            ("2023-04-05", "Glucose", "105 mg/dL", "70-99 mg/dL", "HIGH OUT OF RANGE"),
            ("2023-04-05", "Hemoglobin", "13.6 g/dL", "13.5-17.5 g/dL", "Low in range"),
            ("2023-01-10", "Glucose", "90 mg/dL", "70-99 mg/dL", "Normal"),
            ("2022-11-20", "Ferritin", "20 ng/mL", "30-400 ng/mL", "LOW OUT OF RANGE"),
            ("2022-11-20", "Comment", "See report", "", ""),
        ]

    def test_missing_test_meta_leaves_test_blank(self):
        obs = observation("2023-01-10", "Glucose", "90 mg/dL")
        del obs["testMeta"]
        assert lab_result_rows({"observations": [obs]}) == [("2023-01-10", "", "90 mg/dL", "", "")]


class TestVitalSignRows:
    def test_rows(self, json_data):
        assert vital_sign_rows(json_data) == [
            ("Weight", "lb", 151.0, "2023-04-05", 149.5, 151.0, 150.2, 2),
            ("BP Systolic", "mmHg", 120, "2023-01-10", 120, 120, 120.0, 1),
            ("BP Diastolic", "mmHg", 80, "2023-01-10", 80, 80, 80.0, 1),
        ]

    def test_all_vitals_output_keeps_list(self, json_data):
        # --json_add_all_vitals leaves each vital's full "list" in place
        json_data["vitalSigns"][1]["list"] = [{"time": "2023-04-05 08:00:00 +0000", "value": 151.0}]
        assert vital_sign_rows(json_data)[0][0] == "Weight"

    def test_no_vitals(self):
        assert vital_sign_rows({}) == []


class TestCounts:
    def test_observation_counts_by_year(self, json_data):
        assert observation_counts_by_year(json_data) == [("2022", 2), ("2023", 3)]

    def test_abnormal_counts_are_ordered_by_severity(self, json_data):
        assert abnormal_counts_by_interpretation(json_data) == [
            ("LOW OUT OF RANGE", 1), ("Low in range", 1), ("HIGH OUT OF RANGE", 1)]

    def test_observation_counts_by_date(self, json_data):
        assert observation_counts_by_date(json_data) == [
            (datetime(2022, 11, 20), 2), (datetime(2023, 1, 10), 1), (datetime(2023, 4, 5), 2)]

    def test_abnormal_counts_by_date(self, json_data):
        assert observation_counts_by_date(json_data, abnormal_only=True) == [
            (datetime(2022, 11, 20), 1), (datetime(2023, 4, 5), 2)]

    def test_empty(self):
        assert observation_counts_by_year({}) == []
        assert abnormal_counts_by_interpretation({}) == []
        assert observation_counts_by_date({}) == []
