import logging
from pathlib import Path

import pytest

from health_data_parser.ingest.fhir_json import ClinicalRecordsParser
from health_data_parser.model.units import VitalSignCategory

GLUCOSE_ID = "http://loinc.org2345-7"


def parse(args, custom_data_files=None):
    return ClinicalRecordsParser(args, [] if custom_data_files is None else custom_data_files).parse()


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
        assert data.dates == ["2023-04-05", "2023-01-10"]
        assert data.codes == ["Glucose"]
        assert data.code_ids("Glucose") == [GLUCOSE_ID]
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
        assert data.codes == ["Glucose", "Hemoglobin"]

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

        assert data.dates == ["2023-04-05"]

    def test_start_year(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2019-01-10"))
        write_json(base_dir / "Observation-2.json", make_lab_observation(date="2023-04-05"))
        json_parser_args.start_year = 2020

        assert parse(json_parser_args).dates == ["2023-04-05"]

    def test_vital_sign_observations_are_kept_separately(self, json_parser_args, write_json,
                                                         make_lab_observation):
        write_json(Path(json_parser_args.base_dir) / "Observation-1.json",
                   make_lab_observation(display="Pulse", code="8867-4", value=62, unit="/min",
                                        range_text=None, category="Vital Signs"))

        data = parse(json_parser_args)

        assert data.observations == {}
        [obs] = data.vitals_by_date["2023-04-05"]
        assert obs.vital_sign_category is VitalSignCategory.PULSE
        assert obs.value == 62.0

    def test_unrelated_files_are_ignored(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation())
        (base_dir / ".DS_Store").write_bytes(b"")
        (base_dir / "Patient-1.json").write_text("{}", encoding="utf-8")

        assert len(parse(json_parser_args).observations) == 1

    def test_vital_sign_named_by_category(self, json_parser_args, write_json, make_lab_observation):
        write_json(Path(json_parser_args.base_dir) / "Observation-1.json",
                   make_lab_observation(display="Body temperature", code="8310-5", value=98.6,
                                        unit="[degF]", range_text=None, category="Temperature"))

        [obs] = parse(json_parser_args).vitals
        assert obs.vital_sign_category is VitalSignCategory.TEMPERATURE

    def test_unidentified_vital_sign_is_skipped(self, json_parser_args, write_json, make_lab_observation):
        write_json(Path(json_parser_args.base_dir) / "Observation-1.json",
                   make_lab_observation(display="Heart rate", code="8867-4", value=62, unit="/min",
                                        range_text=None, category="Vital Signs"))

        assert parse(json_parser_args).vitals == []

    def test_vital_signs_on_skipped_dates(self, json_parser_args, write_json, make_lab_observation):
        write_json(Path(json_parser_args.base_dir) / "Observation-1.json",
                   make_lab_observation(display="Pulse", code="8867-4", value=62, unit="/min",
                                        range_text=None, category="Vital Signs"))
        json_parser_args.skip_dates = ["2023-04-05"]

        assert parse(json_parser_args).vitals == []

    @pytest.mark.parametrize("first_result, uses_index", [
        ({"date": "2019-01-01"}, True),                    # before start year: index used
        ({"date": "2023-01-10"}, False),                   # skipped date: index reused
        ({"category": "Vital Signs", "display": "Heart rate"}, False),  # unidentified vital
        ({"broken": True}, False),                         # malformed: index reused
    ])
    def test_contained_result_ids(self, json_parser_args, write_json, make_lab_observation,
                                  first_result, uses_index):
        json_parser_args.start_year = 2020
        json_parser_args.skip_dates = ["2023-01-10"]
        first = make_lab_observation(date=first_result.get("date", "2023-04-05"),
                                     display=first_result.get("display", "Ferritin"), code="2276-4",
                                     category=first_result.get("category", "Laboratory"))
        if first_result.get("broken"):
            del first["effectiveDateTime"]
        write_json(Path(json_parser_args.base_dir) / "DiagnosticReport-1.json", diagnostic_report([
            first, make_lab_observation(display="Hemoglobin", code="718-7", value=14, unit="g/dL",
                                        range_text="13.5-17.5 g/dL")]))

        expected_id = "DiagnosticReport-1.json[1]" if uses_index else "DiagnosticReport-1.json[0]"
        assert set(parse(json_parser_args).observations) == {expected_id}

    def test_malformed_observation_is_logged_without_verbose(self, json_parser_args, write_json,
                                                             make_lab_observation, caplog):
        broken = make_lab_observation()
        del broken["effectiveDateTime"]
        write_json(Path(json_parser_args.base_dir) / "Observation-1.json", broken)

        with caplog.at_level(logging.ERROR):
            assert parse(json_parser_args).observations == {}
        assert any("Error processing observation Observation-1.json" in r.getMessage()
                   for r in caplog.records)
