from datetime import date
from types import SimpleNamespace

import pytest

from health_data_parser.errors import HealthDataParseError
from health_data_parser.ingest.apple_xml import AppleHealthXMLParser
from health_data_parser.model.units import HeightUnit, TemperatureUnit, WeightUnit
from health_data_parser.model.vitals import VitalSigns

ME = ('<Me HKCharacteristicTypeIdentifierDateOfBirth="1990-05-01" '
      'HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexFemale" '
      'HKCharacteristicTypeIdentifierBloodType="HKBloodTypeAPositive"/>')


def record(record_type, value, date="2023-01-01 08:00:00 -0500", unit=None, children=""):
    unit_attr = f' unit="{unit}"' if unit else ""
    return (f'<Record type="HKQuantityTypeIdentifier{record_type}"{unit_attr} value="{value}" '
            f'startDate="{date}">{children}</Record>')


def blood_pressure(systolic, diastolic, date="2023-01-01 08:00:00 -0500"):
    return (f'<Correlation type="HKCorrelationTypeIdentifierBloodPressure" startDate="{date}">'
            + record("BloodPressureSystolic", systolic, date, "mmHg")
            + record("BloodPressureDiastolic", diastolic, date, "mmHg")
            + '</Correlation>')


MOTION = '<MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="2"/>'


def xml_options(start_year=None):
    """The subset of ParseOptions that AppleHealthXMLParser reads."""
    return SimpleNamespace(
        subject={}, verbose=False, start_year=start_year,
        normal_height_unit=HeightUnit.CM, normal_weight_unit=WeightUnit.LB,
        normal_temperature_unit=TemperatureUnit.C, datetime_format="%Y-%m-%d %X %z")


def new_vital_signs():
    return VitalSigns(HeightUnit.CM, WeightUnit.LB, TemperatureUnit.C)


@pytest.fixture
def parse_xml(tmp_path):
    def _parse(*elements, start_year=None, me=ME):
        path = tmp_path / "export.xml"
        path.write_text("<HealthData>" + me + "".join(elements) + "</HealthData>", encoding="utf-8")
        options = xml_options(start_year)
        vitals = new_vital_signs()
        AppleHealthXMLParser(vitals, options).parse(str(path))
        return vitals, options.subject
    return _parse


