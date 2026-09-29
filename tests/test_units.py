from copy import deepcopy
from datetime import datetime

import pytest

import data.units as units
from data.units import (HeightUnit, WeightUnit, TemperatureUnit, VitalSignCategory,
                        base_stats, calculate_bmi, convert, get_age, set_stats)


class TestConvert:
    def test_centimeters_to_meters(self):
        assert convert(HeightUnit.M, HeightUnit.CM, 180) == pytest.approx(1.8)

    def test_inches_to_centimeters(self):
        assert convert(HeightUnit.CM, HeightUnit.IN, 12) == pytest.approx(30.48, rel=1e-4)

    def test_pounds_to_kilograms(self):
        assert convert(WeightUnit.KG, WeightUnit.LB, 2.204623) == pytest.approx(1.0)


class TestUnitFromValue:
    @pytest.mark.parametrize("value, expected", [
        ("cm", HeightUnit.CM), ("m", HeightUnit.M), ("ft", HeightUnit.FT), ("in", HeightUnit.IN),
        ("inches", HeightUnit.IN), ("feet", HeightUnit.FT), ("meters", HeightUnit.M),
        ("centimeters", HeightUnit.CM),
    ])
    def test_height(self, value, expected):
        assert HeightUnit.from_value(value) is expected

    @pytest.mark.parametrize("value, expected", [
        ("lb", WeightUnit.LB), ("kg", WeightUnit.KG), ("g", WeightUnit.G),
        ("pounds", WeightUnit.LB), ("kilos", WeightUnit.KG), ("kilograms", WeightUnit.KG),
        ("grams", WeightUnit.G),
    ])
    def test_weight(self, value, expected):
        assert WeightUnit.from_value(value) is expected

    @pytest.mark.parametrize("value, expected", [
        ("degF", TemperatureUnit.F), ("degC", TemperatureUnit.C),
        ("F", TemperatureUnit.F), ("C", TemperatureUnit.C),
        ("fahrenheit", TemperatureUnit.F),
    ])
    def test_temperature(self, value, expected):
        assert TemperatureUnit.from_value(value) is expected

    @pytest.mark.xfail(reason="Known bug: from_value only accepts the misspelling 'celcius', and "
                              "its strip of 'DEGREES'/'°'/spaces discards the result")
    @pytest.mark.parametrize("value, expected", [
        ("Celsius", TemperatureUnit.C), ("°F", TemperatureUnit.F), ("degrees C", TemperatureUnit.C),
    ])
    def test_temperature_common_spellings(self, value, expected):
        assert TemperatureUnit.from_value(value) is expected


class TestTemperatureConvert:
    def test_fahrenheit_to_celsius(self):
        assert TemperatureUnit.F.convertTo(TemperatureUnit.C, 212) == pytest.approx(100)

    def test_celsius_to_fahrenheit(self):
        assert TemperatureUnit.C.convertTo(TemperatureUnit.F, 37) == pytest.approx(98.6)

    def test_same_unit_is_unchanged(self):
        assert TemperatureUnit.C.convertTo(TemperatureUnit.C, 37) == 37


class TestVitalSignCategoryMatches:
    @pytest.mark.parametrize("text", ["Blood Pressure", "BLOOD_PRESSURE", "blood_pressure panel"])
    def test_matches_value_name_or_lowercase_name(self, text):
        assert VitalSignCategory.BLOOD_PRESSURE.matches(text)

    def test_does_not_match_unrelated_text(self):
        assert not VitalSignCategory.PULSE.matches("Heart rate")


class TestCalculateBmi:
    def test_metric(self):
        assert calculate_bmi(180, 81, HeightUnit.CM, WeightUnit.KG, False) == 25.0

    def test_converts_from_normal_units(self):
        # 70.866 in = 180 cm, 178.574 lb = 81 kg
        assert calculate_bmi(70.866, 178.574, HeightUnit.IN, WeightUnit.LB, False) == pytest.approx(25.0, abs=0.01)

    def test_zero_height_raises(self):
        with pytest.raises(Exception, match="division by zero"):
            calculate_bmi(0, 81, HeightUnit.CM, WeightUnit.KG, False)


class TestSetStats:
    def test_scalar_values(self):
        stats = deepcopy(base_stats)
        for value in [5, 10, 3]:
            set_stats(stats, None, value)
        assert stats["count"] == 3
        assert stats["sum"] == 18
        assert stats["max"] == 10
        assert stats["min"] == 3
        assert stats["list"] == [5, 10, 3]

    def test_timed_values_are_recorded_with_time(self):
        stats = deepcopy(base_stats)
        time = datetime(2023, 1, 1)
        set_stats(stats, time, 60)
        assert stats["list"] == [{"time": time, "value": 60}]

    def test_list_values_track_each_component(self):
        stats = {"count": 0, "sum": [0, 0], "max": [None, None], "min": [None, None], "list": []}
        for value in [[120, 80], [130, 75], [110, 85]]:
            set_stats(stats, None, value)
        assert stats["count"] == 3
        assert stats["sum"] == [360, 240]
        assert stats["max"] == [130, 85]
        assert stats["min"] == [110, 75]


class _FixedToday(datetime):
    @classmethod
    def today(cls):
        return cls(2026, 6, 15)


class TestGetAge:
    @pytest.fixture(autouse=True)
    def fixed_today(self, monkeypatch):
        monkeypatch.setattr(units, "datetime", _FixedToday)

    def test_on_birthday(self):
        assert get_age(datetime(2000, 6, 15)) == 26

    def test_before_birthday_this_year(self):
        # 183 days short of the 26th birthday
        assert get_age(datetime(2000, 12, 15)) == pytest.approx(25.5)

    @pytest.mark.xfail(raises=ValueError,
                       reason="Known bug: a Feb 29 birth date builds datetime(<non-leap year>, 2, 29)")
    def test_leap_day_birth_date(self):
        assert get_age(datetime(2000, 2, 29)) == pytest.approx(26.3)
