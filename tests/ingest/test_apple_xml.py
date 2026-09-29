from types import SimpleNamespace

import pytest

from health_data_parser.model.units import HeightUnit, TemperatureUnit, WeightUnit
from health_data_parser.ingest.apple_xml import AppleHealthXMLData, AppleHealthXMLParser
from health_data_parser.errors import HealthDataParseError

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


@pytest.fixture
def parse_xml(tmp_path):
    def _parse(*elements, start_year=None, me=ME):
        path = tmp_path / "export.xml"
        path.write_text("<HealthData>" + me + "".join(elements) + "</HealthData>", encoding="utf-8")
        args = SimpleNamespace(
            subject={}, verbose=False, start_year=start_year,
            normal_height_unit=HeightUnit.CM, normal_weight_unit=WeightUnit.LB,
            normal_temperature_unit=TemperatureUnit.C, datetime_format="%Y-%m-%d %X %z")
        data = AppleHealthXMLData(args.normal_height_unit, args.normal_weight_unit)
        AppleHealthXMLParser(data, args).parse(str(path))
        return data, args.subject
    return _parse


class TestAppleHealthXMLParser:
    def test_subject(self, parse_xml):
        _, subject = parse_xml()
        assert subject["birthDate"] == "1990-05-01"
        assert subject["sex"] == "Female"
        assert subject["bloodType"] == "APositive"
        assert "age" in subject

    def test_height_and_weight_are_converted_to_normal_units(self, parse_xml):
        data, _ = parse_xml(record("Height", 70, unit="in"), record("BodyMass", 80, unit="kg"))
        assert data.height_stats["list"][0]["value"] == pytest.approx(177.8)
        assert data.weight_stats["list"][0]["value"] == pytest.approx(176.37, abs=0.01)

    def test_records_without_units_are_skipped(self, parse_xml):
        data, _ = parse_xml(record("Height", 70))
        assert data.height_stats["count"] == 0

    def test_implausible_heart_rates_are_filtered(self, parse_xml):
        data, _ = parse_xml(
            record("HeartRate", 60),
            record("HeartRate", 145),                       # high but at rest: kept
            record("HeartRate", 150, children=MOTION),      # over 140 in motion: dropped
            record("HeartRate", 200),                       # over 155: dropped
            record("HeartRate", 30),                        # under 35: dropped
        )
        assert data.pulse_stats["count"] == 2
        assert [obs["value"] for obs in data.pulse_stats["list"]] == [60.0, 145.0]
        assert (data.pulse_stats["min"], data.pulse_stats["max"]) == (60.0, 145.0)
        assert data.pulse_stats["sum"] == 205.0

    def test_heart_rate_motion_context(self, parse_xml):
        data, _ = parse_xml(record("HeartRate", 120, children=MOTION))
        assert data.pulse_stats["list"][0]["motion"] == 2
        assert data.motion_data_found

    def test_body_temperature_is_converted(self, parse_xml):
        data, _ = parse_xml(record("BodyTemperature", 98.6, unit="degF"))
        assert data.temperature_stats["list"][0]["value"] == pytest.approx(37.0)

    def test_blood_pressure_correlations(self, parse_xml):
        data, _ = parse_xml(blood_pressure(120, 80), blood_pressure(130, 85))
        stats = data.blood_pressure_stats
        assert stats["count"] == 2
        assert [obs["value"] for obs in stats["list"]] == [[120, 80], [130, 85]]
        assert stats["max"] == [130, 85]
        assert stats["min"] == [120, 80]
        assert stats["sum"] == [250, 165]

    def test_other_record_types(self, parse_xml):
        data, _ = parse_xml(record("StepCount", 100), record("HeartRateVariabilitySDNN", 45),
                            record("OxygenSaturation", 0.98), record("AppleStandTime", 3))
        assert data.step_stats["count"] == 1
        assert data.hrv_stats["count"] == 1
        assert data.spo2_stats["count"] == 1
        assert data.stand_stats["count"] == 1

    def test_observations_count(self, parse_xml):
        data, _ = parse_xml(blood_pressure(120, 80), record("HeartRate", 60),
                            record("BodyTemperature", 37, unit="degC"), record("StepCount", 100))
        # Blood pressure, heart rate, HRV and temperature count; steps do not
        assert data.xml_vitals_observations_count == 3

    def test_start_year(self, parse_xml):
        data, _ = parse_xml(record("HeartRate", 60, date="2019-06-01 08:00:00 -0500"),
                            record("HeartRate", 70), start_year=2020)
        assert [obs["value"] for obs in data.pulse_stats["list"]] == [70.0]

    @pytest.mark.xfail(reason="Known bug: a record whose startDate fails to parse reuses the "
                              "previous record's time")
    def test_unparseable_date_after_valid_record_is_skipped(self, parse_xml):
        data, _ = parse_xml(record("HeartRate", 60), record("HeartRate", 70, date="not a date"))
        assert [obs["value"] for obs in data.pulse_stats["list"]] == [60.0]

    @pytest.mark.xfail(raises=HealthDataParseError,
                       reason="Known bug: an unparseable startDate on the first record leaves "
                              "`time` unbound, which aborts the whole parse")
    def test_unparseable_date_on_first_record_is_skipped(self, parse_xml):
        data, _ = parse_xml(record("HeartRate", 60, date="not a date"), record("HeartRate", 70))
        assert [obs["value"] for obs in data.pulse_stats["list"]] == [70.0]

    def test_earliest_record_date_is_tracked(self, parse_xml):
        parse_xml(record("HeartRate", 60, date="2021-03-04 08:00:00 -0500"), record("HeartRate", 70))
        assert AppleHealthXMLParser.min_xml_ordinal == 737853  # 2021-03-04

    def test_malformed_xml_raises(self, tmp_path):
        path = tmp_path / "export.xml"
        path.write_text("<HealthData>", encoding="utf-8")
        args = SimpleNamespace(subject={}, verbose=False, start_year=None,
                               normal_height_unit=HeightUnit.CM, normal_weight_unit=WeightUnit.LB,
                               normal_temperature_unit=TemperatureUnit.C,
                               datetime_format="%Y-%m-%d %X %z")
        with pytest.raises(HealthDataParseError, match="parsing XML"):
            AppleHealthXMLParser(AppleHealthXMLData(HeightUnit.CM, WeightUnit.LB), args).parse(str(path))

    def test_missing_me_element_raises(self, parse_xml):
        with pytest.raises(HealthDataParseError):
            parse_xml(record("HeartRate", 60), me="")
