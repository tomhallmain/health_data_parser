from enum import Enum
import re


class Interpretation(Enum):
    """How an abnormal result relates to its reference range, in severity order."""
    LOW_OUT_OF_RANGE = "---"
    LOW_IN_RANGE = "--"
    NON_NEGATIVE = "+"
    HIGH_IN_RANGE = "++"
    HIGH_OUT_OF_RANGE = "+++"

    @property
    def text(self):
        return _INTERPRETATION_TEXT[self]

    @property
    def is_in_range(self):
        return self in (Interpretation.LOW_IN_RANGE, Interpretation.HIGH_IN_RANGE)

    @classmethod
    def ordered(cls, include_in_range=True):
        return [i for i in cls if include_in_range or not i.is_in_range]


_INTERPRETATION_TEXT = {
    Interpretation.LOW_OUT_OF_RANGE: "LOW OUT OF RANGE",
    Interpretation.LOW_IN_RANGE: "Low in range",
    Interpretation.NON_NEGATIVE: "Non-negative result",
    Interpretation.HIGH_IN_RANGE: "High in range",
    Interpretation.HIGH_OUT_OF_RANGE: "HIGH OUT OF RANGE",
}


class InvalidReferenceRange(ValueError):
    """The range text can't be used to classify a result."""


# "lower - upper", with optional thousands separators and decimals
_RANGE_PATTERN = re.compile(r"(\d[\d,]*\.\d+|\d[\d,]*) *(-|–) *(\d[\d,]*\.\d+|\d[\d,]*)")


