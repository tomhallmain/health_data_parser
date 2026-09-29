from dataclasses import dataclass, field
from datetime import datetime
import os
from typing import ClassVar

from health_data_parser.errors import HealthDataParseError
from health_data_parser.model.units import HeightUnit, WeightUnit, TemperatureUnit, get_age


@dataclass(frozen=True)
class OutputPaths:
    """Where a run writes its files. Charts and the PDF also go in `directory`."""
    directory: str

    @property
    def all_data_csv(self):
        return os.path.join(self.directory, "observations.csv")

    @property
    def all_data_json(self):
        return os.path.join(self.directory, "observations.json")

    @property
    def abnormal_results_csv(self):
        return os.path.join(self.directory, "abnormal_results.csv")

    @property
    def abnormal_results_by_interpretation_csv(self):
        return os.path.join(self.directory, "abnormal_results_by_interpretation.csv")

    @property
    def abnormal_results_by_code_text(self):
        return os.path.join(self.directory, "abnormal_results_by_code.txt")


@dataclass(frozen=True)
class ParseOptions:
    """Every option for a run, with each default defined here only.

    Construction validates the options and raises HealthDataParseError, so the
    CLI and the GUI apply the same checks. Use dataclasses.replace() to derive
    a changed copy.
    """
    data_export_dir: str
    # Defaults to data_export_dir
    output_dir: str | None = None
    verbose: bool = False
    start_year: int | None = None
    skip_dates: tuple[str, ...] = ()
    skip_long_values: bool = False
    skip_in_range_abnormal_results: bool = False
    in_range_abnormal_boundary: float = 0.15
    report_highlight_abnormal_results: bool = True
    only_clinical_records: bool = False
    custom_only: bool = False
    json_add_all_vitals: bool = False
    extra_observations_csv: str | None = None
    food_data_csv: str | None = None
    symptom_data_csv: str | None = None
    birth_date: str | None = None
    normal_height_unit: HeightUnit = HeightUnit.CM
    normal_weight_unit: WeightUnit = WeightUnit.LB
    normal_temperature_unit: TemperatureUnit = TemperatureUnit.C
    # Filled in during a run: parsers add the subject's name, birth date, sex, ...
    subject: dict = field(default_factory=dict, compare=False, repr=False)

    # Timestamp format of Apple Health export.xml records
    datetime_format: ClassVar[str] = "%Y-%m-%d %X %z"

    def __post_init__(self):
        self._validate_export_dir()
        if self.output_dir is not None and os.path.isfile(self.output_dir):
            raise HealthDataParseError(f"Output directory \"{self.output_dir}\" is a file.")
        if self.start_year is not None and not isinstance(self.start_year, int):
            raise HealthDataParseError(f"\"{self.start_year}\" is not a valid year.")
        if not abs(self.in_range_abnormal_boundary) < 0.5:
            raise HealthDataParseError(
                f"\"{self.in_range_abnormal_boundary}\" is not a valid decimal-formatted percentage: "
                "its absolute value must be less than 0.5.")
        for date in self.skip_dates:
            _parse_iso_date(date, f"\"{','.join(self.skip_dates)}\" is not a valid list of dates "
                                  "in format YYYY-MM-DD.")
        if self.birth_date is not None:
            birth_date = _parse_iso_date(
                self.birth_date, f"\"{self.birth_date}\" is not a valid date in format YYYY-MM-DD.")
            self.subject["birthDate"] = self.birth_date
            self.subject["age"] = get_age(birth_date)

    def _validate_export_dir(self):
        if self.data_export_dir is None or self.data_export_dir == "":
            raise HealthDataParseError("Missing Apple Health data export directory path.")
        if not os.path.isdir(self.data_export_dir):
            raise HealthDataParseError(
                f"Apple Health data export directory path \"{self.data_export_dir}\" is invalid.")
        if not os.path.isdir(self.base_dir) or len(os.listdir(self.base_dir)) == 0:
            raise HealthDataParseError(
                f"Folder \"clinical-records\" not found in export folder \"{self.data_export_dir}\". "
                "Ensure data has been connected to Apple Health before export.")

    @property
    def base_dir(self):
        """The export's clinical-records folder."""
        return os.path.join(self.data_export_dir, "clinical-records")

    @property
    def export_xml(self):
        return os.path.join(self.data_export_dir, "export.xml")

    @property
    def output_paths(self):
        return OutputPaths(self.output_dir or self.data_export_dir)


def _parse_iso_date(value: str, message: str):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise HealthDataParseError(message) from None


# Conversions from option strings (CLI arguments, GUI text fields). Checks that
# don't depend on where a value came from live in ParseOptions itself.

def parse_start_year(value: str):
    try:
        return int(value)
    except ValueError:
        raise HealthDataParseError(f"\"{value}\" is not a valid year.") from None


def parse_skip_dates(value: str):
    return tuple(date.strip() for date in value.split(",") if date.strip())


def parse_boundary(value: str):
    try:
        return float(value)
    except ValueError:
        raise HealthDataParseError(f"\"{value}\" is not a valid decimal-formatted percentage.") from None


def parse_bool(value: str, option_name: str):
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise HealthDataParseError(f"{option_name} value \"{value}\" is not a boolean (true or false).")
