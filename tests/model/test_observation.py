from health_data_parser.model.lab_test import LabTest
from health_data_parser.model.observation import Observation
from health_data_parser.model.reference_range import ReferenceRange

GLUCOSE = LabTest(None, {"coding": [{"system": "http://loinc.org", "code": "2345-7", "display": "Glucose"}]})


def glucose(value=105.0, range_text="70-99 mg/dL", **kwargs):
    reference = (ReferenceRange(range_text, value, f"{value} mg/dL", "mg/dL")
                 if range_text is not None else None)
    return Observation(obs_id="obs-1", date="2023-04-05", category="Laboratory", test=GLUCOSE,
                       value=value, value_string=f"{value} mg/dL", unit="mg/dL",
                       reference=reference, **kwargs)


class TestObservation:
    def test_code_and_ids_come_from_the_test(self):
        obs = glucose()
        assert obs.code == "Glucose"
        assert obs.primary_code_id == "http://loinc.org2345-7"
        assert obs.datecode == "2023-04-05http://loinc.org2345-7"

    def test_abnormal(self):
        assert glucose(105.0).is_abnormal
        assert not glucose(90.0).is_abnormal
        assert not glucose(range_text=None).is_abnormal
        assert not glucose(range_text=None).has_reference


class TestObservationToDict:
    def test_fields(self):
        out = glucose().to_dict()
        assert out["observationId"] == "obs-1"
        assert out["date"] == "2023-04-05"
        assert out["category"] == "Laboratory"
        assert out["testMeta"] == {"testDescription": "Glucose",
                                   "codings": {"http://loinc.org": "2345-7"}}
        assert out["observedResult"]["valueString"] == "105.0 mg/dL"
        assert out["observedResult"]["value"] == 105.0
        assert out["observedResult"]["referenceRange"]["interpretation"] == "HIGH OUT OF RANGE"
        assert "comment" not in out["observedResult"]

    def test_optional_fields(self):
        out = glucose(value=None, range_text=None, comment="Fasting").to_dict()
        assert "value" not in out["observedResult"]
        assert "referenceRange" not in out["observedResult"]
        assert out["observedResult"]["comment"] == "Fasting"