class ReferenceRange:
    """A result's reference range and whether the result falls outside it.

    Range results within `abnormal_boundary` (a fraction of the range's span)
    of either end count as abnormal "in range", unless
    `skip_in_range_abnormal_results` is set. A negative boundary widens the
    range instead: only results beyond it count as abnormal.
    """

    def __init__(self, range_text: str, value, value_string: str, unit: str | None, *,
                 skip_in_range_abnormal_results: bool = False, abnormal_boundary: float = 0.15,
                 check_units_match: bool = False):
        self.range_text = range_text

        if (self.range_text is None
                or self.range_text == ""
                or not re.search("[A-z0-9]", self.range_text)):
            raise InvalidReferenceRange("Unparsable reference range")

        if "not estab" in self.range_text.lower():
            raise InvalidReferenceRange("Range not established")

        self.is_abnormal = False
        self.is_range_type = False
        self.is_binary_type = False
        self.unit = unit
        self.interpretation: Interpretation | None = None

        if (check_units_match
            and not (self.range_text.lower() == "none"
                     or self.range_text.lower() == "clear")
                and not (self.unit is not None and self.unit in self.range_text)):
            raise InvalidReferenceRange("Unmatched units for reference range")

        if value is not None and not isinstance(value, str):
            self._parse_range_result(value, abnormal_boundary, skip_in_range_abnormal_results)
        elif value is None and value_string is not None and isinstance(value_string, str):
            self.is_binary_type = True
            self._parse_binary_result(value_string, abnormal_boundary, skip_in_range_abnormal_results)

    @property
    def tag(self):
        """The interpretation's short form ("+++" etc.), or "" for a normal result."""
        return self.interpretation.value if self.interpretation else ""

    def _parse_range_result(self, value, abnormal_boundary, skip_in_range_abnormal_results):
        # NOTE "high" and "low" objects less consistent than "text" field
        # so use "text" to set the range
        value_range_matcher = _RANGE_PATTERN.search(self.range_text)

        if value_range_matcher:
            self.is_range_type = True
            self.range_lower = float(value_range_matcher.group(1).replace(",", ""))
            self.range_upper = float(value_range_matcher.group(3).replace(",", ""))

            if self.range_lower > self.range_upper:
                self.range_lower, self.range_upper = self.range_upper, self.range_lower

            low_out_of_range = value < self.range_lower
            high_out_of_range = value > self.range_upper
            self.range_span = self.range_upper - self.range_lower
            low_end_of_range = high_end_of_range = False

            if self.range_span > 0.5:
                # If negative abnormal boundary, considering values higher
                # out of range than simply immediately outside range boundary
                if abnormal_boundary < 0:
                    skip_in_range_abnormal_results = False
                    low_out_of_range = False
                    high_out_of_range = False
                if not skip_in_range_abnormal_results:
                    low_end_of_range = (not self.range_lower == 0
                                        and not low_out_of_range
                                        and (value - self.range_lower) / self.range_span < abnormal_boundary)
                    high_end_of_range = (not high_out_of_range
                                         and (self.range_upper - value) / self.range_span < abnormal_boundary)

            if (low_out_of_range or high_out_of_range
                    or low_end_of_range or high_end_of_range):
                self.is_abnormal = True
                self.range = str(self.range_lower) + " - " + str(self.range_upper)

                if low_out_of_range:
                    self.interpretation = Interpretation.LOW_OUT_OF_RANGE
                elif low_end_of_range:
                    self.interpretation = Interpretation.LOW_IN_RANGE
                elif high_end_of_range:
                    self.interpretation = Interpretation.HIGH_IN_RANGE
                elif high_out_of_range:
                    self.interpretation = Interpretation.HIGH_OUT_OF_RANGE

        elif re.search("^none$", self.range_text, flags=re.IGNORECASE):
            self.is_binary_type = True
            self.is_range_type = True
            self.range_upper = float(1) if (self.unit is not None
                                            and self.unit == "%") else float(0)
            self.range_lower = float(0)
            if value > self.range_upper:
                self.is_abnormal = True
                self.range = str(self.range_lower) + " - " + str(self.range_upper)
                self.interpretation = Interpretation.NON_NEGATIVE

    def _parse_binary_result(self, value_string, abnormal_boundary, skip_in_range_abnormal_results):
        if self.range_text == "NEG" or re.match(
                "^negative$", self.range_text, flags=re.IGNORECASE):
            if not value_string == "NEG" and not re.match(
                    "^negative$", value_string, flags=re.IGNORECASE):
                if abnormal_boundary <= 0.1:
                    if not re.match("^trace$", value_string, flags=re.IGNORECASE):
                        self.is_abnormal = True
                else:
                    self.is_abnormal = True
        elif (re.match("^clear$", self.range_text, flags=re.IGNORECASE)
                and not re.match("^clear$", value_string, flags=re.IGNORECASE)):
            if abnormal_boundary <= 0.1:
                if not re.match("^trace$", value_string, flags=re.IGNORECASE):
                    self.is_abnormal = True
            else:
                self.is_abnormal = True
        elif re.match("^positive$", value_string, flags=re.IGNORECASE):
            self.is_abnormal = True

        if skip_in_range_abnormal_results and re.match(
                "^(trace|small)$", value_string, flags=re.IGNORECASE):
            self.is_abnormal = False

        if self.is_abnormal:
            self.interpretation = Interpretation.NON_NEGATIVE

    def to_dict(self):
        out = {}
        out["expectedValue"] = self.range_text
        out["isAbnormal"] = self.is_abnormal
        out["isRangeType"] = self.is_range_type
        out["unit"] = self.unit
        if self.is_range_type:
            _range = {}
            _range["rangeHigh"] = self.range_upper
            _range["rangeLow"] = self.range_lower
            out["range"] = _range
        out["isBinaryType"] = self.is_binary_type
        if self.is_abnormal:
            out["interpretation"] = self.interpretation.text
        return out


def reference_range_or_none(range_text, value, value_string, unit, **kwargs):
    """A ReferenceRange, or None when the range text can't classify the result."""
    try:
        return ReferenceRange(range_text, value, value_string, unit, **kwargs)
    except InvalidReferenceRange:
        return None
