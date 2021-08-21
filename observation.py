import re

from labtest import LabTest
from result import Result

class Observation:
    def __init__(self, data, obs_id, tests, date_codes, start_year, skip_long_values,
                 skip_in_range_abnormal_results, abnormal_boundary, disallowed_categories, disallowed_codes):
        self.obs_id = obs_id
        self.observation_complete = False

        if "valueString" not in data and "valueQuantity" not in data:
            raise ValueError("Observation value not found")

        if "text" in data["category"]:
            self.category = data["category"]["text"]
        else:
            self.category = data["category"]["coding"][0]["code"]

        if self.category in disallowed_categories:
            raise AssertionError("Skipping observation for category " + self.category)

        self.date = data["effectiveDateTime"][0:10]

        if start_year != None:
            year = int(date[0:4])
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

        if self.value_string == None or self.value_string == "" or not re.search("[A-z0-9]", self.value_string):
            raise ValueError("Skipping observation with unparseable value for [date / code] " + self.date + " / " + self.code)
        elif skip_long_values and len(self.value_string) > 200:
            raise ValueError("Skipping observation with excessively long value for [date / code] " + self.date + " / " + self.code)

        self.result = None
        self.has_reference = False

        if "referenceRange" in data:
            self.has_reference = True
            try:
                self.result = Result(skip_in_range_abnormal_results, abnormal_boundary, data["referenceRange"], self.value, self.value_string)
            except ValueError as e:
                self.result = None
                self.has_reference = False

        self.comment = data["comments"] if "comments" in data else None
        self.observation_complete = True

    def to_dict(self, _id, tests):
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



