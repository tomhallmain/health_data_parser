from dataclasses import dataclass
from datetime import datetime

from health_data_parser.model.units import VitalSignCategory

# More heart rate readings than this are taken to mean a wearable recorded
# them, which is also enough data for the heart rate charts
WEARABLE_HEART_RATE_READINGS = 10000


@dataclass
class Reading:
    time: datetime
    value: float
    # Heart rate only: motion context from a wearable, 0 when not in motion
    motion: int | None = None

    def to_dict(self):
        out = {"time": self.time, "value": self.value}
        if self.motion is not None:
            out["motion"] = self.motion
        return out


class VitalSeries:
    """Readings of one vital sign, with statistics computed from them."""

    def __init__(self, name: str, unit: str | None = None):
        self.name = name
        self.unit = unit
        self.readings: list[Reading] = []

    def add(self, time, value, motion=None):
        self.readings.append(Reading(time, value, motion))

    def sort(self):
        """Order readings by time. Raises TypeError, leaving the order unchanged,
        when naive and timezone-aware times are mixed."""
        self.readings = sorted(self.readings, key=lambda reading: reading.time)

    @property
    def count(self):
        return len(self.readings)

    @property
    def values(self):
        return [reading.value for reading in self.readings]

    @property
    def mean(self):
        return sum(self.values) / self.count if self.readings else None

    @property
    def stdev(self):
        """Population standard deviation."""
        if not self.readings:
            return None
        mean = self.mean
        return (sum((value - mean) ** 2 for value in self.values) / self.count) ** (1 / 2)

    @property
    def min(self):
        return min(self.values) if self.readings else None

    @property
    def max(self):
        return max(self.values) if self.readings else None

    @property
    def most_recent(self):
        """The last reading; the most recent once sorted."""
        return self.readings[-1] if self.readings else None

    def to_dict(self, include_readings=False):
        out = {
            "vital": self.name,
            "unit": self.unit,
            "count": self.count,
            "avg": self.mean,
            "max": self.max,
            "min": self.min,
            "stDev": self.stdev,
            "mostRecent": self.most_recent.to_dict() if self.most_recent else None,
        }
        if include_readings:
            out["list"] = [reading.to_dict() for reading in self.readings]
        return out


class BloodPressureSeries:
    """Systolic and diastolic readings taken together.

    Serialized as one vital whose stats are [systolic, diastolic] pairs, named
    by "labels".
    """
    name = VitalSignCategory.BLOOD_PRESSURE.value
    labels = ["BP Systolic", "BP Diastolic"]

    def __init__(self, unit="mmHg"):
        self.unit = unit
        self.systolic = VitalSeries(self.labels[0])
        self.diastolic = VitalSeries(self.labels[1])

    def add(self, time, systolic, diastolic):
        self.systolic.add(time, systolic)
        self.diastolic.add(time, diastolic)

    def sort(self):
        self.systolic.sort()
        self.diastolic.sort()

    @property
    def count(self):
        return self.systolic.count

    def to_dict(self, include_readings=False):
        parts = (self.systolic, self.diastolic)
        out = {
            "vital": self.name,
            "unit": self.unit,
            "labels": list(self.labels),
            "count": self.count,
            "avg": [part.mean for part in parts],
            "max": [part.max for part in parts],
            "min": [part.min for part in parts],
            "stDev": [part.stdev for part in parts],
            "mostRecent": None,
        }
        if self.count > 0:
            out["mostRecent"] = {"time": self.systolic.most_recent.time,
                                 "value": [part.most_recent.value for part in parts]}
        if include_readings:
            out["list"] = [{"time": s.time, "value": [s.value, d.value]}
                           for s, d in zip(self.systolic.readings, self.diastolic.readings)]
        return out


class VitalSigns:
    """All vital-sign series for a run, from export.xml and clinical records.

    Height, weight and temperature are stored in the run's normal units.
    """

    def __init__(self, normal_height_unit, normal_weight_unit, normal_temperature_unit):
        self.height = VitalSeries(VitalSignCategory.HEIGHT.value, normal_height_unit.name.lower())
        self.weight = VitalSeries(VitalSignCategory.WEIGHT.value, normal_weight_unit.name.lower())
        self.bmi = VitalSeries("BMI", "BMI")
        self.temperature = VitalSeries(VitalSignCategory.TEMPERATURE.value, normal_temperature_unit.name)
        self.pulse = VitalSeries(VitalSignCategory.PULSE.value)
        self.respiration = VitalSeries(VitalSignCategory.RESPIRATION.value)
        self.blood_pressure = BloodPressureSeries()
        # SDNN, in milliseconds
        self.hrv = VitalSeries("Heart rate variability", "ms")
        # Parsed from export.xml but not included in reports
        self.spo2 = VitalSeries(VitalSignCategory.SPO2.value, "%")
        self.stand = VitalSeries("Apple stand minutes", "/5min")
        self.steps = VitalSeries("Steps")
        # Blood pressure, heart rate, HRV and temperature records from export.xml
        self.xml_observation_count = 0
        # Vital-sign observations from clinical records
        self.clinical_observation_count = 0
        # Date ordinal of the earliest export.xml record used, None without export.xml data
        self.earliest_xml_ordinal = None
        self.motion_data_found = False

    @property
    def reported_series(self):
        """The series written to observations.json and the PDF, in report order."""
        return [self.height, self.weight, self.bmi, self.temperature, self.pulse,
                self.respiration, self.blood_pressure, self.hrv, self.stand]

    @property
    def observation_count(self):
        return self.xml_observation_count + self.clinical_observation_count

    @property
    def wearable_heart_rate_detected(self):
        return self.pulse.count > WEARABLE_HEART_RATE_READINGS

    def note_xml_date(self, time):
        ordinal = time.toordinal()
        if self.earliest_xml_ordinal is None or ordinal < self.earliest_xml_ordinal:
            self.earliest_xml_ordinal = ordinal

    def sort_readings(self):
        """Order every series by time.

        Returns the names of series left unsorted because naive and
        timezone-aware times were mixed in them.
        """
        unsorted = []
        for series in [self.height, self.weight, self.bmi, self.temperature, self.pulse,
                       self.respiration, self.blood_pressure, self.hrv, self.spo2,
                       self.stand, self.steps]:
            try:
                series.sort()
            except TypeError:
                unsorted.append(series.name)
        return unsorted
