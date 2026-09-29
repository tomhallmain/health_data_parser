from datetime import datetime, timezone

from health_data_parser.model.units import (
    VitalSignCategory, HeightUnit, WeightUnit, TemperatureUnit, calculate_bmi, convert)
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('vitals')


def add_clinical_vitals(store, vital_signs, options, verbose=False):
    """Add the vital-sign observations from clinical records to `vital_signs`,
    converting height, weight and temperature to the run's normal units and
    deriving BMI for dates with both a height and a weight.

    Clinical records give a date without a time, so each reading is placed at
    local midnight. A date whose observations can't be processed is skipped.
    """
    if verbose:
        logger.info("Compiling vital signs data from clinical records if present...")
    local_tz = timezone(datetime.now().astimezone().tzinfo.utcoffset(None))

    for date, observations in store.vitals_by_date.items():
        time = datetime.fromisoformat(date).replace(tzinfo=local_tz)
        try:
            _add_date(time, observations, vital_signs, options, verbose)
        except Exception as e:
            if verbose:
                logger.error(f"Error processing vital signs data: {e}")
    vital_signs.clinical_observation_count = len(store.vitals)


def _add_date(time, observations, vital_signs, options, verbose):
    height = height_unit = weight = weight_unit = None
    for obs in observations:
        category = obs.vital_sign_category
        if category is VitalSignCategory.HEIGHT:
            height, height_unit = obs.value, obs.unit
            continue
        if category is VitalSignCategory.WEIGHT:
            weight, weight_unit = obs.value, obs.unit
            continue
        unit = obs.unit
        if obs.value is None or unit is None:
            if category is VitalSignCategory.TEMPERATURE and obs.value is not None:
                # Without a unit, assume Fahrenheit for values too high to be Celsius
                unit = "F" if obs.value > 45 else "C"
            else:
                logger.warning(f"Skipping obs on date {obs.date} of category {category} "
                               "because value or unit was None")
                continue
        if category is VitalSignCategory.BLOOD_PRESSURE:
            vital_signs.blood_pressure.unit = unit
            vital_signs.blood_pressure.add(time, obs.value, obs.value2)
        elif category is VitalSignCategory.PULSE:
            vital_signs.pulse.unit = unit
            # Heart rates in clinical records are taken as not in motion
            vital_signs.pulse.add(time, obs.value, motion=0)
        elif category is VitalSignCategory.RESPIRATION:
            vital_signs.respiration.unit = unit
            vital_signs.respiration.add(time, obs.value)
        elif category is VitalSignCategory.TEMPERATURE:
            temperature = TemperatureUnit.from_value(unit).convertTo(
                options.normal_temperature_unit, obs.value)
            vital_signs.temperature.add(time, round(temperature, 2))

    normalized_height = normalized_weight = None
    if height is not None and height_unit is not None:
        normalized_height = convert(options.normal_height_unit,
                                    HeightUnit.from_value(height_unit), height)
        vital_signs.height.add(time, normalized_height)
    if weight is not None and weight_unit is not None:
        normalized_weight = convert(options.normal_weight_unit,
                                    WeightUnit.from_value(weight_unit), weight)
        vital_signs.weight.add(time, normalized_weight)
    if normalized_height is not None and normalized_weight is not None:
        bmi = calculate_bmi(normalized_height, normalized_weight,
                            options.normal_height_unit, options.normal_weight_unit, verbose)
        vital_signs.bmi.add(time, bmi)


def sort_vital_signs(vital_signs, verbose=False):
    unsorted = vital_signs.sort_readings()
    for name in unsorted:
        logger.warning(f"Readings for {name} mix timezone-aware and naive times and could not be "
                       "sorted; vital signs output that relies on their order may be wrong.")
    if verbose:
        for series in vital_signs.reported_series:
            if series.count > 0:
                logger.info(f"Found {series.count} observations for vital sign: {series.name}")
