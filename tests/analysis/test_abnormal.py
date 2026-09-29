from pathlib import Path

from health_data_parser.analysis.abnormal import apply_shared_reference_ranges
from health_data_parser.ingest.fhir_json import ClinicalRecordsParser, ObservationRules

GLUCOSE_ID = "http://loinc.org2345-7"


def parse(args):
    return ClinicalRecordsParser(args, []).parse()


class TestApplySharedReferenceRanges:
    def test_range_is_applied_to_results_without_one(self, json_parser_args, write_json,
                                                    make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2023-04-05", value=90))
        write_json(base_dir / "Observation-2.json",
                   make_lab_observation(date="2023-01-10", value=150, range_text=None))
        data = parse(json_parser_args)
        assert GLUCOSE_ID not in data.abnormal_results

        apply_shared_reference_ranges(data, ObservationRules())

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

        apply_shared_reference_ranges(data, ObservationRules())

        assert GLUCOSE_ID not in data.abnormal_results

    def test_most_recent_range_is_used(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json",
                   make_lab_observation(date="2022-01-01", value=90, range_text="60-90 mg/dL"))
        write_json(base_dir / "Observation-2.json", make_lab_observation(date="2023-04-05", value=90))
        write_json(base_dir / "Observation-3.json",
                   make_lab_observation(date="2023-01-10", value=95, range_text=None))
        data = parse(json_parser_args)

        apply_shared_reference_ranges(data, ObservationRules())

        assert data.ranges == {"Glucose": "70-99 mg/dL"}
        assert data.find("2023-01-10", GLUCOSE_ID).reference.range_text == "70-99 mg/dL"

    def test_rules_apply_to_shared_ranges(self, json_parser_args, write_json, make_lab_observation):
        base_dir = Path(json_parser_args.base_dir)
        write_json(base_dir / "Observation-1.json", make_lab_observation(date="2023-04-05", value=90))
        # 97 is within 15% of the top of 70-99
        write_json(base_dir / "Observation-2.json",
                   make_lab_observation(date="2023-01-10", value=97, range_text=None))
        data = parse(json_parser_args)

        apply_shared_reference_ranges(data, ObservationRules(skip_in_range_abnormal_results=True))

        assert data.find("2023-01-10", GLUCOSE_ID).has_reference
        assert GLUCOSE_ID not in data.abnormal_results
