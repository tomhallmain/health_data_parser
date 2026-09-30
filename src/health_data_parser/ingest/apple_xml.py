from datetime import datetime
import xml.etree.ElementTree as ET

from health_data_parser.errors import HealthDataParseError
from health_data_parser.model.units import HeightUnit, WeightUnit, TemperatureUnit, convert, get_age
from health_data_parser.utils.translations import _
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('xml_parser')

_TYPE_PREFIX = "HKQuantityTypeIdentifier"


class AppleHealthXMLParser:
    """Reads an Apple Health export.xml into a VitalSigns and the subject's
    details into options.subject."""

    def __init__(self, vital_signs, options):
        self.vital_signs = vital_signs
        self.subject = options.subject
        self.verbose = options.verbose
        self.normal_height_unit = options.normal_height_unit
        self.normal_weight_unit = options.normal_weight_unit
        self.normal_temperature_unit = options.normal_temperature_unit
        self.datetime_format = options.datetime_format
        self.start_year = options.start_year

    def parse(self, export_xml_file_path):
        logger.info("Parsing XML...")
        try:
            root = ET.parse(export_xml_file_path).getroot()
            self._parse_subject(root.find("Me").attrib)
            blood_pressure_count = self._parse_blood_pressure(root)
            heart_rate_count = self._parse_records(root)
        except Exception as e:
            if self.verbose:
                logger.error(f"Error details: {e}")
            raise HealthDataParseError(
                _("An exception occurred in parsing XML export files: {0}").format(e)) from e

        vitals = self.vital_signs
        vitals.xml_observation_count = (blood_pressure_count + heart_rate_count
                                        + vitals.hrv.count + vitals.temperature.count)
        if self.verbose:
            for series in [vitals.blood_pressure, vitals.pulse, vitals.height, vitals.weight,
                           vitals.hrv, vitals.spo2, vitals.stand, vitals.steps, vitals.temperature]:
                if series.count > 0:
                    logger.info(f"Found {series.count} {series.name} observations in XML data.")

    def _parse_subject(self, me):
        if "birthDate" not in self.subject:
            birth_date_str = me["HKCharacteristicTypeIdentifierDateOfBirth"]
            self.subject["birthDate"] = birth_date_str
            self.subject["age"] = get_age(datetime.fromisoformat(birth_date_str))
        self.subject["sex"] = me["HKCharacteristicTypeIdentifierBiologicalSex"].replace(
            "HKBiologicalSex", "")
        self.subject["bloodType"] = me["HKCharacteristicTypeIdentifierBloodType"].replace(
            "HKBloodType", "")

    def _record_time(self, element):
        """The element's start time, or None when it's missing, unparseable, or
        before the start year."""
        if "startDate" not in element.attrib:
            return None
        try:
            time = datetime.strptime(element.attrib["startDate"], self.datetime_format)
        except Exception:
            if self.verbose:
                logger.error("Exception on constructing date from XML observation")
            return None
        if self.start_year is not None and self.start_year > time.year:
            return None
        return time

    def _parse_blood_pressure(self, root):
        count = 0
        for correlation in root.iter("Correlation"):
            if correlation.attrib.get("type") != "HKCorrelationTypeIdentifierBloodPressure":
                continue
            time = self._record_time(correlation)
            if time is None:
                continue
            systolic = None
            diastolic = None
            for rec in correlation.iter("Record"):
                if rec.attrib["type"] == _TYPE_PREFIX + "BloodPressureSystolic":
                    systolic = int(rec.attrib["value"])
                elif rec.attrib["type"] == _TYPE_PREFIX + "BloodPressureDiastolic":
                    diastolic = int(rec.attrib["value"])
            if systolic is None or diastolic is None:
                if self.verbose:
                    logger.warning("Missing systolic or diastolic for blood pressure observation in XML data")
                continue
            self.vital_signs.note_xml_date(time)
            self.vital_signs.blood_pressure.add(time, systolic, diastolic)
            count += 1
        return count

    def _parse_records(self, root):
        """Adds single-value records to their series; returns the heart rate count."""
        vitals = self.vital_signs
        heart_rate_count = 0
        for rec in root.iter("Record"):
            if "type" not in rec.attrib or "value" not in rec.attrib:
                continue
            rec_type = rec.attrib["type"]
            try:
                value = float(rec.attrib["value"])
            except Exception:
                continue
            time = self._record_time(rec)
            if time is None:
                continue

            if rec_type == _TYPE_PREFIX + "Height":
                value = self._converted(rec, value, "height", lambda unit: convert(
                    self.normal_height_unit, HeightUnit.from_value(unit), value))
                series = vitals.height
            elif rec_type == _TYPE_PREFIX + "BodyMass":
                value = self._converted(rec, value, "weight", lambda unit: convert(
                    self.normal_weight_unit, WeightUnit.from_value(unit), value))
                series = vitals.weight
            elif rec_type == _TYPE_PREFIX + "HeartRate":
                motion = self._motion(rec)
                # Implausible readings: too high, too high while not at rest, too low
                if value > 155 or (value > 140 and motion != 0) or value < 35:
                    continue
                vitals.note_xml_date(time)
                vitals.pulse.add(time, value, motion)
                heart_rate_count += 1
                continue
            elif rec_type == _TYPE_PREFIX + "HeartRateVariabilitySDNN":
                if value > 160:
                    continue
                series = vitals.hrv
            elif rec_type == _TYPE_PREFIX + "OxygenSaturation":
                series = vitals.spo2
            elif rec_type == _TYPE_PREFIX + "AppleStandTime":
                series = vitals.stand
            elif rec_type == _TYPE_PREFIX + "StepCount":
                series = vitals.steps
            elif rec_type == _TYPE_PREFIX + "BodyTemperature":
                # Without a unit, assume Fahrenheit for values too high to be Celsius
                value = self._converted(
                    rec, value, "temperature",
                    lambda unit: TemperatureUnit.from_value(unit).convertTo(
                        self.normal_temperature_unit, value),
                    default_unit="F" if value > 45 else "C")
                series = vitals.temperature
            else:
                continue

            if value is None:
                continue
            vitals.note_xml_date(time)
            series.add(time, value)
        return heart_rate_count

    def _converted(self, rec, value, kind, convert_from, default_unit=None):
        """`value` converted from the record's unit to the normal unit, or None
        when the record has no unit (and there's no default) or it can't be
        converted."""
        unit = rec.attrib.get("unit", default_unit)
        if unit is None:
            return None
        try:
            return convert_from(unit)
        except Exception as e:
            if self.verbose:
                logger.error(f"Error converting {kind} unit: {e}")
                logger.error(f"Unit: {unit}")
            return None

    def _motion(self, rec):
        metadata_entry = rec.find("MetadataEntry")
        if (metadata_entry is not None
                and metadata_entry.attrib.get("key") == "HKMetadataKeyHeartRateMotionContext"):
            self.vital_signs.motion_data_found = True
            return int(metadata_entry.attrib["value"])
        return 0
