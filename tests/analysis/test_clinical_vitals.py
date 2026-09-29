import pytest

from health_data_parser.analysis.vitals import add_clinical_vitals
from health_data_parser.ingest.fhir_json import ObservationRules, parse_observation
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.model.units import HeightUnit, TemperatureUnit, VitalSignCategory, WeightUnit
from health_data_parser.model.vitals import VitalSigns
from health_data_parser.options import ParseOptions


@pytest.fixture
def options(export_dir):
    return ParseOptions(str(export_dir))


@pytest.fixture
def add_vital(make_lab_observation):
    store = ObservationStore()

    def _add(category, display, value, unit, date="2023-04-05", data=None):
        if data is None:
            data = make_lab_observation(display=display, code=display, value=value, unit=unit,
                                        date=date, range_text=None, category="Vital Signs")
            if unit is None:
                del data["valueQuantity"]["unit"]
        obs = parse_observation(data, f"obs-{len(store.vitals)}", store, ObservationRules(),
                                disallowed_codes=())
        obs.vital_sign_category = category
        store.add_vital(obs)
        return store
    return _add


def vitals_for(store, options):
    vitals = VitalSigns(HeightUnit.CM, WeightUnit.LB, TemperatureUnit.C)
    add_clinical_vitals(store, vitals, options)
    return vitals


class TestAddClinicalVitals:
    def test_height_weight_and_bmi(self, add_vital, options):
        add_vital(VitalSignCategory.HEIGHT, "Body height", 70.866, "in")
        store = add_vital(VitalSignCategory.WEIGHT, "Body weight", 81, "kg")
        vitals = vitals_for(store, options)
        assert vitals.height.values == [pytest.approx(180.0, abs=0.01)]
        assert vitals.weight.values == [pytest.approx(178.57, abs=0.01)]
        assert vitals.bmi.values == [pytest.approx(25.0, abs=0.01)]

    def test_no_bmi_without_both(self, add_vital, options):
        store = add_vital(VitalSignCategory.HEIGHT, "Body height", 180, "cm")
        vitals = vitals_for(store, options)
        assert vitals.height.count == 1
        assert vitals.bmi.count == 0

    @pytest.mark.parametrize("value, unit", [(98.6, "[degF]"), (37, "Cel"), (98.6, None), (37, None)])
    def test_temperature_is_normalized(self, add_vital, options, value, unit):
        store = add_vital(VitalSignCategory.TEMPERATURE, "Body temperature", value, unit)
        assert vitals_for(store, options).temperature.values == [pytest.approx(37.0)]

    def test_pulse_is_not_in_motion(self, add_vital, options):
        store = add_vital(VitalSignCategory.PULSE, "Pulse", 62, "/min")
        vitals = vitals_for(store, options)
        assert vitals.pulse.readings[0].motion == 0
        assert vitals.pulse.unit == "/min"

    def test_readings_are_at_local_midnight(self, add_vital, options):
        store = add_vital(VitalSignCategory.PULSE, "Pulse", 62, "/min")
        time = vitals_for(store, options).pulse.readings[0].time
        assert (time.date().isoformat(), time.hour, time.minute) == ("2023-04-05", 0, 0)
        assert time.tzinfo is not None

    def test_blood_pressure(self, make_blood_pressure_observation, add_vital, options):
        store = add_vital(VitalSignCategory.BLOOD_PRESSURE, None, None, None,
                          data=make_blood_pressure_observation())
        bp = vitals_for(store, options).blood_pressure
        assert (bp.systolic.values, bp.diastolic.values) == ([120.0], [80.0])
        assert bp.unit == "mm[Hg]"

    def test_missing_unit_is_skipped(self, add_vital, options):
        store = add_vital(VitalSignCategory.PULSE, "Pulse", 62, None)
        assert vitals_for(store, options).pulse.count == 0

    def test_unconvertible_date_is_skipped_but_others_kept(self, add_vital, options):
        add_vital(VitalSignCategory.TEMPERATURE, "Body temperature", 37, "kelvin", date="2023-01-10")
        store = add_vital(VitalSignCategory.PULSE, "Pulse", 62, "/min")
        vitals = vitals_for(store, options)
        assert vitals.temperature.count == 0
        assert vitals.pulse.count == 1

    def test_clinical_observation_count(self, add_vital, options):
        add_vital(VitalSignCategory.PULSE, "Pulse", 62, "/min")
        store = add_vital(VitalSignCategory.PULSE, "Pulse", 64, "/min", date="2023-04-06")
        assert vitals_for(store, options).clinical_observation_count == 2
