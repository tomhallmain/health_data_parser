class LabTest:
    def __init__(self, code_desc, code_dict):
        self.codings = {}
        code_id = None

        if "coding" in code_dict:
            for coding in code_dict["coding"]:
                if "system" in coding and "code" in coding:
                    if not coding["system"] in self.codings:
                        self.codings[coding["system"]] = coding["code"]

                    if coding["system"] == "http://loinc.org":
                        if code_desc == None and "display" in coding:
                            code_desc = coding["display"]
                        code_id = coding["system"] + coding["code"]

            if code_id == None or code_id == "SOLOINC":
                coding = code_dict["coding"][0]
                if code_desc == None and "display" in coding:
                    code_desc = coding["display"]
                code_id = coding["system"] + coding["code"]
        
        else:
            code_id = code_desc

        if code_desc == None or code_id == None:
            raise Exception("Code description or ID is None")

        self.test_desc = code_desc
        self.primary_id = code_id

    # As data is traversed a test may be found to have more than one coding
    def add_coding(self, new_code_dict):
        if not "coding" in new_code_dict:
            return

        for coding in new_code_dict["coding"]:
            if not "system" in coding or not "code" in coding:
                continue

            if not coding["system"] in self.codings:
                self.codings[coding["system"]] = coding["code"]

    def matches(self, other_test):
        if self.codings == None or other_test.codings == None:
            return self.primary_id == other_test.primary_id

        for system in self.codings:
            for _system in other_test.codings:
                if system == _system and self.codings[system] == other_test.codings[_system]:
                    return True

        return False

    def get_code_ids(self):
        return set(self.coding.values())

    def to_dict(self):
        out = {}
        out["testDescription"] = self.test_desc
        out["codings"] = self.codings
        return out

