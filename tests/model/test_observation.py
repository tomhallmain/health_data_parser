import pytest

from health_data_parser.model.observation import CategoryError, Observation, ObservationVital

VITAL_SIGN_CATEGORIES = ["Vital Signs", "Pulse"]
DISALLOWED_CODES = ["NARRATIVE"]


def make_observation(data, tests=None, date_codes=None, start_year=None,
                     skip_long_values=False, obs_id="obs-1"):
    return Observation(data, obs_id, [] if tests is None else tests,
                       {} if date_codes is None else date_codes, start_year,
                       skip_long_values, False, 0.15, VITAL_SIGN_CATEGORIES, DISALLOWED_CODES)


class TestObservation:
    def test_lab_observation_fields(self, make_lab_observation):
        obs = make_observation(make_lab_observation())
        assert obs.observation_complete
        assert obs.code == "Glucose"
        assert obs.category == "Laboratory"
        assert obs.date == "2023-04-05"
        assert obs.value == 105.0
        assert obs.unit == "mg/dL"
        assert obs.value_string == "105 mg/dL"
        assert obs.datecode == "2023-04-05http://loinc.org2345-7"

    def test_out_of_range_value_is_abnormal(self, make_lab_observation):
        obs = make_observation(make_lab_observation(value=105))
        assert obs.has_reference
        assert obs.result.is_abnormal
        assert obs.result.interpretation == "+++"

    def test_without_reference_range(self, make_lab_observation):
        obs = make_observation(make_lab_observation(range_text=None))
        assert not obs.has_reference
        assert obs.result is None

    def test_numeric_value_is_extracted_from_string_quantity(self, make_lab_observation):
        obs = make_observation(make_lab_observation(value="<5.2"))
        assert obs.value == 5.2

    def test_value_string_observation(self, make_lab_observation):
        data = make_lab_observation(range_text="NEG")
        del data["valueQuantity"]
        data["valueString"] = "POSITIVE"
        obs = make_observation(data)
        assert obs.value is None
        assert obs.result.is_abnormal

    def test_vital_sign_category_is_handled_separately(self, make_lab_observation):
        with pytest.raises(CategoryError):
            make_observation(make_lab_observation(category="Vital Signs"))

    def test_before_start_year_is_skipped(self, make_lab_observation):
        with pytest.raises(AssertionError, match="before start year"):
            make_observation(make_lab_observation(date="2019-01-01"), start_year=2020)

    def test_duplicate_datecode_is_skipped(self, make_lab_observation):
        date_codes = {"2023-04-05http://loinc.org2345-7": "earlier-obs"}
        with pytest.raises(AssertionError, match="already recorded"):
            make_observation(make_lab_observation(), date_codes=date_codes)

    def test_disallowed_code_is_skipped(self, make_lab_observation):
        with pytest.raises(AssertionError, match="Skipping observation for code"):
            make_observation(make_lab_observation(display="Narrative"))

    def test_missing_value_raises(self, make_lab_observation):
        data = make_lab_observation()
        del data["valueQuantity"]
        with pytest.raises(ValueError, match="value not found"):
            make_observation(data)

    def test_long_value_skipped_only_when_requested(self, make_lab_observation):
        data = make_lab_observation(range_text=None)
        del data["valueQuantity"]
        data["valueString"] = "x" * 201
        assert make_observation(data).value_string == "x" * 201
        with pytest.raises(ValueError, match="excessively long"):
            make_observation(data, skip_long_values=True)

    def test_see_below_prefix_is_removed(self, make_lab_observation):
        data = make_lab_observation(range_text=None)
        del data["valueQuantity"]
        data["valueString"] = "SEE BELOW\nDetected"
        assert make_observation(data).value_string == "Detected"

    def test_seen_test_is_reused(self, make_lab_observation):
        tests = []
        first = make_observation(make_lab_observation(date="2023-01-01"), tests=tests)
        tests.append(first.test)
        second = make_observation(make_lab_observation(date="2023-02-01"), tests=tests)
        assert second.is_seen_test
        assert second.test_index == 0
        assert second.test is first.test


class TestObservationToDict:
    def test_includes_test_meta(self, make_lab_observation):
        tests = []
        obs = make_observation(make_lab_observation(), tests=tests)
        # ObservationJSONDataParser records each new test after construction
        tests.append(obs.test)
        out = obs.to_dict("obs-1", tests)
        assert out["testMeta"] == {"testDescription": "Glucose",
                                   "codings": {"http://loinc.org": "2345-7"}}

    def test_fields(self, make_lab_observation):
        tests = []
        obs = make_observation(make_lab_observation(), tests=tests)
        tests.append(obs.test)
        out = obs.to_dict("obs-1", tests)
        assert out["observationId"] == "obs-1"
        assert out["date"] == "2023-04-05"
        assert out["category"] == "Laboratory"
        assert out["observedResult"]["valueString"] == "105 mg/dL"
        assert out["observedResult"]["value"] == 105.0
        assert out["observedResult"]["referenceRange"]["interpretation"] == "HIGH OUT OF RANGE"
        assert "comment" not in out["observedResult"]

    def test_unrecorded_test_is_omitted(self, make_lab_observation):
        obs = make_observation(make_lab_observation())
        assert "testMeta" not in obs.to_dict("obs-1", [])


class TestObservationVital:
    def test_blood_pressure_components(self, make_blood_pressure_observation):
        obs = ObservationVital(make_blood_pressure_observation(), "bp-1", [], {}, None, False, False, 0.15)
        assert obs.value == 120.0
        assert obs.value2 == 80.0
        assert obs.value_string == "120.0/80.0 mm[Hg]"
        assert obs.vital_sign_category is None

    def test_blood_pressure_missing_component(self, make_blood_pressure_observation):
        data = make_blood_pressure_observation()
        data["component"] = data["component"][:1]
        with pytest.raises(ValueError, match="Systolic or Diastolic value not found"):
            ObservationVital(data, "bp-1", [], {}, None, False, False, 0.15)
