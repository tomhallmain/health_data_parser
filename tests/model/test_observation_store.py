from health_data_parser.ingest.fhir_json import ObservationRules, parse_observation
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.model.units import VitalSignCategory

GLUCOSE_ID = "http://loinc.org2345-7"
HEMOGLOBIN_ID = "http://loinc.org718-7"


def add(store, observation, obs_id):
    obs = parse_observation(observation, obs_id, store, ObservationRules())
    store.add(obs)
    return obs


def hemoglobin(make_lab_observation, **kwargs):
    kwargs.setdefault("range_text", "13.5-17.5 g/dL")
    return make_lab_observation(display="Hemoglobin", code="718-7", unit="g/dL", **kwargs)


class TestObservationStore:
    def test_empty(self):
        store = ObservationStore()
        assert (store.codes, store.dates, store.reference_dates) == ([], [], [])
        assert store.abnormal_results == {}
        assert store.abnormal_count == 0
        assert store.interpretations_by_code() == {}

    def test_indexes(self, make_lab_observation):
        store = ObservationStore()
        glucose = add(store, make_lab_observation(date="2023-01-10", value=90), "obs-1")
        add(store, make_lab_observation(date="2023-04-05", value=105), "obs-2")
        add(store, hemoglobin(make_lab_observation, date="2023-04-05", value=14, range_text=None), "obs-3")

        assert store.codes == ["Glucose", "Hemoglobin"]
        assert store.code_ids("Glucose") == [GLUCOSE_ID]
        assert store.dates == ["2023-04-05", "2023-01-10"]
        assert store.reference_dates == ["2023-01-10", "2023-04-05"]
        assert store.find("2023-01-10", GLUCOSE_ID) is glucose
        assert store.find("2023-01-10", HEMOGLOBIN_ID) is None
        assert store.is_recorded("2023-01-10" + GLUCOSE_ID)
        assert len(store.tests) == 2

    def test_abnormal_results(self, make_lab_observation):
        store = ObservationStore()
        add(store, make_lab_observation(date="2023-01-10", value=150), "obs-1")
        add(store, make_lab_observation(date="2023-04-05", value=40), "obs-2")
        add(store, make_lab_observation(date="2023-06-01", value=85), "obs-3")
        add(store, hemoglobin(make_lab_observation, date="2023-04-05", value=13.6), "obs-4")

        assert [o.obs_id for o in store.abnormal_results[GLUCOSE_ID]] == ["obs-1", "obs-2"]
        assert store.abnormal_dates == ["2023-04-05", "2023-01-10"]
        assert store.abnormal_count == 3
        assert store.interpretations_by_code() == {
            "Glucose": ["LOW OUT OF RANGE", "HIGH OUT OF RANGE"],
            "Hemoglobin": ["Low in range"],
        }

    def test_interpretations_without_in_range(self, make_lab_observation):
        store = ObservationStore()
        # A negative boundary only flags results beyond the range by more than the
        # margin, and labels them "in range", even when in-range results are skipped
        rules = ObservationRules(skip_in_range_abnormal_results=True, in_range_abnormal_boundary=-0.1)
        store.add(parse_observation(hemoglobin(make_lab_observation, value=13.0), "obs-1", store, rules))
        store.add(parse_observation(make_lab_observation(value=150), "obs-2", store, rules))
        assert store.find("2023-04-05", HEMOGLOBIN_ID).reference.tag == "--"
        assert store.find("2023-04-05", GLUCOSE_ID).reference.tag == "++"

        assert store.interpretations_by_code(include_in_range=False) == {"Glucose": [], "Hemoglobin": []}
        assert store.interpretations_by_code() == {
            "Glucose": ["High in range"], "Hemoglobin": ["Low in range"]}

    def test_reference_added_later_is_reflected(self, make_lab_observation):
        store = ObservationStore()
        obs = add(store, make_lab_observation(date="2023-01-10", value=150, range_text=None), "obs-1")
        assert store.abnormal_count == 0

        obs.reference = ObservationRules().reference_range("70-99 mg/dL", obs.value,
                                                           obs.value_string, obs.unit)

        assert store.abnormal_count == 1
        assert store.reference_dates == ["2023-01-10"]

    def test_vitals_by_date(self, make_lab_observation):
        store = ObservationStore()
        for obs_id, date in [("v1", "2023-04-05"), ("v2", "2023-01-10"), ("v3", "2023-04-05")]:
            obs = parse_observation(make_lab_observation(display="Pulse", code="8867-4", date=date,
                                                         range_text=None, category="Vital Signs"),
                                    obs_id, store, ObservationRules(), disallowed_codes=())
            obs.vital_sign_category = VitalSignCategory.PULSE
            store.add_vital(obs)

        by_date = store.vitals_by_date
        assert list(by_date) == ["2023-01-10", "2023-04-05"]
        assert [o.obs_id for o in by_date["2023-04-05"]] == ["v1", "v3"]
        assert store.observations == {}
