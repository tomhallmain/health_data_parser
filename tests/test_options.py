"""ParseOptions validation, and failures during a run: both raise
HealthDataParseError so the GUI can report them and stay open; only the CLI
entry points turn them into a process exit."""
import dataclasses

import pytest

from health_data_parser.errors import HealthDataParseError
from health_data_parser.model.units import HeightUnit, TemperatureUnit, WeightUnit
from health_data_parser.options import (
    OutputPaths, ParseOptions, parse_bool, parse_boundary, parse_skip_dates, parse_start_year)
from health_data_parser.pipeline import DataParser


class TestParseOptions:
    def test_input_paths(self, export_dir):
        options = ParseOptions(str(export_dir))
        assert options.base_dir == str(export_dir / "clinical-records")
        assert options.export_xml == str(export_dir / "export.xml")

    def test_defaults(self, export_dir):
        options = ParseOptions(str(export_dir))
        assert options.output_dir is None
        assert options.start_year is None
        assert options.skip_dates == ()
        assert options.skip_long_values is False
        assert options.skip_in_range_abnormal_results is False
        assert options.in_range_abnormal_boundary == 0.15
        assert options.report_highlight_abnormal_results is True
        assert options.only_clinical_records is False
        assert options.custom_only is False
        assert options.json_add_all_vitals is False
        assert (options.normal_height_unit, options.normal_weight_unit, options.normal_temperature_unit) \
            == (HeightUnit.CM, WeightUnit.LB, TemperatureUnit.C)
        assert options.subject == {}

    def test_is_immutable(self, export_dir):
        options = ParseOptions(str(export_dir))
        with pytest.raises(dataclasses.FrozenInstanceError):
            options.start_year = 2020

    def test_replace_revalidates(self, export_dir):
        options = ParseOptions(str(export_dir))
        assert dataclasses.replace(options, start_year=2020).start_year == 2020
        with pytest.raises(HealthDataParseError):
            dataclasses.replace(options, in_range_abnormal_boundary=0.5)

    @pytest.mark.parametrize("path", [None, ""])
    def test_missing_path(self, path):
        with pytest.raises(HealthDataParseError, match="Missing"):
            ParseOptions(path)

    def test_nonexistent_path(self, tmp_path):
        with pytest.raises(HealthDataParseError, match="is invalid"):
            ParseOptions(str(tmp_path / "missing"))

    def test_file_instead_of_directory(self, tmp_path):
        path = tmp_path / "export.zip"
        path.write_bytes(b"")
        with pytest.raises(HealthDataParseError, match="is invalid"):
            ParseOptions(str(path))

    def test_missing_clinical_records(self, tmp_path):
        with pytest.raises(HealthDataParseError, match="clinical-records"):
            ParseOptions(str(tmp_path))

    def test_empty_clinical_records(self, tmp_path):
        (tmp_path / "clinical-records").mkdir()
        with pytest.raises(HealthDataParseError, match="clinical-records"):
            ParseOptions(str(tmp_path))

    @pytest.mark.parametrize("boundary", [0.5, -0.5, 1.0])
    def test_boundary_must_be_under_half(self, export_dir, boundary):
        with pytest.raises(HealthDataParseError, match="not a valid decimal-formatted percentage"):
            ParseOptions(str(export_dir), in_range_abnormal_boundary=boundary)

    def test_negative_boundary_is_allowed(self, export_dir):
        assert ParseOptions(str(export_dir), in_range_abnormal_boundary=-0.1).in_range_abnormal_boundary == -0.1

    def test_skip_dates_must_be_iso(self, export_dir):
        with pytest.raises(HealthDataParseError, match="not a valid list of dates"):
            ParseOptions(str(export_dir), skip_dates=("2023-01-01", "2023-13-45"))

    def test_start_year_must_be_an_integer(self, export_dir):
        with pytest.raises(HealthDataParseError, match="not a valid year"):
            ParseOptions(str(export_dir), start_year="2020")

    def test_birth_date_fills_subject(self, export_dir):
        options = ParseOptions(str(export_dir), birth_date="1990-05-01")
        assert options.subject["birthDate"] == "1990-05-01"
        assert "age" in options.subject

    def test_invalid_birth_date(self, export_dir):
        with pytest.raises(HealthDataParseError, match="not a valid date"):
            ParseOptions(str(export_dir), birth_date="yesterday")

    def test_output_dir_defaults_to_export_dir(self, export_dir):
        assert ParseOptions(str(export_dir)).output_paths == OutputPaths(str(export_dir))

    def test_output_dir(self, export_dir, tmp_path):
        options = ParseOptions(str(export_dir), output_dir=str(tmp_path / "reports"))
        assert options.output_paths.directory == str(tmp_path / "reports")

    def test_output_dir_must_not_be_a_file(self, export_dir, tmp_path):
        path = tmp_path / "reports"
        path.write_text("", encoding="utf-8")
        with pytest.raises(HealthDataParseError, match="is a file"):
            ParseOptions(str(export_dir), output_dir=str(path))


def test_output_paths(tmp_path):
    paths = OutputPaths(str(tmp_path))
    assert paths.all_data_csv == str(tmp_path / "observations.csv")
    assert paths.all_data_json == str(tmp_path / "observations.json")
    assert paths.abnormal_results_csv == str(tmp_path / "abnormal_results.csv")
    assert paths.abnormal_results_by_interpretation_csv == str(tmp_path / "abnormal_results_by_interpretation.csv")
    assert paths.abnormal_results_by_code_text == str(tmp_path / "abnormal_results_by_code.txt")


class TestStringConversions:
    def test_start_year(self):
        assert parse_start_year("2020") == 2020
        with pytest.raises(HealthDataParseError, match="not a valid year"):
            parse_start_year("abc")

    def test_skip_dates(self):
        assert parse_skip_dates("2023-01-01, 2023-02-01") == ("2023-01-01", "2023-02-01")
        assert parse_skip_dates("") == ()

    def test_boundary(self):
        assert parse_boundary("0.2") == 0.2
        with pytest.raises(HealthDataParseError, match="not a valid decimal-formatted percentage"):
            parse_boundary("lots")

    @pytest.mark.parametrize("value, expected", [("true", True), ("False", False), (" TRUE ", True)])
    def test_bool(self, value, expected):
        assert parse_bool(value, "--flag") is expected

    def test_invalid_bool(self):
        with pytest.raises(HealthDataParseError, match="not a boolean"):
            parse_bool("maybe", "--flag")


class TestDataParserErrors:
    def test_missing_extra_observations_csv(self, export_dir, tmp_path):
        options = ParseOptions(str(export_dir), extra_observations_csv=str(tmp_path / "missing.csv"))
        with pytest.raises(HealthDataParseError, match="is invalid"):
            DataParser(options).process_custom_data()

    def test_extra_observations_without_rows(self, export_dir, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("Subject,Performer,Collection Date,Report Description,LOINC Code,"
                        "Code Description,Value,Range,Units\n", encoding="utf-8")
        options = ParseOptions(str(export_dir), extra_observations_csv=str(path))
        with pytest.raises(HealthDataParseError, match="extra observations"):
            DataParser(options).process_custom_data()

    def test_unreadable_food_data(self, export_dir, tmp_path):
        options = ParseOptions(str(export_dir), food_data_csv=str(tmp_path / "missing.csv"))
        with pytest.raises(HealthDataParseError, match="food data"):
            DataParser(options).process_custom_data()

    def test_report_without_observations(self, export_dir):
        with pytest.raises(HealthDataParseError, match="No relevant laboratory records"):
            DataParser(ParseOptions(str(export_dir))).report()