class TestAppleHealthXMLParser:
    def test_subject(self, parse_xml):
        _, subject = parse_xml()
        assert subject["birthDate"] == "1990-05-01"
        assert subject["sex"] == "Female"
        assert subject["bloodType"] == "APositive"
        assert "age" in subject

    def test_given_birth_date_is_kept(self, tmp_path):
        path = tmp_path / "export.xml"
        path.write_text("<HealthData>" + ME + "</HealthData>", encoding="utf-8")
        options = xml_options()
        options.subject["birthDate"] = "1985-01-01"
        AppleHealthXMLParser(new_vital_signs(), options).parse(str(path))
        assert options.subject["birthDate"] == "1985-01-01"

    def test_height_and_weight_are_converted_to_normal_units(self, parse_xml):
        vitals, _ = parse_xml(record("Height", 70, unit="in"), record("BodyMass", 80, unit="kg"))
        assert vitals.height.values == [pytest.approx(177.8)]
        assert vitals.weight.values == [pytest.approx(176.37, abs=0.01)]

    def test_records_without_units_are_skipped(self, parse_xml):
        vitals, _ = parse_xml(record("Height", 70))
        assert vitals.height.count == 0

    def test_records_with_unknown_units_are_skipped(self, parse_xml):
        vitals, _ = parse_xml(record("Height", 70, unit="furlongs"))
        assert vitals.height.count == 0

    def test_implausible_heart_rates_are_filtered(self, parse_xml):
        vitals, _ = parse_xml(
            record("HeartRate", 60),
            record("HeartRate", 145),                       # high but at rest: kept
            record("HeartRate", 150, children=MOTION),      # over 140 in motion: dropped
            record("HeartRate", 200),                       # over 155: dropped
            record("HeartRate", 30),                        # under 35: dropped
        )
        assert vitals.pulse.values == [60.0, 145.0]
        assert (vitals.pulse.min, vitals.pulse.max, vitals.pulse.mean) == (60.0, 145.0, 102.5)
        assert [reading.motion for reading in vitals.pulse.readings] == [0, 0]

    def test_heart_rate_motion_context(self, parse_xml):
        vitals, _ = parse_xml(record("HeartRate", 120, children=MOTION))
        assert vitals.pulse.readings[0].motion == 2
        assert vitals.motion_data_found

    @pytest.mark.parametrize("value, unit", [(98.6, "degF"), (37, "degC"), (98.6, None), (37, None)])
    def test_body_temperature_is_converted(self, parse_xml, value, unit):
        # Without a unit, values over 45 are taken as Fahrenheit
        vitals, _ = parse_xml(record("BodyTemperature", value, unit=unit))
        assert vitals.temperature.values == [pytest.approx(37.0)]

    def test_blood_pressure_correlations(self, parse_xml):
        vitals, _ = parse_xml(blood_pressure(120, 80), blood_pressure(130, 85))
        bp = vitals.blood_pressure
        assert bp.count == 2
        assert bp.systolic.values == [120, 130]
        assert bp.diastolic.values == [80, 85]
        assert (bp.systolic.max, bp.systolic.min, bp.systolic.mean) == (130, 120, 125)
        assert (bp.diastolic.max, bp.diastolic.min, bp.diastolic.mean) == (85, 80, 82.5)

    def test_blood_pressure_missing_a_component_is_skipped(self, parse_xml):
        correlation = ('<Correlation type="HKCorrelationTypeIdentifierBloodPressure" '
                       'startDate="2023-01-01 08:00:00 -0500">'
                       + record("BloodPressureSystolic", 120, unit="mmHg") + '</Correlation>')
        vitals, _ = parse_xml(correlation)
        assert vitals.blood_pressure.count == 0

    def test_other_record_types(self, parse_xml):
        vitals, _ = parse_xml(record("StepCount", 100), record("HeartRateVariabilitySDNN", 45),
                              record("HeartRateVariabilitySDNN", 170),   # over 160: dropped
                              record("OxygenSaturation", 0.98), record("AppleStandTime", 3))
        assert vitals.steps.count == 1
        assert vitals.hrv.count == 1
        assert vitals.spo2.count == 1
        assert vitals.stand.count == 1

    def test_observations_count(self, parse_xml):
        vitals, _ = parse_xml(blood_pressure(120, 80), record("HeartRate", 60),
                              record("BodyTemperature", 37, unit="degC"), record("StepCount", 100))
        # Blood pressure, heart rate, HRV and temperature count; steps do not
        assert vitals.xml_observation_count == 3

    def test_start_year(self, parse_xml):
        vitals, _ = parse_xml(record("HeartRate", 60, date="2019-06-01 08:00:00 -0500"),
                              record("HeartRate", 70), start_year=2020)
        assert vitals.pulse.values == [70.0]

    def test_earliest_record_date_is_tracked(self, parse_xml):
        vitals, _ = parse_xml(record("HeartRate", 60, date="2021-03-04 08:00:00 -0500"),
                              record("HeartRate", 70))
        assert vitals.earliest_xml_ordinal == date(2021, 3, 4).toordinal()

    def test_earliest_date_is_per_parse(self, parse_xml):
        parse_xml(record("HeartRate", 60, date="2019-03-04 08:00:00 -0500"))
        vitals, _ = parse_xml(record("HeartRate", 70))
        assert vitals.earliest_xml_ordinal == date(2023, 1, 1).toordinal()

    def test_unparseable_date_after_valid_record_is_skipped(self, parse_xml):
        vitals, _ = parse_xml(record("HeartRate", 60), record("HeartRate", 70, date="not a date"))
        assert vitals.pulse.values == [60.0]

    def test_unparseable_date_on_first_record_is_skipped(self, parse_xml):
        vitals, _ = parse_xml(record("HeartRate", 60, date="not a date"), record("HeartRate", 70))
        assert vitals.pulse.values == [70.0]

    def test_malformed_xml_raises(self, tmp_path):
        path = tmp_path / "export.xml"
        path.write_text("<HealthData>", encoding="utf-8")
        with pytest.raises(HealthDataParseError, match="parsing XML"):
            AppleHealthXMLParser(new_vital_signs(), xml_options()).parse(str(path))

    def test_missing_me_element_raises(self, parse_xml):
        with pytest.raises(HealthDataParseError):
            parse_xml(record("HeartRate", 60), me="")
