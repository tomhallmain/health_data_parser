import re


class Result:
    def __init__(self, skip_in_range_abnormal_results: bool,
                 abnormal_boundary: float, range_data: list, value,
                 value_string: str, unit: str, check_units_match: bool):
        self.range_text = range_data[0]["text"]
        self.range_pat = "(\d[\d,]*\\.\d+|\d[\d,]+) *(-|–) *(\d[\d,]*\.\d+|\d[\d,]*)"

        if (self.range_text is None
                or self.range_text == ""
                or not re.search("[A-z0-9]", self.range_text)):
            raise ValueError("Unparsable reference range")

        if "not estab" in self.range_text.lower():
            raise ValueError("Range not established")

        self.is_abnormal = False
        self.is_range_type = False
        self.is_binary_type = False
        self.unit = unit

        if (check_units_match
            and not (self.range_text.lower() == "none"
                     or self.range_text.lower() == "clear")
                and not (self.unit is not None and self.unit in self.range_text)):
            raise ValueError("Unmatched units for reference range")

        if value is not None and not isinstance(value, str):
            self.parse_range_result(
                value, value_string, abnormal_boundary, skip_in_range_abnormal_results)
        elif value is None and value_string is not None and isinstance(value_string, str):
            self.is_binary_type = True
            self.parse_binary_result(
                value, value_string, abnormal_boundary, skip_in_range_abnormal_results)

        if not self.is_abnormal:
            self.interpretation = ""

    def parse_range_result(self, value, value_string, abnormal_boundary,
                           skip_in_range_abnormal_results):
        # NOTE "high" and "low" objects less consistent than "text" field
        # so use "text" to set the range
        value_range_matcher = re.search(self.range_pat, self.range_text)

        if value_range_matcher:
            self.is_range_type = True
            value1 = value_range_matcher.group(1).replace(",", "")
            value2 = value_range_matcher.group(3).replace(",", "")
            self.range_lower = float(value1)
            self.range_upper = float(value2)

            if self.range_lower > self.range_upper:
                temp = self.range_upper
                self.range_upper = self.range_lower
                self.range_lower = temp
                temp = None

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
                self.range = str(self.range_lower) + " - " + \
                    str(self.range_upper)

                if low_out_of_range:
                    self.interpretation = "---"
                elif low_end_of_range:
                    self.interpretation = "--"
                elif high_end_of_range:
                    self.interpretation = "++"
                elif high_out_of_range:
                    self.interpretation = "+++"

        else:
            none_matcher = re.search(
                    "^none$", self.range_text, flags=re.IGNORECASE)

            if none_matcher:
                self.is_binary_type = True
                self.is_range_type = True
                self.range_upper = float(1) if (self.unit is not None
                                                and self.unit == "%") else float(0)
                self.range_lower = float(0)
                if value > self.range_upper:
                    self.is_abnormal = True
                    self.range = str(self.range_lower) + \
                        " - " + str(self.range_upper)
                    self.interpretation = "+"

    def parse_binary_result(self, value, value_string, abnormal_boundary,
                            skip_in_range_abnormal_results):
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
            self.interpretation = "+"

    def get_result_interpretation_text(self):
        return get_interpretation_text(self.interpretation)

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
            out["interpretation"] = self.get_result_interpretation_text()
        return out


def get_interpretation_text(interpretation_key: str):
    if interpretation_key == "---":
        return "LOW OUT OF RANGE"
    elif interpretation_key == "--":
        return "Low in range"
    elif interpretation_key == "+":
        return "Non-negative result"
    elif interpretation_key == "++":
        return "High in range"
    elif interpretation_key == "+++":
        return "HIGH OUT OF RANGE"
    else:
        return ""


def get_interpretation_keys(skip_in_range: bool):
    if skip_in_range:
        return ["---", "+", "+++"]
    else:
        return ["---", "--", "+", "++", "+++"]
