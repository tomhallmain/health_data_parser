from pathlib import Path

import pytest

from data.observation_json_parser import ObservationJSONDataParser, ObservationsData
from data.units import VitalSignCategory

GLUCOSE_ID = "http://loinc.org2345-7"


def parse(args, custom_data_files=None):
    parser = ObservationJSONDataParser(args, [] if custom_data_files is None else custom_data_files,
                                       ObservationsData())
    return parser.parse()


def diagnostic_report(contained, category_code="LAB"):
    return {
        "resourceType": "DiagnosticReport",
        "category": {"coding": [{"system": "http://hl7.org/fhir/v2/0074", "code": category_code}]},
        "contained": contained,
    }


class TestParse:
    def test_observation_files(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2023-01-10", value=90))
        write_json(base_dir / "Observation-2.json", make_lab_observation(date="2023-04-05", value=105))

        data = parse(json_parser_args)

        assert len(data.observations) == 2
        assert data.observation_dates == ["2023-04-05", "2023-01-10"]
        assert data.observation_code_ids == {"Glucose": [GLUCOSE_ID]}
        assert len(data.tests) == 1
        assert [obs.date for obs in data.abnormal_results[GLUCOSE_ID]] == ["2023-04-05"]
        assert json_parser_args.subject["name"] == "Test Subject"

    def test_diagnostic_report_with_contained_observations(self, json_parser_args, write_json,
                                                           make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "DiagnosticReport-1.json", diagnostic_report([
            make_lab_observation(),
            make_lab_observation(display="Hemoglobin", code="718-7", value=14,
                                 unit="g/dL", range_text="13.5-17.5 g/dL"),
        ]))

        data = parse(json_parser_args)

        assert set(data.observations) == {"DiagnosticReport-1.json[0]", "DiagnosticReport-1.json[1]"}
        assert set(data.observation_code_ids) == {"Glucose", "Hemoglobin"}

    def test_non_lab_diagnostic_report_is_ignored(self, json_parser_args, write_json, make_lab_observation):
        write_json(Path(json_parser_args.base_dir) / "DiagnosticReport-1.json",
                   diagnostic_report([make_lab_observation()], category_code="RAD"))
        assert parse(json_parser_args).observations == {}

    def test_custom_report_files_are_listed(self, json_parser_args, write_json, make_lab_observation):
        path = write_json(Path(json_parser_args.base_dir) / "DiagnosticReport-abc-CUSTOM.json",
                          diagnostic_report([make_lab_observation()]))
        custom_data_files = []
        parse(json_parser_args, custom_data_files)
        assert custom_data_files == [str(path)]

    def test_skip_dates(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2023-01-10"))
        write_json(base_dir / "Observation-2.json", make_lab_observation(date="2023-04-05"))
        json_parser_args.skip_dates = ["2023-01-10"]

        data = parse(json_parser_args)

        assert data.observation_dates == ["2023-04-05"]

    def test_start_year(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2019-01-10"))
        write_json(base_dir / "Observation-2.json", make_lab_observation(date="2023-04-05"))
        json_parser_args.start_year = 2020

        assert parse(json_parser_args).observation_dates == ["2023-04-05"]

    def test_vital_sign_observations_are_kept_separately(self, json_parser_args, write_json,
                                                         make_lab_observation):
        write_json(Path(json_parser_args.base_dir) / "Observation-1.json",
                   make_lab_observation(display="Pulse", code="8867-4", value=62, unit="/min",
                                        range_text=None, category="Vital Signs"))

        data = parse(json_parser_args)

        assert data.observations == {}
        [obs] = data.observations_vital_signs["2023-04-05"]
        assert obs.vital_sign_category is VitalSignCategory.PULSE
        assert obs.value == 62.0

    @pytest.mark.xfail(raises=ValueError,
                       reason="Known bug: file names without '-' (e.g. .DS_Store) abort the parse")
    def test_unrelated_files_are_ignored(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation())
        (base_dir / ".DS_Store").write_bytes(b"")

        assert len(parse(json_parser_args).observations) == 1


class TestDetermineAbnormalResults:
    def test_range_is_applied_to_results_without_one(self, json_parser_args, write_json,
                                                    make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2023-04-05", value=90))
        write_json(base_dir / "Observation-2.json",
                   make_lab_observation(date="2023-01-10", value=150, range_text=None))
        data = parse(json_parser_args)
        assert GLUCOSE_ID not in data.abnormal_results

        data.determine_abnormal_results(False, False, 0.15)

        assert [obs.date for obs in data.abnormal_results[GLUCOSE_ID]] == ["2023-01-10"]
        assert data.ranges == {"Glucose": "70-99 mg/dL"}
        assert data.reference_dates == ["2023-01-10", "2023-04-05"]

    def test_range_with_mismatched_units_is_not_applied(self, json_parser_args, write_json,
                                                        make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2023-04-05", value=90))
        write_json(base_dir / "Observation-2.json",
                   make_lab_observation(date="2023-01-10", value=8.3, unit="mmol/L", range_text=None))
        data = parse(json_parser_args)

        data.determine_abnormal_results(False, False, 0.15)

        assert GLUCOSE_ID not in data.abnormal_results
