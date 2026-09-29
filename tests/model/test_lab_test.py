import pytest

from health_data_parser.model.lab_test import LabTest

LOINC = "http://loinc.org"


def loinc_code(code="2345-7", display="Glucose"):
    return {"coding": [{"system": LOINC, "code": code, "display": display}]}


class TestLabTest:
    def test_loinc_coding_sets_description_and_id(self):
        test = LabTest(None, loinc_code())
        assert test.test_desc == "Glucose"
        assert test.primary_id == LOINC + "2345-7"
        assert test.codings == {LOINC: "2345-7"}

    def test_explicit_description_takes_precedence(self):
        assert LabTest("Glucose, Serum", loinc_code()).test_desc == "Glucose, Serum"

    def test_non_loinc_coding_uses_first_coding(self):
        test = LabTest(None, {"coding": [{"system": "CUSTOM", "code": "ABC", "display": "Custom Test"}]})
        assert test.test_desc == "Custom Test"
        assert test.primary_id == "CUSTOMABC"

    def test_description_only(self):
        test = LabTest("Free text test", {"text": "Free text test"})
        assert test.test_desc == "Free text test"
        assert test.primary_id == "Free text test"

    def test_missing_description_raises(self):
        with pytest.raises(Exception, match="None"):
            LabTest(None, {"text": "ignored"})

    def test_matches_on_shared_system_and_code(self):
        other = LabTest("Glucose (other lab)", {"coding": [
            {"system": "urn:other", "code": "GLU"}, {"system": LOINC, "code": "2345-7"}]})
        assert LabTest(None, loinc_code()).matches(other)

    def test_does_not_match_different_code(self):
        assert not LabTest(None, loinc_code()).matches(LabTest(None, loinc_code("718-7", "Hemoglobin")))

    def test_add_coding_keeps_first_code_per_system(self):
        test = LabTest(None, loinc_code())
        test.add_coding({"coding": [{"system": "urn:other", "code": "GLU"}, {"system": LOINC, "code": "9999-9"}]})
        assert test.codings == {LOINC: "2345-7", "urn:other": "GLU"}

    def test_to_dict(self):
        assert LabTest(None, loinc_code()).to_dict() == {
            "testDescription": "Glucose", "codings": {LOINC: "2345-7"}}

    def test_get_code_ids(self):
        test = LabTest(None, loinc_code())
        test.add_coding({"coding": [{"system": "urn:other", "code": "GLU"}]})
        assert test.get_code_ids() == {"2345-7", "GLU"}
