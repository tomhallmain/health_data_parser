from copy import deepcopy
from datetime import datetime
import xml.etree.ElementTree as ET

from data.units import VitalSignCategory, HeightUnit, WeightUnit, TemperatureUnit
from data.units import convert, get_age, base_stats, set_stats


class AppleHealthXMLData:
    def __init__(self, normal_height_unit, normal_weight_unit):
        self.blood_pressure_stats = {
            "vital": VitalSignCategory.BLOOD_PRESSURE.value, "count": 0,
            "labels": ["BP Systolic", "BP Diastolic"],
            "sum": [0, 0],
            "avg": [None, None],
            "max": [None, None],
            "min": [None, None],
            "mostRecent": [None, None],
            "unit": "mmHg",
            "list": []}
        self.bmi_stats = deepcopy(base_stats)
        self.height_stats = deepcopy(base_stats)
        self.hrv_stats = deepcopy(base_stats)
        self.pulse_stats = deepcopy(base_stats)
        self.respiration_stats = deepcopy(base_stats)
        self.spo2_stats = deepcopy(base_stats)
        self.stand_stats = deepcopy(base_stats)
        self.step_stats = deepcopy(base_stats)
        self.temperature_stats = deepcopy(base_stats)
        self.weight_stats = deepcopy(base_stats)
        self.bmi_stats["vital"] = "BMI"
        self.bmi_stats["unit"] = "BMI"
        self.height_stats["vital"] = VitalSignCategory.HEIGHT.value
        self.height_stats["unit"] = normal_height_unit.name.lower()
        self.hrv_stats["vital"] = "Heart rate variability"
        self.hrv_stats["unit"] = "HRV"
        self.respiration_stats["vital"] = VitalSignCategory.RESPIRATION.value
        self.pulse_stats["vital"] = VitalSignCategory.PULSE.value
        self.spo2_stats["vital"] = VitalSignCategory.SPO2.value
        self.spo2_stats["unit"] = "%"
        self.stand_stats["vital"] = "Apple stand minutes"
        self.stand_stats["unit"] = "/5min"
        self.step_stats["vital"] = "Steps"
        self.temperature_stats["vital"] = VitalSignCategory.TEMPERATURE.value
        self.weight_stats["vital"] = VitalSignCategory.WEIGHT.value
        self.weight_stats["unit"] = normal_weight_unit.name.lower()
        self.xml_vitals_observations_count = 0
        self.blood_pressure_stats_preset = False
        self.motion_data_found = False

        self.vitals_stats_list = [
            self.height_stats, self.weight_stats, self.bmi_stats,
            self.temperature_stats, self.pulse_stats, self.respiration_stats,
            self.blood_pressure_stats, self.hrv_stats, self.stand_stats, self.step_stats]


    def set_observations_count(self, blood_pressure_count, heart_rate_count):
        self.xml_vitals_observations_count = (blood_pressure_count + heart_rate_count
            + self.hrv_stats["count"] + self.temperature_stats["count"])

    def finalize(self, verbose,
            blood_pressure_observations, blood_pressure_count, blood_pressure_sums,
            heart_rate_observations, heart_rate_count, heart_rate_sum):

        if self.blood_pressure_stats["count"] > 0:
            self.blood_pressure_stats_preset = True
            if verbose:
                print("Found " + str(len(blood_pressure_observations))
                            + " blood pressure observations in XML data.")
            self.blood_pressure_stats["count"] = blood_pressure_count
            self.blood_pressure_stats["sum"] = blood_pressure_sums
        if self.pulse_stats["count"] > 0:
            if verbose:
                print("Found " + str(len(heart_rate_observations))
                        + " heart rate observations in XML data.")
            self.pulse_stats["count"] = heart_rate_count
            self.pulse_stats["sum"] = heart_rate_sum
        if verbose:
            if self.height_stats["count"] > 0:
                print("Found " + str(self.height_stats["count"])
                    + " height observations in XML data.")
            if self.weight_stats["count"] > 0:
                print("Found " + str(self.weight_stats["count"])
                    + " weight observations in XML data.")
            if self.hrv_stats["count"] > 0:
                print("Found " + str(self.hrv_stats["count"])
                    + " heart rate variability observations in XML data.")
            if self.spo2_stats["count"] > 0:
                print("Found " + str(self.spo2_stats["count"])
                    + " oxygen saturation observations in XML data.")
            if self.stand_stats["count"] > 0:
                print("Found " + str(self.stand_stats["count"])
                    + " stand observations in XML data.")
            if self.step_stats["count"] > 0:
                print("Found " + str(self.step_stats["count"])
                    + " step observations in XML data.")
            if self.temperature_stats["count"] > 0:
                print("Found " + str(self.temperature_stats["count"])
                    + " temperature observations in XML data.")


