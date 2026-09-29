import json

import pytest

from data.observation_json_parser import ObservationJSONDataParser, ObservationsData
from generate_diagnostic_report_files import (
    construct_observation, generate_diagnostic_report_files, generate_report_id)
from utils.errors import HealthDataParseError

HEADER = ("Subject,Performer,Collection Date,Report Description,LOINC Code,"
          "Code Description,Value,Range,Units\n")
ROWS = [
    '"Doe, Jane",Organization/ExampleLab,2021-10-04,Autoimmune Screen,2489-3,Intrinsic Factor,0.72,0.0-2.5,ELISA\n',
    '"Doe, Jane",Organization/ExampleLab,2021-10-04,Autoimmune Screen,,Custom Marker,31,10-20,\n',
]


@pytest.fixture
def observations_csv(tmp_path):
    path = tmp_path / "observations_data.csv"
    path.write_text(HEADER + "".join(ROWS), encoding="utf-8")
    return path


@pytest.fixture
def base_dir(tmp_path):
    path = tmp_path / "export" / "clinical-records"
    path.mkdir(parents=True)
    return path


def custom_report_files(base_dir):
    return sorted(base_dir.glob("DiagnosticReport-*-CUSTOM.json"))


class TestGenerateDiagnosticReportFiles:
    def test_rows_for_one_report_are_saved_together(self, observations_csv, base_dir):
        assert generate_diagnostic_report_files(str(observations_csv), str(base_dir), False, False)

        [report_file] = custom_report_files(base_dir)
        report = json.loads(report_file.read_text(encoding="utf-8"))
        assert report["resourceType"] == "DiagnosticReport"
        assert report["category"]["coding"][0]["code"] == "LAB"
        assert report["subject"] == {"display": "Doe, Jane"}
        assert [obs["code"]["coding"][0]["display"] for obs in report["contained"]] == [
            "Intrinsic Factor", "Custom Marker"]
        assert report["result"] == [{"reference": "#1"}, {"reference": "#2"}]

    def test_regenerating_replaces_previous_file(self, observations_csv, base_dir):
        generate_diagnostic_report_files(str(observations_csv), str(base_dir), False, False)
        [first_file] = custom_report_files(base_dir)

        generate_diagnostic_report_files(str(observations_csv), str(base_dir), False, False)

        [second_file] = custom_report_files(base_dir)
        assert second_file != first_file

    def test_generated_reports_are_parsed(self, observations_csv, base_dir, json_parser_args):
        generate_diagnostic_report_files(str(observations_csv), str(base_dir), False, False)
        json_parser_args.base_dir = str(base_dir)

        data = ObservationJSONDataParser(json_parser_args, [], ObservationsData()).parse()

        assert set(data.observation_code_ids) == {"Intrinsic Factor", "Custom Marker"}
        assert list(data.abnormal_results) == ["CUSTOMCustom Marker"]

    def test_header_only_csv_returns_false(self, tmp_path, base_dir):
        path = tmp_path / "empty.csv"
        path.write_text(HEADER, encoding="utf-8")
        assert not generate_diagnostic_report_files(str(path), str(base_dir), False, False)
        assert custom_report_files(base_dir) == []

    @pytest.mark.parametrize("name", ["missing.csv", "observations.txt"])
    def test_invalid_csv_path_raises(self, tmp_path, base_dir, name):
        path = tmp_path / name
        if name.endswith(".txt"):
            path.write_text(HEADER, encoding="utf-8")
        with pytest.raises(HealthDataParseError, match="is invalid"):
            generate_diagnostic_report_files(str(path), str(base_dir), False, False)

    def test_empty_csv_path_raises(self, base_dir):
        with pytest.raises(HealthDataParseError, match="Missing"):
            generate_diagnostic_report_files("", str(base_dir), False, False)


class TestConstructObservation:
    def test_loinc_observation_with_units(self):
        obs = construct_observation("1", "Doe, Jane", "2021-10-04", "Intrinsic Factor",
                                    "2489-3", "0.0-2.5", 0.72, "ELISA")
        assert obs["code"] == {"coding": [
            {"system": "http://loinc.org", "display": "Intrinsic Factor", "code": "2489-3"}]}
        assert obs["referenceRange"] == [{
            "low": {"value": 0.0, "unit": "ELISA"},
            "high": {"value": 2.5, "unit": "ELISA"},
            "text": "0.0-2.5 ELISA"}]
        assert obs["valueQuantity"]["value"] == 0.72
        assert obs["valueQuantity"]["unit"] == "ELISA"
        assert obs["effectiveDateTime"] == "2021-10-04T12:00:00+00:00"

    def test_custom_code_without_units_or_range(self):
        obs = construct_observation("1", "Doe, Jane", "2021-10-04", "Custom Marker", "", "", "31", "")
        assert obs["code"]["coding"][0]["system"] == "CUSTOM"
        assert "referenceRange" not in obs
        assert obs["valueQuantity"] == {"value": 31}

    def test_integer_range(self):
        obs = construct_observation("1", "Doe, Jane", "2021-10-04", "Custom Marker", "", "10 - 20", 15, "")
        assert obs["referenceRange"][0]["low"] == {"value": 10}
        assert obs["referenceRange"][0]["high"] == {"value": 20}


def test_generate_report_id():
    assert generate_report_id("Doe, Jane", "Organization/Example-Lab", "2021-10-04", "Lipid Panel, Basic") == \
        "DoeJane.OrganizationExampleLab.2021-10-04.LipidPanelBasic"
