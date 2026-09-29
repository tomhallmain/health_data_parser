"""Failures during a run raise HealthDataParseError so the GUI can report them
and stay open; only the CLI entry points turn them into a process exit."""
import pytest

from health_data_parser.options import HealthDataParseArgs
from health_data_parser.pipeline import DataParser
from health_data_parser.errors import HealthDataParseError


class TestHealthDataParseArgs:
    def test_valid_export_dir(self, export_dir):
        args = HealthDataParseArgs(str(export_dir))
        assert args.base_dir == str(export_dir / "clinical-records")
        assert args.all_data_json == str(export_dir / "observations.json")

    def test_defaults(self, export_dir):
        args = HealthDataParseArgs(str(export_dir))
        assert args.start_year is None
        assert args.skip_long_values is False
        assert args.skip_in_range_abnormal_results is False
        assert args.in_range_abnormal_boundary == 0.15
        assert args.skip_dates == []

    @pytest.mark.parametrize("path", [None, ""])
    def test_missing_path(self, path):
        with pytest.raises(HealthDataParseError, match="Missing"):
            HealthDataParseArgs(path)

    def test_nonexistent_path(self, tmp_path):
        with pytest.raises(HealthDataParseError, match="is invalid"):
            HealthDataParseArgs(str(tmp_path / "missing"))

    def test_file_instead_of_directory(self, tmp_path):
        path = tmp_path / "export.zip"
        path.write_bytes(b"")
        with pytest.raises(HealthDataParseError, match="is invalid"):
            HealthDataParseArgs(str(path))

    def test_missing_clinical_records(self, tmp_path):
        with pytest.raises(HealthDataParseError, match="clinical-records"):
            HealthDataParseArgs(str(tmp_path))

    def test_empty_clinical_records(self, tmp_path):
        (tmp_path / "clinical-records").mkdir()
        with pytest.raises(HealthDataParseError, match="clinical-records"):
            HealthDataParseArgs(str(tmp_path))


class TestDataParserErrors:
    @pytest.fixture
    def args(self, export_dir):
        return HealthDataParseArgs(str(export_dir))

    def test_missing_extra_observations_csv(self, args, tmp_path):
        args.extra_observations_csv = str(tmp_path / "missing.csv")
        with pytest.raises(HealthDataParseError, match="is invalid"):
            DataParser(args).process_custom_data()

    def test_extra_observations_without_rows(self, args, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("Subject,Performer,Collection Date,Report Description,LOINC Code,"
                        "Code Description,Value,Range,Units\n", encoding="utf-8")
        args.extra_observations_csv = str(path)
        with pytest.raises(HealthDataParseError, match="extra observations"):
            DataParser(args).process_custom_data()

    def test_unreadable_food_data(self, args, tmp_path):
        args.food_data_csv = str(tmp_path / "missing.csv")
        with pytest.raises(HealthDataParseError, match="food data"):
            DataParser(args).process_custom_data()

    def test_report_without_observations(self, args):
        with pytest.raises(HealthDataParseError, match="No relevant laboratory records"):
            DataParser(args).report()