class AppleHealthXMLParser:
    min_xml_ordinal = 99999999

    def __init__(self, apple_health_data, args):
        self.data = apple_health_data
        self.subject = args.subject
        self.verbose = args.verbose
        self.normal_height_unit = args.normal_height_unit
        self.normal_weight_unit = args.normal_weight_unit
        self.normal_temperature_unit = args.normal_temperature_unit
        self.datetime_format = args.datetime_format
        self.start_year = args.start_year

    def parse(self, export_xml_file_path):
        print("Parsing XML...")
        try:
            tree = ET.parse(export_xml_file_path)
            root = tree.getroot()
            me = root.find("Me").attrib
            if "birthDate" not in self.subject:
                birth_date_str = me["HKCharacteristicTypeIdentifierDateOfBirth"]
                birth_date = datetime.fromisoformat(birth_date_str)
                self.subject["birthDate"] = birth_date_str
                self.subject["age"] = get_age(birth_date)
            self.subject["sex"] = me["HKCharacteristicTypeIdentifierBiologicalSex"].replace(
                "HKBiologicalSex", "")
            self.subject["bloodType"] = me["HKCharacteristicTypeIdentifierBloodType"].replace(
                "HKBloodType", "")
            blood_pressure_observations = []
            blood_pressure_sums = [0, 0]
            blood_pressure_count = 0
            blood_pressure_max = [None, None]
            blood_pressure_min = [None, None]
            heart_rate_observations = []
            heart_rate_sum = 0
            heart_rate_count = 0
            heart_rate_max = None
            heart_rate_min = None

            for correlation in root.iter("Correlation"):
                if "type" not in correlation.attrib:
                    continue
                if correlation.attrib["type"] == "HKCorrelationTypeIdentifierBloodPressure":
                    if "startDate" in correlation.attrib:
                        try:
                            time = datetime.strptime(
                                correlation.attrib["startDate"], self.datetime_format)
                        except Exception:
                            if self.verbose:
                                print(
                                    "Exception on constructing date from XML observation")
                        if self.start_year is not None and self.start_year > time.year:
                            continue
                    else:
                        continue

                    blood_pressure_obs = {}
                    systolic = None
                    diastolic = None
                    for rec in correlation.iter("Record"):
                        if rec.attrib["type"] == "HKQuantityTypeIdentifierBloodPressureSystolic":
                            systolic = int(rec.attrib["value"])
                        elif rec.attrib["type"] == "HKQuantityTypeIdentifierBloodPressureDiastolic":
                            diastolic = int(rec.attrib["value"])
                    if systolic is None or diastolic is None:
                        if self.verbose:
                            print("Missing both systolic and diastolic for blood pressure observation in XML data")
                        continue
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    blood_pressure_obs["value"] = [systolic, diastolic]
                    blood_pressure_obs["time"] = time
                    blood_pressure_observations.append(blood_pressure_obs)
                    blood_pressure_count += 1
                    blood_pressure_sums[0] += systolic
                    blood_pressure_sums[1] += diastolic
                    if blood_pressure_max[0] is None:
                        blood_pressure_max[0] = systolic
                        blood_pressure_max[1] = diastolic
                        blood_pressure_min[0] = systolic
                        blood_pressure_min[1] = diastolic
                    else:
                        if blood_pressure_max[0] < systolic:
                            blood_pressure_max[0] = systolic
                        elif blood_pressure_min[0] > systolic:
                            blood_pressure_min[0] = systolic
                        if blood_pressure_max[1] < diastolic:
                            blood_pressure_max[1] = diastolic
                        elif blood_pressure_min[1] > diastolic:
                            blood_pressure_min[1] = diastolic
            for rec in root.iter("Record"):
                if "type" not in rec.attrib:
                    continue

                rec_type = rec.attrib["type"]
                obs = {}

                if "value" in rec.attrib:
                    try:
                        value = float(rec.attrib["value"])
                    except Exception:
                        continue
                    obs["value"] = value
                else:
                    continue
                if "startDate" in rec.attrib:
                    try:
                        time = datetime.strptime(
                            rec.attrib["startDate"], self.datetime_format)
                    except Exception:
                        if self.verbose:
                            print("Exception on constructing date from XML observation")
                    if self.start_year is not None and self.start_year > time.year:
                        continue
                else:
                    continue

                if rec_type == "HKQuantityTypeIdentifierHeight":
                    if "unit" in rec.attrib:
                        try:
                            value = convert(self.normal_height_unit, HeightUnit.from_value(
                                        rec.attrib["unit"]), value)
                        except Exception as e:
                            if self.verbose:
                                print(e)
                                print(rec.attrib["unit"])
                            continue
                    else:
                        continue
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.height_stats, time, value)
                elif rec_type == "HKQuantityTypeIdentifierBodyMass":
                    if "unit" in rec.attrib:
                        try:
                            value = convert(self.normal_weight_unit, WeightUnit.from_value(
                                        rec.attrib["unit"]), value)
                        except Exception as e:
                            if self.verbose:
                                print(e)
                                print(rec.attrib["unit"])
                            continue
                    else:
                        continue
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.weight_stats, time, value)
                elif rec_type == "HKQuantityTypeIdentifierHeartRate":
                    metadataentry = rec.find("MetadataEntry")
                    if (metadataentry is not None
                            and "key" in metadataentry.attrib
                            and metadataentry.attrib["key"] == "HKMetadataKeyHeartRateMotionContext"):
                        obs["motion"] = int(metadataentry.attrib["value"])
                        self.data.motion_data_found = True
                    else:
                        obs["motion"] = 0
                    if value > 155:
                        continue
                    elif value > 140 and obs["motion"] != 0:
                        continue
                    elif value < 35:
                        continue
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    obs["time"] = time
                    heart_rate_observations.append(obs)
                    heart_rate_count += 1
                    heart_rate_sum += value
                    heart_rate_most_recent = value
                    if heart_rate_max is None:
                        heart_rate_max = value
                        heart_rate_min = value
                    elif value > heart_rate_max:
                        heart_rate_max = value
                    elif value < heart_rate_min:
                        heart_rate_min = value
                elif rec_type == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                    if value > 160:
                        continue
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.hrv_stats, time, value)
                elif rec_type == "HKQuantityTypeIdentifierOxygenSaturation":
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.spo2_stats, time, value)
                elif rec_type == "HKQuantityTypeIdentifierAppleStandTime":
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.stand_stats, time, value)
                elif rec_type == "HKQuantityTypeIdentifierStepCount":
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.step_stats, time, value)
                elif rec_type == "HKQuantityTypeIdentifierBodyTemperature":
                    if "unit" in rec.attrib:
                        try:
                            value = TemperatureUnit.from_value(
                                rec.attrib["unit"]).convertTo(
                                    self.normal_temperature_unit, value)
                        except Exception as e:
                            if self.verbose:
                                print(e)
                                print(rec.attrib["unit"])
                            continue
                    else:
                        try:
                            value = TemperatureUnit.from_value(
                                "F" if value > 45 else "C").convertTo(
                                    self.normal_temperature_unit, value)
                        except Exception as e:
                            if self.verbose:
                                print(e)
                            continue
                    if time.toordinal() < AppleHealthXMLParser.min_xml_ordinal:
                        AppleHealthXMLParser.min_xml_ordinal = time.toordinal()
                    set_stats(self.data.temperature_stats, time, value)

            self.data.blood_pressure_stats["count"] = blood_pressure_count
            self.data.blood_pressure_stats["list"] = blood_pressure_observations
            self.data.blood_pressure_stats["max"] = blood_pressure_max
            self.data.blood_pressure_stats["min"] = blood_pressure_min
            self.data.pulse_stats["count"] = heart_rate_count
            self.data.pulse_stats["list"] = heart_rate_observations
            self.data.pulse_stats["max"] = heart_rate_max
            self.data.pulse_stats["min"] = heart_rate_min
            self.data.set_observations_count(blood_pressure_count, heart_rate_count)
            self.data.finalize(self.verbose,
                blood_pressure_observations, blood_pressure_count, blood_pressure_sums,
                heart_rate_observations, heart_rate_count, heart_rate_sum)

        except Exception as e:
            print("An exception occurred in parsing XML export files.")
            if self.verbose:
                print(e)
            else:
                print("For more detail on the error run in verbose mode.")
            exit(1)