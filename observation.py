import re

from labtest import LabTest
from result import Result

class CategoryError(AssertionError):
    def __init__(self, message):
        super().__init__(message)


'''
When constructed directly used to handle observations not belonging to vital sign categories.
'''

class Observation:
    def __init__(self, data: dict, obs_id: str, tests: list, date_codes: dict, start_year: int, skip_long_values: bool,
                 skip_in_range_abnormal_results: bool, abnormal_boundary: float, vital_sign_categories: list, disallowed_codes: list):
        self.obs_id = obs_id
        self.observation_complete = False

        if "valueString" not in data and "valueQuantity" not in data:
            raise ValueError("Observation value not found")

        if "text" in data["category"]:
            self.category = data["category"]["text"]
        else:
            self.category = data["category"]["coding"][0]["code"]

        if self.category in vital_sign_categories:
            raise CategoryError("Observation for category " + self.category + " to be handled separately")

        self.date = data["effectiveDateTime"][0:10]

        if start_year != None:
            year = int(self.date[0:4])
            if year < start_year:
                raise AssertionError("Observation year is before start year")

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

        self.datecode = self.date + self.primary_code_id

        if self.datecode in date_codes:
            raise AssertionError("Datecode " + self.datecode + " for code " + self.code + " already recorded")

        self.unit = None

        if "valueString" in data:
            self.value_string = data["valueString"]
            self.value = None
        elif "valueQuantity" in data:
            value_quantity = data["valueQuantity"]
            value = value_quantity["value"]
            numbervalue = None
            if value != None:
                if isinstance(value, str):
                    value_matcher = re.search("(\d+\.\d+|\d+)", value)
                    if value_matcher:
                        numbervalue = value_matcher.group(1)
                else:
                    numbervalue = value
            self.value = None if numbervalue == None else float(numbervalue)
            self.value_string = str(value)
            if "unit" in value_quantity:
                self.unit = value_quantity["unit"]
                self.value_string = self.value_string + " " + self.unit



        # Validations

        if self.value_string == None or self.value_string == "" or not re.search("[A-z0-9]", self.value_string):
            raise ValueError("Skipping observation with unparseable value for [date / code] " + self.date + " / " + self.code)
        elif "SEE BELOW" in self.value_string or "See Below" in self.value_string:
            self.value_string = self.value_string.replace("SEE BELOW\n\n", "").replace("SEE BELOW\n", "").replace("SEE BELOW", "")
            if not re.search("[A-z0-9]", self.value_string):
                raise ValueError("Skipping observation with unparseable value for [date / code] " + self.date + " / " + self.code)
        elif "See Below" in self.value_string:
            self.value_string = self.value_string.replace("See Below\n\n", "").replace("See Below\n", "").replace("See Below", "")
            if not re.search("[A-z0-9]", self.value_string):
                raise ValueError("Skipping observation with unparseable value for [date / code] " + self.date + " / " + self.code)
        elif skip_long_values and len(self.value_string) > 200:
            raise ValueError("Skipping observation with excessively long value for [date / code] " + self.date + " / " + self.code)


        
        self.result = None
        self.has_reference = False

        if "referenceRange" in data:
            self.set_reference(skip_in_range_abnormal_results, abnormal_boundary, data["referenceRange"], self.unit, False)

        self.comment = data["comments"] if "comments" in data else None
        self.observation_complete = True


    def set_reference(self, skip_in_range_abnormal_results: bool, abnormal_boundary: float, ranges_list: list, unit: str, check_units_match: bool):
        try:
            self.result = Result(skip_in_range_abnormal_results, abnormal_boundary, 
                ranges_list, self.value, self.value_string, unit, check_units_match)
            self.has_reference = True
        except ValueError:
            pass


    def to_dict(self, _id: str, tests: list):
        out = {}
        out["observationId"] = _id
        out["date"] = self.date
        out["category"] = self.category
        out["testMeta"] = tests[self.test_index].to_dict()
        result = {}
        result["valueString"] = self.value_string
        if self.value != None:
            result["value"] = self.value
        if self.has_reference:
            result["referenceRange"] = self.result.to_dict()
        if self.comment != None:
            result["comment"] = self.comment
        out["observedResult"] = result
        return out




'''
Used to handle observations belonging to these categories/codes:
    - "Vital Signs"
    - "Height"
    - "Pulse"
    - "Respiration"
    - "SpO2"
    - "Temperature"
    - "Weight"
'''

class ObservationVital(Observation):
    def __init__(self, data: dict, obs_id: str, tests: list, date_codes: dict, start_year: int, skip_long_values: bool,
                 skip_in_range_abnormal_results: bool, abnormal_boundary: float):
        super().__init__(data, obs_id, tests, date_codes, start_year, skip_long_values, 
            skip_in_range_abnormal_results, abnormal_boundary, [], [])
        self.vital_sign_category = None
