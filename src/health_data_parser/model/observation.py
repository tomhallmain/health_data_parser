from dataclasses import dataclass

from health_data_parser.model.lab_test import LabTest
from health_data_parser.model.reference_range import ReferenceRange
from health_data_parser.model.units import VitalSignCategory


class SkipObservation(Exception):
    """An observation the report leaves out; the message says why."""


@dataclass
class Observation:
    """One result from clinical records (a lab result or a vital sign)."""
    obs_id: str
    # YYYY-MM-DD
    date: str
    category: str
    # Shared by every observation of the same test, so codings seen on any of
    # them accumulate in one place
    test: LabTest
    value: float | None
    value_string: str
    unit: str | None = None
    # Diastolic pressure for blood pressure readings (value is systolic)
    value2: float | None = None
    reference: ReferenceRange | None = None
    comment: str | None = None
    vital_sign_category: VitalSignCategory | None = None

    @property
    def code(self):
        """The test's description, which groups results across dates."""
        return self.test.test_desc

    @property
    def primary_code_id(self):
        return self.test.primary_id

    @property
    def datecode(self):
        return self.date + self.primary_code_id

    @property
    def has_reference(self):
        return self.reference is not None

    @property
    def is_abnormal(self):
        return self.reference is not None and self.reference.is_abnormal

    def to_dict(self):
        out = {}
        out["observationId"] = self.obs_id
        out["date"] = self.date
        out["category"] = self.category
        out["testMeta"] = self.test.to_dict()
        result = {}
        result["valueString"] = self.value_string
        if self.value is not None:
            result["value"] = self.value
        if self.reference is not None:
            result["referenceRange"] = self.reference.to_dict()
        if self.comment is not None:
            result["comment"] = self.comment
        out["observedResult"] = result
        return out
