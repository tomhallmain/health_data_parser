import pytest

from health_data_parser.model.reference_range import Result, get_interpretation_keys, get_interpretation_text


def make_result(range_text, value, value_string=None, unit=None,
                skip_in_range=False, boundary=0.15, check_units_match=False):
    if value_string is None:
        value_string = str(value)
    return Result(skip_in_range, boundary, [{"text": range_text}], value,
                  value_string, unit, check_units_match)


class TestRangeResults:
    @pytest.mark.parametrize("value, interpretation", [
        (5, "---"),    # below range
        (11, "--"),    # within the lowest 15% of the range
        (19, "++"),    # within the highest 15% of the range
        (25, "+++"),   # above range
    ])
    def test_abnormal_interpretations(self, value, interpretation):
        result = make_result("10-20", value)
        assert result.is_abnormal
        assert result.is_range_type
        assert result.interpretation == interpretation

    def test_mid_range_value_is_normal(self):
        result = make_result("10-20", 15)
        assert not result.is_abnormal
        assert result.interpretation == ""
        assert (result.range_lower, result.range_upper) == (10.0, 20.0)

    def test_skip_in_range_abnormal_results(self):
        assert not make_result("10-20", 19, skip_in_range=True).is_abnormal
        assert make_result("10-20", 25, skip_in_range=True).is_abnormal

    def test_reversed_range_is_normalized(self):
        result = make_result("20-10", 15)
        assert (result.range_lower, result.range_upper) == (10.0, 20.0)

    def test_decimal_range_with_units(self):
        result = make_result("3.5-5.0 mmol/L", 5.5, unit="mmol/L")
        assert result.is_abnormal
        assert result.interpretation == "+++"

    def test_lower_bound_of_zero_is_not_low_in_range(self):
        assert not make_result("0.0-10.0", 0.5).is_abnormal

    @pytest.mark.parametrize("range_text, value", [("0-5", 7), ("4-10", 12), ("4 - 10 mg/dL", 12)])
    def test_single_digit_integer_lower_bound(self, range_text, value):
        result = make_result(range_text, value)
        assert result.is_range_type
        assert result.interpretation == "+++"

    def test_none_range_flags_positive_value(self):
        result = make_result("None", 2)
        assert result.is_abnormal
        assert result.is_binary_type
        assert result.interpretation == "+"

    def test_none_range_accepts_zero(self):
        assert not make_result("None", 0).is_abnormal


class TestBinaryResults:
    def test_positive_against_negative_range(self):
        result = make_result("NEG", None, value_string="POSITIVE")
        assert result.is_abnormal
        assert result.is_binary_type
        assert result.interpretation == "+"

    def test_negative_against_negative_range(self):
        assert not make_result("Negative", None, value_string="NEG").is_abnormal

    def test_trace_is_abnormal_only_with_boundary_above_ten_percent(self):
        assert make_result("NEG", None, value_string="Trace", boundary=0.15).is_abnormal
        assert not make_result("NEG", None, value_string="Trace", boundary=0.05).is_abnormal

    def test_skip_in_range_ignores_trace(self):
        assert not make_result("NEG", None, value_string="Trace", skip_in_range=True).is_abnormal

    def test_clear_range(self):
        assert make_result("Clear", None, value_string="Cloudy").is_abnormal
        assert not make_result("Clear", None, value_string="clear").is_abnormal


class TestInvalidRanges:
    @pytest.mark.parametrize("range_text", ["", "--"])
    def test_unparsable_range(self, range_text):
        with pytest.raises(ValueError, match="Unparsable"):
            make_result(range_text, 1)

    def test_range_not_established(self):
        with pytest.raises(ValueError, match="not established"):
            make_result("Not Estab.", 1)

    def test_units_must_match_when_checked(self):
        with pytest.raises(ValueError, match="Unmatched units"):
            make_result("10-20 mg/dL", 15, unit="mmol/L", check_units_match=True)

    def test_matching_units_pass_check(self):
        assert not make_result("10-20 mg/dL", 15, unit="mg/dL", check_units_match=True).is_abnormal


class TestToDict:
    def test_abnormal_range_result(self):
        assert make_result("10-20", 25, unit="mg").to_dict() == {
            "expectedValue": "10-20",
            "isAbnormal": True,
            "isRangeType": True,
            "unit": "mg",
            "range": {"rangeHigh": 20.0, "rangeLow": 10.0},
            "isBinaryType": False,
            "interpretation": "HIGH OUT OF RANGE",
        }

    def test_normal_result_has_no_interpretation(self):
        assert "interpretation" not in make_result("10-20", 15).to_dict()


class TestInterpretations:
    @pytest.mark.parametrize("key, text", [
        ("---", "LOW OUT OF RANGE"), ("--", "Low in range"), ("+", "Non-negative result"),
        ("++", "High in range"), ("+++", "HIGH OUT OF RANGE"), ("", ""),
    ])
    def test_interpretation_text(self, key, text):
        assert get_interpretation_text(key) == text

    def test_keys_exclude_in_range_when_skipped(self):
        assert get_interpretation_keys(True) == ["---", "+", "+++"]
        assert get_interpretation_keys(False) == ["---", "--", "+", "++", "+++"]
