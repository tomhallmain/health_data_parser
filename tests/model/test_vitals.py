from datetime import datetime, timezone

import pytest

from health_data_parser.model.units import HeightUnit, TemperatureUnit, WeightUnit
from health_data_parser.model.vitals import (
    WEARABLE_HEART_RATE_READINGS, BloodPressureSeries, Reading, VitalSeries, VitalSigns)


def at(day, hour=8):
    return datetime(2023, 1, day, hour)


class TestVitalSeries:
    def test_stats(self):
        series = VitalSeries("Pulse", "/min")
        for day, value in [(1, 60), (2, 80), (3, 70)]:
            series.add(at(day), value)
        assert series.count == 3
        assert series.mean == 70
        assert series.min == 60
        assert series.max == 80
        assert series.stdev == pytest.approx((200 / 3) ** 0.5)
        assert series.most_recent == Reading(at(3), 70)

    def test_empty_series(self):
        series = VitalSeries("Pulse")
        assert series.count == 0
        assert (series.mean, series.min, series.max, series.stdev, series.most_recent) == (None,) * 5

    def test_sort(self):
        series = VitalSeries("Pulse")
        series.add(at(2), 80)
        series.add(at(1), 60)
        series.sort()
        assert series.values == [60, 80]
        assert series.most_recent.value == 80

    def test_sort_with_mixed_timezones_leaves_order_unchanged(self):
        series = VitalSeries("Pulse")
        series.add(at(2), 80)
        series.add(datetime(2023, 1, 1, tzinfo=timezone.utc), 60)
        with pytest.raises(TypeError):
            series.sort()
        assert series.values == [80, 60]

    def test_to_dict(self):
        series = VitalSeries("Pulse", "/min")
        series.add(at(1), 60, motion=0)
        series.add(at(2), 80, motion=2)
        assert series.to_dict() == {
            "vital": "Pulse", "unit": "/min", "count": 2, "avg": 70.0, "max": 80, "min": 60,
            "stDev": 10.0, "mostRecent": {"time": at(2), "value": 80, "motion": 2}}

    def test_to_dict_with_readings(self):
        series = VitalSeries("Weight", "lb")
        series.add(at(1), 150)
        assert series.to_dict(include_readings=True)["list"] == [{"time": at(1), "value": 150}]

    def test_empty_to_dict(self):
        assert VitalSeries("Respiration").to_dict() == {
            "vital": "Respiration", "unit": None, "count": 0, "avg": None, "max": None, "min": None,
            "stDev": None, "mostRecent": None}


class TestBloodPressureSeries:
    def test_to_dict_pairs_systolic_and_diastolic(self):
        bp = BloodPressureSeries()
        bp.add(at(1), 120, 80)
        bp.add(at(2), 130, 90)
        out = bp.to_dict(include_readings=True)
        assert out["vital"] == "Blood Pressure"
        assert out["unit"] == "mmHg"
        assert out["labels"] == ["BP Systolic", "BP Diastolic"]
        assert out["count"] == 2
        assert out["avg"] == [125.0, 85.0]
        assert out["max"] == [130, 90]
        assert out["min"] == [120, 80]
        assert out["stDev"] == [5.0, 5.0]
        assert out["mostRecent"] == {"time": at(2), "value": [130, 90]}
        assert out["list"] == [{"time": at(1), "value": [120, 80]}, {"time": at(2), "value": [130, 90]}]

    def test_sort_keeps_pairs_together(self):
        bp = BloodPressureSeries()
        bp.add(at(2), 130, 90)
        bp.add(at(1), 120, 80)
        bp.sort()
        assert bp.to_dict()["mostRecent"]["value"] == [130, 90]

    def test_empty(self):
        out = BloodPressureSeries().to_dict()
        assert out["count"] == 0
        assert out["avg"] == [None, None]
        assert out["mostRecent"] is None


class TestVitalSigns:
    @pytest.fixture
    def vitals(self):
        return VitalSigns(HeightUnit.CM, WeightUnit.LB, TemperatureUnit.C)

    def test_units_follow_normal_units(self, vitals):
        assert (vitals.height.unit, vitals.weight.unit, vitals.temperature.unit) == ("cm", "lb", "C")

    def test_reported_series_order(self, vitals):
        assert [s.name for s in vitals.reported_series] == [
            "Height", "Weight", "BMI", "Temperature", "Pulse", "Respiration", "Blood Pressure",
            "Heart rate variability", "Apple stand minutes"]

    def test_observation_count(self, vitals):
        vitals.xml_observation_count = 3
        vitals.clinical_observation_count = 2
        assert vitals.observation_count == 5

    def test_earliest_xml_date(self, vitals):
        assert vitals.earliest_xml_ordinal is None
        vitals.note_xml_date(at(5))
        vitals.note_xml_date(at(2))
        vitals.note_xml_date(at(9))
        assert vitals.earliest_xml_ordinal == at(2).toordinal()

    def test_wearable_detection(self, vitals):
        for i in range(WEARABLE_HEART_RATE_READINGS):
            vitals.pulse.add(at(1), 60)
        assert not vitals.wearable_heart_rate_detected
        vitals.pulse.add(at(1), 60)
        assert vitals.wearable_heart_rate_detected

    def test_sort_readings_reports_unsortable_series(self, vitals):
        vitals.pulse.add(at(2), 80)
        vitals.pulse.add(datetime(2023, 1, 1, tzinfo=timezone.utc), 60)
        vitals.weight.add(at(2), 150)
        vitals.weight.add(at(1), 149)
        assert vitals.sort_readings() == ["Pulse"]
        assert vitals.weight.values == [149, 150]
