from labtest import LabTest
from result import Result

class Observation:
    def __init__(self, data, obs_id, tests, date_codes,
                 start_year, disallowed_categories, disallowed_codes):
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
            self.value = value_quantity["value"]
            self.value = None if self.value == None else float(self.value)
            self.value_string = str(value_quantity["value"])
            if "unit" in value_quantity:
                self.value_string = self.value_string + " " + value_quantity["unit"]

        self.result = None
        self.has_result = False

        if "referenceRange" in data:
            self.result = Result(data["referenceRange"], self.value, self.value_string)
            self.has_result = True
            if self.result.is_abnormal_result:
                self.value = self.value_string

        if "comments" in data:
            self.comment = data["comments"]

        self.observation_complete = True
