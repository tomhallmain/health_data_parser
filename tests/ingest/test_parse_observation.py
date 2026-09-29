import pytest

from health_data_parser.ingest.fhir_json import ObservationRules, parse_observation
from health_data_parser.model.observation import SkipObservation
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.model.reference_range import Interpretation


def parse(data, store=None, obs_id="obs-1", disallowed_codes=("NARRATIVE",), **rules):
    return parse_observation(data, obs_id, ObservationStore() if store is None else store,
                             ObservationRules(**rules), disallowed_codes=disallowed_codes)


class TestParseObservation:
    def test_lab_observation_fields(self, make_lab_observation):
        obs = parse(make_lab_observation())
        assert obs.obs_id == "obs-1"
        assert obs.code == "Glucose"
        assert obs.category == "Laboratory"
        assert obs.date == "2023-04-05"
        assert obs.value == 105.0
        assert obs.unit == "mg/dL"
        assert obs.value_string == "105 mg/dL"
        assert obs.datecode == "2023-04-05http://loinc.org2345-7"

    def test_out_of_range_value_is_abnormal(self, make_lab_observation):
        obs = parse(make_lab_observation(value=105))
        assert obs.has_reference
        assert obs.is_abnormal
        assert obs.reference.interpretation is Interpretation.HIGH_OUT_OF_RANGE

    def test_without_reference_range(self, make_lab_observation):
        obs = parse(make_lab_observation(range_text=None))
        assert not obs.has_reference
        assert not obs.is_abnormal

    def test_reference_range_without_text_is_ignored(self, make_lab_observation):
        data = make_lab_observation()
        data["referenceRange"] = [{"low": {"value": 70}, "high": {"value": 99}}]
        obs = parse(data)
        assert not obs.has_reference

    def test_rules_apply_to_the_reference_range(self, make_lab_observation):
        # 97 is within 15% of the top of 70-99
        assert parse(make_lab_observation(value=97)).is_abnormal
        assert not parse(make_lab_observation(value=97), skip_in_range_abnormal_results=True).is_abnormal

    def test_numeric_value_is_extracted_from_string_quantity(self, make_lab_observation):
        assert parse(make_lab_observation(value="<5.2")).value == 5.2

    def test_value_string_observation(self, make_lab_observation):
        data = make_lab_observation(range_text="NEG")
        del data["valueQuantity"]
        data["valueString"] = "POSITIVE"
        obs = parse(data)
        assert obs.value is None
        assert obs.is_abnormal

    def test_comment(self, make_lab_observation):
        data = make_lab_observation()
        data["comments"] = "Fasting"
        assert parse(data).comment == "Fasting"

    def test_before_start_year_is_skipped(self, make_lab_observation):
        with pytest.raises(SkipObservation, match="before start year"):
            parse(make_lab_observation(date="2019-01-01"), start_year=2020)

    def test_duplicate_datecode_is_skipped(self, make_lab_observation):
        store = ObservationStore()
        store.add(parse(make_lab_observation(), store=store))
        with pytest.raises(SkipObservation, match="already recorded"):
            parse(make_lab_observation(), store=store, obs_id="obs-2")

    def test_disallowed_code_is_skipped(self, make_lab_observation):
        with pytest.raises(SkipObservation, match="Skipping observation for code"):
            parse(make_lab_observation(display="Narrative"))

    def test_missing_value_is_skipped(self, make_lab_observation):
        data = make_lab_observation()
        del data["valueQuantity"]
        with pytest.raises(SkipObservation, match="value not found"):
            parse(data)

    def test_missing_code_description_is_an_error(self, make_lab_observation):
        # A malformed resource rather than a result the report leaves out
        data = make_lab_observation()
        data["code"] = {"coding": [{"system": "http://loinc.org", "code": "2345-7"}]}
        with pytest.raises(ValueError, match="Code description or ID is None"):
            parse(data)

    def test_null_unit_is_ignored(self, make_lab_observation):
        data = make_lab_observation(range_text=None)
        data["valueQuantity"]["unit"] = None
        obs = parse(data)
        assert obs.unit is None
        assert obs.value_string == "105"

    def test_long_value_skipped_only_when_requested(self, make_lab_observation):
        data = make_lab_observation(range_text=None)
        del data["valueQuantity"]
        data["valueString"] = "x" * 201
        assert parse(data).value_string == "x" * 201
        with pytest.raises(SkipObservation, match="excessively long"):
            parse(data, skip_long_values=True)

    @pytest.mark.parametrize("value_string", ["SEE BELOW\nDetected", "See Below\nDetected"])
    def test_see_below_prefix_is_removed(self, make_lab_observation, value_string):
        data = make_lab_observation(range_text=None)
        del data["valueQuantity"]
        data["valueString"] = value_string
        assert parse(data).value_string == "Detected"

    def test_see_below_alone_is_skipped(self, make_lab_observation):
        data = make_lab_observation(range_text=None)
        del data["valueQuantity"]
        data["valueString"] = "SEE BELOW"
        with pytest.raises(SkipObservation, match="unparseable value"):
            parse(data)

    def test_seen_test_is_reused_and_gains_codings(self, make_lab_observation):
        store = ObservationStore()
        first = parse(make_lab_observation(date="2023-01-01"), store=store)
        store.add(first)
        data = make_lab_observation(date="2023-02-01")
        data["code"]["coding"].append({"system": "urn:other", "code": "GLU"})
        second = parse(data, store=store, obs_id="obs-2")
        assert second.test is first.test
        assert first.test.codings == {"http://loinc.org": "2345-7", "urn:other": "GLU"}


class TestBloodPressure:
    def test_components(self, make_blood_pressure_observation):
        obs = parse(make_blood_pressure_observation(), disallowed_codes=())
        assert obs.value == 120.0
        assert obs.value2 == 80.0
        assert obs.unit == "mm[Hg]"
        assert obs.value_string == "120.0/80.0 mm[Hg]"

    def test_missing_component(self, make_blood_pressure_observation):
        data = make_blood_pressure_observation()
        data["component"] = data["component"][:1]
        with pytest.raises(SkipObservation, match="Systolic or Diastolic value not found"):
            parse(data, disallowed_codes=())
