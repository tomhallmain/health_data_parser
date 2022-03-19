import re

from data.labtest import LabTest
from data.result import Result


class CategoryError(AssertionError):
    def __init__(self, message):
        super().__init__(message)


'''
When constructed directly used to handle observations not belonging to vital sign categories.
'''


class Observation:
    def __init__(self, data: dict, obs_id: str, tests: list, date_codes: dict,
                 start_year: int, skip_long_values: bool,
                 skip_in_range_abnormal_results: bool, abnormal_boundary: float,
                 vital_sign_categories: list, disallowed_codes: list):
        self.obs_id = obs_id
        self.observation_complete = False

        if "valueString" not in data and "valueQuantity" not in data:
            if "component" not in data:
                raise ValueError("Observation value not found")

        if "text" in data["category"]:
            self.category = data["category"]["text"]
        else:
            self.category = data["category"]["coding"][0]["code"]

        if self.category in vital_sign_categories:
            raise CategoryError("Observation for category "
                                + self.category + " to be handled separately")

        self.date = data["effectiveDateTime"][0:10]

        if start_year is not None:
            year = int(self.date[0:4])
            if year < start_year:
                raise AssertionError("Observation year is before start year")

        self.set_code_and_test(data, disallowed_codes, tests)

        self.datecode = self.date + self.primary_code_id

        if self.datecode in date_codes:
            raise AssertionError(
                "Datecode " + self.datecode + " for code " + self.code + " already recorded")

        self.unit = None
        self.value = None

        self.set_value_and_value_string(data)
        self.validate_value(skip_long_values)
        self.result = None
        self.has_reference = False

        if "referenceRange" in data:
            self.set_reference(skip_in_range_abnormal_results,
                               abnormal_boundary, data["referenceRange"], self.unit, False)

        self.comment = data["comments"] if "comments" in data else None
        self.observation_complete = True

    def set_code_and_test(self, data, disallowed_codes, tests):
        if "text" in data["code"]:
            self.code = data["code"]["text"]
        else:
            self.code = None

        self.primary_code_id = None
        self.test = LabTest(self.code, data["code"])
        self.code = self.test.test_desc

        if self.code.upper() in disallowed_codes:
            raise AssertionError("Skipping observation for code " + self.code)

        self.primary_code_id = self.test.primary_id
        self.test_index = -1
        i = 0

        for _test in tests:
            if self.test.matches(_test):
                self.test_index = i
                break
            i += 1

        if self.test_index < 0:
            self.is_seen_test = False
            self.test_index = len(tests)
        else:
            self.is_seen_test = True
            saved_test = tests[self.test_index]
            saved_test.add_coding(data["code"])
            self.test = saved_test
            self.code = self.test.test_desc
            self.primary_code_id = self.test.primary_id
            saved_test = None

    def set_value_and_value_string(self, data):
        if "valueString" in data:
            self.value_string = data["valueString"]
        elif "valueQuantity" in data:
            value_quantity = data["valueQuantity"]
            value = value_quantity["value"]
            numbervalue = None
            if value is not None:
                if isinstance(value, str):
                    value_matcher = re.search("(\d+\.\d+|\d+)", value)
                    if value_matcher:
                        numbervalue = value_matcher.group(1)
                else:
                    numbervalue = value
            if numbervalue is not None:
                self.value = float(numbervalue)
            self.value_string = str(value)
            if "unit" in value_quantity:
                self.unit = value_quantity["unit"]
                self.value_string += " " + self.unit
        # Blood pressure observations
        elif "component" in data:
            for component_value in data["component"]:
                if not ("code" in component_value
                        and "valueQuantity" in component_value
                        and "value" in component_value["valueQuantity"]
                        and "coding" in component_value["code"]
                        and len(component_value["code"]["coding"]) > 0
                        and "system" in component_value["code"]["coding"][0]
                        and component_value["code"]["coding"][0]["system"] == "http://loinc.org"
                        and "code" in component_value["code"]["coding"][0]):
                    continue
                # Systolic
                elif component_value["code"]["coding"][0]["code"] == "8480-6":
                    self.value = float(
                        component_value["valueQuantity"]["value"])
                # Diastolic
                elif component_value["code"]["coding"][0]["code"] == "8462-4":
                    self.value2 = float(
                        component_value["valueQuantity"]["value"])

                if "unit" in component_value["valueQuantity"]:
                    self.unit = component_value["valueQuantity"]["unit"]

            if self.value is None or self.value2 is None:
                raise ValueError(
                    "Systolic or Diastolic value not found for assumed blood pressure observation.")
            if self.unit is None:
                self.value_string = str(self.value) + \
                                        "/" + str(self.value2) + " mm[Hg]"
            else:
                self.value_string = str(self.value) + \
                                        "/" + str(self.value2) + \
                                                  " " + self.unit

    def validate_value(self, skip_long_values):
        if (self.value_string is None or self.value_string == ""
                or not re.search("[A-z0-9]", self.value_string)):
            raise ValueError(
                "Skipping observation with unparseable value for [date / code] "
                + self.date + " / " + self.code)
        elif "SEE BELOW" in self.value_string or "See Below" in self.value_string:
            self.value_string = self.value_string.replace("SEE BELOW\n\n", "").replace(
                "SEE BELOW\n", "").replace("SEE BELOW", "")
            if not re.search("[A-z0-9]", self.value_string):
                raise ValueError(
                    "Skipping observation with unparseable value for [date / code] "
                    + self.date + " / " + self.code)
        elif "See Below" in self.value_string:
            self.value_string = self.value_string.replace("See Below\n\n", "").replace(
                "See Below\n", "").replace("See Below", "")
            if not re.search("[A-z0-9]", self.value_string):
                raise ValueError(
                    "Skipping observation with unparseable value for [date / code] "
                    + self.date + " / " + self.code)
        elif skip_long_values and len(self.value_string) > 200:
            raise ValueError(
                "Skipping observation with excessively long value for [date / code] "
                + self.date + " / " + self.code)

    def set_reference(self, skip_in_range_abnormal_results: bool,
                      abnormal_boundary: float, ranges_list: list, unit: str,
                      check_units_match: bool):
        try:
            self.result = Result(skip_in_range_abnormal_results,
                                 abnormal_boundary, ranges_list, self.value,
                                 self.value_string, unit, check_units_match)
            self.has_reference = True
        except ValueError:
            pass

    def to_dict(self, _id: str, tests: list):
        out = {}
        out["observationId"] = _id
        out["date"] = self.date
        out["category"] = self.category
        if self.test_index in tests:
            out["testMeta"] = tests[self.test_index].to_dict()
        result = {}
        result["valueString"] = self.value_string
        if self.value is not None:
            result["value"] = self.value
        if self.has_reference:
            result["referenceRange"] = self.result.to_dict()
        if self.comment is not None:
            result["comment"] = self.comment
        out["observedResult"] = result
        return out


'''
Used to handle observations belonging to these (and potentially other) codes:
    - "Vital Signs"
    - "Height"
    - "Pulse"
    - "Respiration"
    - "SpO2"
    - "Temperature"
    - "Weight"
'''


class ObservationVital(Observation):
    def __init__(self, data: dict, obs_id: str, tests: list, date_codes: dict,
                 start_year: int, skip_long_values: bool,
                 skip_in_range_abnormal_results: bool, abnormal_boundary: float):
        super().__init__(data, obs_id, tests, date_codes, start_year, skip_long_values,
                         skip_in_range_abnormal_results, abnormal_boundary, [], [])
        self.vital_sign_category = None
