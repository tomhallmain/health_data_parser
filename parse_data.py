import csv
from datetime import datetime, timezone
import json
import numpy as np
import operator
import os
import sys
import traceback
import xml.etree.ElementTree as ET

from labtest import LabTest
from observation import Observation, ObservationVital, CategoryError
from report import Report
from result import get_interpretation_keys, get_interpretation_text
from generate_diagnostic_report_files import generate_diagnostic_report_files
from graph import PulseStatsGraph
from units import VitalSignCategory, HeightUnit, WeightUnit, TemperatureUnit, convert

help_text = """
Usage:

   $ python parse_data.py path/to/apple_health_export ${args}

    --only_clinical_records
        Do not attempt to parse default XML export files (much faster)

    --start_year=[int] 
        Exclude results from before a certain year

    --skip_long_values
        Full diagnostic report data may be mixed in as a single observation with 
        health data integrated to Apple Health. Exclude these observations with
        excessively long result output using this flag.

    --skip_dates
        Skip dates using a comma-separated list of format YYYY-MM-DD,YYYY-MM-DD

    --filter_abnormal_in_range
        By default abnormal results are collected when a range result is within 15% 
        of the higher or lower ends of a range. Exclude these types of results with
        this flag.

    --in_range_abnormal_boundary=[float]
        By default abnormal results are collected when a range result is within 15%
        of the higher or lower ends of a range. Change that percentage with this flag.

    --extra_observations=path/to/observations_data.csv
        Fill out the sample CSV with data and pass the location at runtime to
        include data not hooked up to your Apple Health in the output

    --report_highlight_abnormal_results=[bool]
        By default abnormal results are highlighted in observations tables on the 
        report. To turn this off, set this value to False.

    --birth_date=[YYYY-MM-DD]
        Subject birth date for reporting purposes, if not found in export XML.

    --json_add_all_vitals
        If using a wearable, a lot of vital sign observations may be accumulated.
        By default these are not added to the JSON output - pass to add these.

    -h, --help
        Print this help text

    -v, --verbose
        Run in verbose mode
"""


### TODO apply ranges found in other observation dates to same codes if not already verified
### TODO get weighted severity of abnormality by code



## SETUP



if len(sys.argv) < 2:
    print(help_text)
    exit()

data_export_dir = sys.argv[1]

if data_export_dir == None or data_export_dir == "":
    print("Missing Apple Health data export directory path.")
    print(help_text)
    exit(1)
elif not os.path.exists(data_export_dir) or not os.path.isdir(data_export_dir):
    print("Apple Health data export directory path \"" + data_export_dir+ "\" is invalid.")
    print(help_text)
    exit(1)

all_data_csv = data_export_dir + "/observations.csv"
all_data_json = data_export_dir + "/observations.json"
abnormal_results_output_csv = data_export_dir + "/abnormal_results.csv"
abnormal_results_by_interp_csv = data_export_dir + "/abnormal_results_by_interpretation.csv"
abnormal_results_by_code_text = data_export_dir + "/abnormal_results_by_code.txt"
export_xml = data_export_dir + "/export.xml"
export_cda_xml = data_export_dir + "/export_cda.xml"
base_dir = data_export_dir + "/clinical-records"

if not os.path.exists(base_dir) or len(os.listdir(base_dir)) == 0:
    print("Folder \"clinical-records\" not found in export folder \"" + data_export_dir + "\".")
    print("Ensure data has been connected to Apple Health before export.")
    exit(1)

COMMANDS = sys.argv[2:]
start_year = None
verbose = False
skip_long_values = False
skip_in_range_abnormal_results = False
in_range_abnormal_boundary = 0.15
skip_dates = []
report_highlight_abnormal_results = True
only_clinical_records = False
extra_observations_csv = None
json_add_all_vitals = False
subject = {}
normal_height_unit = HeightUnit.CM
normal_weight_unit = WeightUnit.LB
normal_temperature_unit = TemperatureUnit.C

def verbose_print(text: str):
    if verbose:
        print(text)

def get_age(birth_date):
    today = datetime.today()
    age = today.year - birth_date.year
    test_date = datetime(today.year, birth_date.month, birth_date.day, 0, 0, 0)
    age += round((today - test_date).days / 365, 1)
    return age



## VALIDATE AND SET FROM COMMANDS


if len(COMMANDS) > 0:
    for command in COMMANDS:
        if command == "-h" or command == "--help":
            print(help_text)
            exit()
        elif command == "-v" or command == "--verbose":
            verbose = True

        elif command[:23] == "--only_clinical_records":
            only_clinical_records = True
        
        elif command[:13] == "--start_year=":
            try:
                year = command[13:]
                start_year = int(year)
                print("Excluding results from before start year " + year)
            except Exception:
                print("\"" + year + "\" is not a valid year.")
                exit(1)
        
        elif command == "--skip_long_values":
            skip_long_values = True
            print("Skipping observations with result values over 150 characters long")
        
        elif command[:13] == "--skip_dates=":
            try:
                skip_dates = command[13:].split(",")
                
                for date in skip_dates:
                    test = datetime.fromisoformat(date)
            except Exception:
                print("\"" + command[13:] + "\" is not a valid list of dates in format YYYY-MM-DD.")
                exit(1)
            if len(skip_dates) > 0:
                print("Skipping dates: " + str(skip_dates))
        
        elif command[:36] == "--report_highlight_abnormal_results=":
            highlight_string = command[36:]
            if highlight_string == "FALSE" or highlight_string == "False" or highlight_string == "false":
                report_highlight_abnormal_results = False
            elif not highlight_string == "TRUE" and not highlight_string == "True" and not highlight_string == "true":
                print("Found report_highlight_abnormal_results \"" + highlight_string + "\" was not a boolean value.")
        
        elif command == "--filter_abnormal_in_range":
            skip_in_range_abnormal_results = True
            print("Excluding abnormal results within allowed quantitative ranges")
        
        elif command[:29] == "--in_range_abnormal_boundary=":
            try:
                abnormal_boundary = command[29:]
                in_range_abnormal_boundary = float(abnormal_boundary)
                if abs(in_range_abnormal_boundary) >= 0.5:
                    raise ValueError("Absolute value of boundary must be less than 0.5")
                print("In range abnormal boundary set to " + abnormal_boundary)
            except Exception:
                print("\"" + abnormal_boundary + "\" is not a valid decimal-formatted percentage")
                exit(1)

        elif command[:21] == "--extra_observations=":
            extra_observations_csv = command[21:]

        elif command[:13] == "--birth_date=":
            birth_date_str = command[13:]
            try:
                birth_date = datetime.fromisoformat(birth_date_str)
            except Exception:
                print("\"" + command[13:] + "\" is not a valid list of date in format YYYY-MM-DD.")
                exit(1)
            
            subject["birthDate"] = birth_date_str
            subject["age"] = get_age(birth_date)

        elif command[:21] == "--json_add_all_vitals":
            json_add_all_vitals = True




## PROCESS CUSTOM DATA FILES


use_custom_data = extra_observations_csv != None
custom_data_files = []

if use_custom_data:
    if not generate_diagnostic_report_files(extra_observations_csv, base_dir, verbose, False):
        exit(1)





## PROCESS APPLE HEALTH XML DATA


datetime_format = "%Y-%m-%d %X %z"
blood_pressure_stats_preset = False
blood_pressure_stats = {
    "vital": VitalSignCategory.BLOOD_PRESSURE.value, "count": 0, 
    "labels": ["BP Systolic", "BP Diastolic"],
    "sum": [0, 0],
    "avg": [None, None],
    "max": [None, None],
    "min": [None, None],
    "mostRecent": [None, None],
    "unit": "mmHg",
    "list": []}
pulse_stats_preset = False
pulse_stats = {"vital": VitalSignCategory.PULSE.value, "count": 0, "sum": 0, "avg": None, "max": None, "min": None, "mostRecent": None, "unit": None, "list": []}
temperature_stats_preset = False
temperature_stats = {"vital": VitalSignCategory.TEMPERATURE.value, "count": 0, "sum": 0, "avg": None, "max": None, "min": None, "mostRecent": None, "unit": None, "list": []}
xml_vitals_observations_count = 0


if only_clinical_records:
    verbose_print("Skipping all data present not in clinical-records folder.")
else:
    if os.path.exists(export_xml):
        print("Parsing XML...")
        try:
            tree = ET.parse(export_xml)
            root = tree.getroot()
            me = root.find("Me").attrib
            if "birthDate" not in subject:
                birth_date_str = me["HKCharacteristicTypeIdentifierDateOfBirth"]
                birth_date = datetime.fromisoformat(birth_date_str)
                subject["birthDate"] = birth_date_str
                subject["age"] = get_age(birth_date)
            subject["sex"] = me["HKCharacteristicTypeIdentifierBiologicalSex"].replace("HKBiologicalSex", "")
            subject["bloodType"] = me["HKCharacteristicTypeIdentifierBloodType"].replace("HKBloodType", "")

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
            temperature_observations = []
            temperature_sum = 0
            temperature_count = 0
            temperature_max = None
            temperature_min = None

            for correlation in root.iter("Correlation"):
                if not "type" in correlation.attrib:
                    continue

                if correlation.attrib["type"] == "HKCorrelationTypeIdentifierBloodPressure":
                    blood_pressure_obs = {}
                    systolic = None
                    diastolic = None
                    
                    for rec in correlation.iter("Record"):
                        if rec.attrib["type"] == "HKQuantityTypeIdentifierBloodPressureSystolic":
                            systolic = int(rec.attrib["value"])
                        elif rec.attrib["type"] == "HKQuantityTypeIdentifierBloodPressureDiastolic":
                            diastolic = int(rec.attrib["value"])
                    
                    if systolic == None or diastolic == None:
                        continue

                    blood_pressure_obs["value"] = [systolic, diastolic]
                    blood_pressure_obs["time"] = datetime.strptime(rec.attrib["startDate"], datetime_format)
                    blood_pressure_observations.append(blood_pressure_obs)
                    blood_pressure_count += 1
                    blood_pressure_sums[0] += systolic
                    blood_pressure_sums[1] += diastolic
                    
                    if blood_pressure_max[0] == None:
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
                if not "type" in rec.attrib:
                    continue

                rec_type = rec.attrib["type"]

                if rec_type == "HKQuantityTypeIdentifierHeartRate":
                    heart_rate_obs = {}
                    value = float(rec.attrib["value"])
                    metadataentry = rec.find("MetadataEntry")
                    motion_data_found = False

                    if metadataentry != None and "key" in metadataentry.attrib and metadataentry.attrib["key"] == "HKMetadataKeyHeartRateMotionContext":
                        heart_rate_obs["motion"] = int(metadataentry.attrib["value"])
                        motion_data_found = True
                    else:
                        heart_rate_obs["motion"] = 0

                    if value > 155:
                        continue
                    elif value > 140 and heart_rate_obs["motion"] != 0:
                        continue
                    elif value < 35:
                        continue
                    
                    heart_rate_obs["value"] = value
                    heart_rate_obs["time"] = datetime.strptime(rec.attrib["startDate"], datetime_format)
                    heart_rate_observations.append(heart_rate_obs)
                    heart_rate_count += 1
                    heart_rate_sum += value
                    heart_rate_most_recent = value
                    if heart_rate_max == None:
                        heart_rate_max = value
                        heart_rate_min = value
                    elif value > heart_rate_max:
                        heart_rate_max = value
                    elif value < heart_rate_min:
                        heart_rate_min = value
                
                elif rec_type == "HKQuantityTypeIdentifierBodyTemperature":
                    temp_obs = {}
                    value = float(rec.attrib["value"])

                    if "unit" in rec.attrib:
                        try:
                            value = TemperatureUnit.from_value(rec.attrib["unit"]).convertTo(normal_temperature_unit, value)
                        except Exception as e:
                            verbose_print(e)
                            verbose_print(rec.attrib["unit"])
                            continue
                    else:
                        try:
                            value = TemperatureUnit.from_value("F" if obs.value > 45 else "C").convertTo(normal_temperature_unit, value)
                        except Exception as e:
                            verbose_print(e)
                            continue

                    temp_obs["value"] = value
                    temp_obs["time"] = datetime.strptime(rec.attrib["startDate"], datetime_format)
                    temperature_observations.append(temp_obs)
                    temperature_count += 1
                    temperature_sum += value
                    if temperature_max == None:
                        temperature_max = value
                        temperature_min = value
                    elif value > temperature_max:
                        temperature_max = value
                    elif value < temperature_min:
                        temperature_min = value
                

            blood_pressure_stats["list"] = blood_pressure_observations
            blood_pressure_stats["max"] = blood_pressure_max
            blood_pressure_stats["min"] = blood_pressure_min
            pulse_stats["list"] = heart_rate_observations
            pulse_stats["max"] = heart_rate_max
            pulse_stats["min"] = heart_rate_min
            temperature_stats["list"] = temperature_observations
            temperature_stats["max"] = temperature_max
            temperature_stats["min"] = temperature_min
            xml_vitals_observations_count = heart_rate_count + temperature_count + blood_pressure_count

            if len(blood_pressure_stats["list"]) > 0:
                blood_pressure_stats_preset = True
                verbose_print("Found " + str(len(blood_pressure_observations)) + " heart rate observations in XML data.")
                blood_pressure_stats["count"] = blood_pressure_count
                blood_pressure_stats["sum"] = blood_pressure_sums
            if len(pulse_stats["list"]) > 0:
                pulse_stats_preset = True
                verbose_print("Found " + str(len(heart_rate_observations)) + " heart rate observations in XML data.")
                pulse_stats["count"] = heart_rate_count
                pulse_stats["sum"] = heart_rate_sum
            if len(temperature_stats["list"]) > 0:
                temperature_stats_preset = True
                verbose_print("Found " + str(len(temperature_observations)) + " temperature observations in XML data.")
                temperature_stats["count"] = temperature_count
                temperature_stats["sum"] = temperature_sum

        except Exception as e:
            print("An exception occurred in parsing XML export files. For more detail on the error run in verbose mode.")
            verbose_print(e)
            exit()
    else:
        print("WARNING: export.xml or export_cda.xml not found in export directory.")





## PROCESS CLINICAL RECORDS JSON DATA



print("Parsing clinical-records JSON...")

health_files = os.listdir(base_dir)
observations = {}
observation_dates = []
reference_dates = []
observation_codes = {}
observation_code_ids = {}
tests = []
date_codes = {}
abnormal_results = {}
abnormal_result_dates = []
observations_vital_signs = {}
category_vital_signs = "Vital Signs"
vital_sign_categories = [member.value for name, member in VitalSignCategory.__members__.items()]
vital_sign_categories.insert(0, category_vital_signs)
disallowed_codes = ["NARRATIVE", "REQUEST PROBLEM"]


def handle_vital_sign_category_observation(data: dict, obs_id: str, tests: list, start_year: int,
        skip_long_values: bool, skip_in_range_abnormal_results: bool, in_range_abnormal_boundary: float):
    obs_v = None

    try:
        obs_v = ObservationVital(data, obs_id, tests, date_codes,
            start_year, skip_long_values, skip_in_range_abnormal_results, 
            in_range_abnormal_boundary)
    except ValueError as e:
        verbose_print(e)
        pass
    except AssertionError as e:
        verbose_print(e)
    except Exception as e:
        verbose_print("Exception encountered in gathering data from observation:")
        verbose_print(obs_id)
        if obs_v != None and obs_v.datecode != None:
            verbose_print(obs_v.datecode)
        verbose_print(traceback.print_exc())
        raise e
    
    if obs_v != None:
        force_presence = str(obs_v.observation_complete)

    if obs_v == None or not obs_v.observation_complete:
        return
    
    if obs_v.date != None and obs_v.date in skip_dates:
        raise Exception("Skipping observation on date " + obs_v.date)

    if obs_v.category == category_vital_signs:
        for category in list(VitalSignCategory):
            if category.matches(obs_v.code):
                obs_v.vital_sign_category = category
                break

        if obs_v.vital_sign_category == None:
            raise AssertionError("Vital sign observation category not identified: " + obs_v.category)
    else:
        for category in list(VitalSignCategory):
            if category.matches(obs_v.category):
                obs_v.vital_sign_category = category
                break

        if obs_v.vital_sign_category == None:
            raise AssertionError("Vital sign observation category not identified: " + obs_v.category)

    if obs_v.date in observations_vital_signs:
        this_date_observations = observations_vital_signs[obs_v.date]
    else:
        this_date_observations = []

    this_date_observations.append(obs_v)
    observations_vital_signs[obs_v.date] = this_date_observations
    
    verbose_print("Vital sign observation recorded for " + obs_v.code + " on " + obs_v.date)



def process_observation(data: dict, obs_id: str):
    obs = None

    try:
        obs = Observation(data, obs_id, tests, date_codes,
            start_year, skip_long_values, skip_in_range_abnormal_results, 
            in_range_abnormal_boundary, vital_sign_categories, disallowed_codes)
    except ValueError as e:
        pass
    except CategoryError as e:
        verbose_print(e)
        handle_vital_sign_category_observation(data, obs_id, tests, start_year,
            skip_long_values, skip_in_range_abnormal_results, in_range_abnormal_boundary)
        return
    except AssertionError as e:
        verbose_print(e)
    except Exception as e:
        verbose_print("Exception encountered in gathering data from observation:")
        verbose_print(obs_id)
        if obs != None and obs.datecode != None:
            verbose_print(obs.datecode)
        verbose_print(traceback.print_exc())
        raise e

    if obs == None or not obs.observation_complete:
        return

    if obs.date != None and obs.date in skip_dates:
        raise Exception("Skipping observation on date " + obs.date)

    observations[obs_id] = obs

    if obs.is_seen_test:
        tests[obs.test_index] = obs.test
    else:
        tests.append(obs.test)

    if obs.primary_code_id not in observation_codes:
        observation_codes[obs.primary_code_id] = obs.code
    
    if obs.code not in observation_code_ids:
        observation_code_ids[obs.code] = []

    code_ids = observation_code_ids[obs.code]
    
    if not obs.primary_code_id in code_ids:
        code_ids.append(obs.primary_code_id)
        observation_code_ids[obs.code] = code_ids

    if obs.date != None:
        if obs.date not in observation_dates:
            observation_dates.append(obs.date)
        if obs.has_reference and obs.date not in reference_dates:
            reference_dates.append(obs.date)

    date_codes[obs.datecode] = obs_id

    if obs.has_reference and obs.result.is_abnormal_result:
        if obs.primary_code_id not in abnormal_results:
            abnormal_results[obs.primary_code_id] = []
        results = abnormal_results[obs.primary_code_id]
        results.append(obs)
        abnormal_results[obs.primary_code_id] = results
        if obs.date not in abnormal_result_dates:
            abnormal_result_dates.append(obs.date)
    
    verbose_print("Observation recorded for " + obs.code + " on " + obs.date)


for f in health_files:
    file_category = f[0:(f.index("-"))]
    f_addr = base_dir + "/" + f

    ## Get data from Observation files

    if file_category == "Observation":
        file_data = json.load(open(f_addr))

        if not "name" in subject and "subject" in file_data:
            subject_data = file_data["subject"]
            if subject_data != None and "display" in subject_data and subject_data["display"] != None:
                subject["name"] = subject_data["display"]
                verbose_print("Identified subject: " + subject["name"])

        try:
            process_observation(file_data, f)
        except Exception as e:
            verbose_print(e)
            continue

    ## Get data from Diagnostic Report type files

    elif file_category == "DiagnosticReport":
        if "-CUSTOM" in f_addr:
            use_custom_data = True
            custom_data_files.append(f_addr)

        file_data = json.load(open(f_addr))
        data_category = file_data["category"]["coding"][0]["code"]

        if data_category not in ["Lab", "LAB"]:
            continue

        ## Some Diagnostic Report files have multiple results contained

        if "contained" in file_data:
            i = 0
            for observation in file_data["contained"]:
                try:
                    process_observation(observation, f + "[" + str(i) + "]")
                except Exception as e:
                    verbose_print(e)
                    continue
                i += 1
        else:
            try:
                process_observation(file_data, f)
            except Exception as e:
                verbose_print(e)
                continue


observation_dates.sort()
observation_dates.reverse()





## APPLY RANGES TO CLINICAL RECORDS RESULTS


ranges = {}

if len(reference_dates) > 0:
    verbose_print("\nConsolidating ranges and validating all results where ranges apply are tested for abnormality...\n")
    
    # Construct ranges object
    for code in sorted(observation_code_ids):
        range_found = False
        for date in observation_dates:
            if range_found:
                break
            for code_id in observation_code_ids[code]:
                datecode = date + code_id
                if datecode in date_codes:
                    observation = observations[date_codes[datecode]]
                    if date in reference_dates and observation.has_reference:
                        ranges[code] = observation.result.range_text
                        range_found = True
                        break

    for code in sorted(observation_code_ids):
        if not code in ranges:
            continue
        
        code_range = ranges[code]
        range_list = [{"text": code_range}]

        for date in observation_dates:
            for code_id in observation_code_ids[code]:
                datecode = date + code_id
                if datecode in date_codes:
                    obs = observations[date_codes[datecode]]
                    if not obs.has_reference:
                        verbose_print("Found missing reference range for code " + code 
                            + " on " + date + " - attempting to apply range from other results")
                        obs.set_reference(skip_in_range_abnormal_results, in_range_abnormal_boundary, range_list, obs.unit, True)

                        if obs.has_reference:
                            if obs.date not in reference_dates:
                                reference_dates.append(obs.date)

                            if obs.result.is_abnormal_result:
                                if obs.primary_code_id not in abnormal_results:
                                    abnormal_results[obs.primary_code_id] = []
                                results = abnormal_results[obs.primary_code_id]
                                results.append(obs)
                                abnormal_results[obs.primary_code_id] = results
                                if obs.date not in abnormal_result_dates:
                                    abnormal_result_dates.append(obs.date)


abnormal_result_dates.sort()
abnormal_result_dates.reverse()
reference_dates.sort()




## COMPILE VITAL SIGNS DATA




verbose_print("\nCompiling vital signs data if present...\n")

respiration_stats = {"vital": VitalSignCategory.RESPIRATION.value, "count": 0, "sum": 0, "avg": None, "max": None, "min": None, "mostRecent": None, "unit": None, "list": []}
height_stats = {"vital": VitalSignCategory.HEIGHT.value, "count": 0, "sum": 0, "avg": None, "max": None, "min": None, "mostRecent": None, "unit": normal_height_unit.name.lower(), "list": []}
weight_stats = {"vital": VitalSignCategory.WEIGHT.value, "count": 0, "sum": 0, "avg": None, "max": None, "min": None, "mostRecent": None, "unit": normal_weight_unit.name.lower(), "list": []}
bmi_stats = {"vital": "BMI", "count": 0, "sum": 0, "avg": None, "max": None, "min": None, "mostRecent": None, "unit": "BMI", "list": []}

def calculate_bmi(normalized_height: float, normalized_weight: float):
    height_meters = convert(HeightUnit.M, normal_height_unit, normalized_height)
    weight_kilos = convert(WeightUnit.KG, normal_weight_unit, normalized_weight)
    bmi = round(weight_kilos / (height_meters ** 2), 2)
    verbose_print("Calculated BMI " + str(bmi) + " (" + str(round(weight_kilos, 2)) + " kg / " + str(round(height_meters, 2)) + " m^2)")
    return bmi

current_tzinfo = timezone(datetime.now().astimezone().tzinfo.utcoffset(None))

def set_stats(stats: dict, time, value):
    if time == None:
        stats["list"].append(value)
    else:
        stats["list"].append({"time": time, "value": value})
    stats["count"] += 1
    if type(value) == list:
        for i in range(len(value)):
            c_value = value[i]
            stats["sum"][i] += c_value
            if stats["max"][i] == None:
                stats["max"][i] = c_value
                stats["min"][i] = c_value
            elif stats["max"][i] < c_value:
                stats["max"][i] = c_value
            elif stats["min"][i] > c_value:
                stats["min"][i] = c_value
    else:
        stats["sum"] += value
        if stats["max"] == None:
            stats["max"] = value
            stats["min"] = value
        elif stats["max"] < value:
            stats["max"] = value
        elif stats["min"] > value:
            stats["min"] = value

for vitals_date in sorted(observations_vital_signs.keys()):
    vitals_datetime = datetime.fromisoformat(vitals_date)
    vitals_datetime = vitals_datetime.replace(tzinfo=current_tzinfo)
    this_date_observations = observations_vital_signs[vitals_date]
    this_date_height = None
    this_date_height_unit = None
    normalized_height = None
    this_date_weight = None
    this_date_weight_unit = None
    normalized_weight = None
    try:
        for obs in this_date_observations:
            if obs.vital_sign_category is VitalSignCategory.HEIGHT:
                this_date_height = obs.value
                this_date_height_unit = obs.unit
                continue
            elif obs.vital_sign_category is VitalSignCategory.WEIGHT:
                this_date_weight = obs.value
                this_date_weight_unit = obs.unit
                continue
            
            if obs.value == None or obs.unit == None:
                if obs.vital_sign_category is VitalSignCategory.TEMPERATURE and obs.value != None:
                    obs.unit = "F" if obs.value > 45 else "C"
                else:
                    print("Skipping obs on date " + vitals_date + " of category " + str(obs.vital_sign_category) + " because value or unit was None")
                    continue
            
            if obs.vital_sign_category is VitalSignCategory.BLOOD_PRESSURE:
                blood_pressure_stats["unit"] = obs.unit
                set_stats(blood_pressure_stats, vitals_datetime, [obs.value, obs.value2])
            elif obs.vital_sign_category is VitalSignCategory.PULSE:
                pulse_stats["unit"] = obs.unit
                set_stats(pulse_stats, vitals_datetime, obs.value)
                pulse_stats["list"][-1]["motion"] = 0 # Assume heart rate observations in clinical-records are not in motion
            elif obs.vital_sign_category is VitalSignCategory.RESPIRATION:
                respiration_stats["unit"] = obs.unit
                set_stats(respiration_stats, vitals_datetime, obs.value)
            elif obs.vital_sign_category is VitalSignCategory.TEMPERATURE:
                this_temp_unit = TemperatureUnit.from_value(obs.unit)
                normalized_temperature = round(this_temp_unit.convertTo(normal_temperature_unit, obs.value), 2)
                set_stats(temperature_stats, vitals_datetime, normalized_temperature)
                temperature_stats["unit"] = obs.unit

        if this_date_height != None and this_date_height_unit != None:
            normalized_height = convert(normal_height_unit, HeightUnit.from_value(this_date_height_unit), this_date_height)
            set_stats(height_stats, vitals_datetime, normalized_height)
        if this_date_weight != None and this_date_weight_unit != None:
            normalized_weight = convert(normal_weight_unit, WeightUnit.from_value(this_date_weight_unit), this_date_weight)
            set_stats(weight_stats, vitals_datetime, normalized_weight)
        if normalized_height == None or normalized_weight == None:
            continue
        bmi = calculate_bmi(normalized_height, normalized_weight)
        set_stats(bmi_stats, vitals_datetime, bmi)
    except Exception as e:
        verbose_print(e)


for stats_obj in [height_stats, weight_stats, bmi_stats, temperature_stats, pulse_stats, respiration_stats, blood_pressure_stats]:
    try:
        stats_obj["list"] = sorted(stats_obj["list"], key=operator.itemgetter("time"))
    except Exception:
        print("WARNING: Encountered a problem comparing timezones between XML and clinical records JSON data."
            + " Vital signs output that relies on sorting may not be calculated correctly.")
        tzinfos = []
        for obs in stats_obj["list"]:
            date = obs["time"]
            if not date.tzinfo in tzinfos:
                verbose_print("Found new tzinfo for date " + str(date))
                verbose_print(date.tzinfo)
                tzinfos.append(date.tzinfo)
    
    if stats_obj["count"] > 0:
        stats_obj["mostRecent"] = stats_obj["list"][-1]
        if stats_obj["mostRecent"]["value"] == None:
            verbose_print("Stats collection for vital " + stats_obj["vital"] + " failed.")
        elif type(stats_obj["mostRecent"]["value"]) == list:
            stats_obj["stDev"] = []
            for i in range(len(stats_obj["mostRecent"])):
                avg = stats_obj["sum"][i] / stats_obj["count"]
                stats_obj["avg"][i] = avg
                sum_sq_diffs = 0
                for obs in stats_obj["list"]:
                    sum_sq_diffs += (obs["value"][i] - avg) ** 2
                stats_obj["stDev"].append((sum_sq_diffs / stats_obj["count"]) ** (1/2))
            del stats_obj["sum"]
        else:
            avg = stats_obj["sum"] / stats_obj["count"]
            stats_obj["avg"] = avg
            del stats_obj["sum"]
            sum_sq_diffs = 0
            for obs in stats_obj["list"]:
                sum_sq_diffs += (obs["value"] - avg) ** 2
            stats_obj["stDev"] = (sum_sq_diffs / stats_obj["count"]) ** (1/2)
        if verbose:
            print("Found stats for vital sign: " + stats_obj["vital"])
            print(str(stats_obj["count"]) + " unique observations with average value " + str(stats_obj["avg"]) 
                + " and standard deviation " + str(stats_obj["stDev"]))



## PULSE GRAPH CALCS


pulse_stats_graph = None
pulse_stats["graphEligible"] = pulse_stats["count"] > 10000

if pulse_stats["graphEligible"]:
    pulse_stats_graph = PulseStatsGraph(pulse_stats)
    pulse_stats_graph.save_graph_images(data_export_dir)



## WRITE DATA TO FILES



verbose_print("\nProcessing complete, writing data to files...\n")
total_abnormal_results = 0
abnormal_result_interpretations_by_code = {}

if len(observations) > 0:
    if use_custom_data:
        print("\nThe compiled information includes some custom data not exported from Apple Health:")
        for filename in custom_data_files:
            print(filename)
        print("")

    if len(abnormal_results) > 0:

        ## Log abnormal results by code then date

        try:
            with open(abnormal_results_by_code_text, "w") as textfile:
                line = "|----- Laboratory Abnormal Results from Apple Health Data by Code -----|"
                verbose_print("\n")
                verbose_print(line)
                verbose_print("\n")

                textfile.write(line)
                textfile.write("\n\n")

                for code in sorted(observation_code_ids):
                    for code_id in observation_code_ids[code]:
                        if code_id in abnormal_results:
                            results = abnormal_results[code_id]
                            line = "Abnormal results found for code " + code + ":"
                            verbose_print(line)
                            textfile.write(line)
                            textfile.write("\n")

                            for observation in sorted(results, key=operator.attrgetter("date")):
                                total_abnormal_results += 1
                                interpretation = observation.result.get_result_interpretation_text()
                                value_string = observation.value_string
                                if observation.result.is_range_type:
                                    line = observation.date + ": " + interpretation + " - observed " + value_string + " - range " + observation.result.range
                                else:
                                    line = observation.date + ": " + interpretation + " - observed " + value_string
                                verbose_print(line)
                                textfile.write(line)
                                textfile.write("\n")

                            verbose_print("")
                            textfile.write("\n")

            print("Abnormal laboratory results data from Apple Health saved to " + abnormal_results_by_code_text)

        except Exception as e:
            print("An error occurred in writing abnormal results data.")
            if verbose:
                traceback.print_exc()
            verbose_print(e)


        ## Log abnormal results by interpretation class, code, date

        try:
            with open(abnormal_results_by_interp_csv, "w") as csvfile:
                filewriter = csv.writer(csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)
                interpretation_keys = get_interpretation_keys(skip_in_range_abnormal_results)
                header = ["Laboratory Abnormal Results by Interpretation from Apple Health Data"]
                interpretations = list(map(lambda key: get_interpretation_text(key), interpretation_keys))
                header.extend(interpretations)
                filewriter.writerow(header)

                for code in sorted(observation_code_ids):
                    abnormal_result_found = False
                    row = [code]
                    code_interpretation_keys = []
                    for code_id in observation_code_ids[code]:
                        if code_id in abnormal_results:
                            results = abnormal_results[code_id]
                            abnormal_result_found = True

                            for observation in results:
                                interpretation_key = observation.result.interpretation
                                if interpretation_key not in code_interpretation_keys:
                                    code_interpretation_keys.append(interpretation_key)

                    if abnormal_result_found:
                        code_interpretations = []
                        for interpretation_key in interpretation_keys:
                            if interpretation_key in code_interpretation_keys:
                                row.append(interpretation_key)
                                code_interpretations.append(get_interpretation_text(interpretation_key))
                            else:
                                row.append("")

                        abnormal_result_interpretations_by_code[code] = code_interpretations
                        filewriter.writerow(row)

            print("Abnormal laboratory results data from Apple Health sorted by interpretation saved to " + abnormal_results_by_interp_csv)

        except Exception as e:
            print("An error occurred in writing abnormal results data.")
            if verbose:
                traceback.print_exc()
            verbose_print(e)


        ## Write abnormal results by datecode to spreadsheet

        try:
            with open(abnormal_results_output_csv, "w") as csvfile:
                filewriter = csv.writer(csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)

                header = ["Laboratory Abnormal Results from Apple Health Data"]

                for date in abnormal_result_dates:
                    header.append(date)

                filewriter.writerow(header)

                for code in sorted(observation_code_ids):
                    row = [code]
                    abnormal_result_found = False
                    
                    for date in abnormal_result_dates:
                        date_found = False
                        
                        for code_id in observation_code_ids[code]:
                            if code_id in abnormal_results:
                                abnormal_result_found = True
                                results = abnormal_results[code_id]

                                for observation in results:
                                    if observation.date == date and date + code_id in date_codes:
                                        date_found = True
                                        row.append(observation.value_string + " " + observation.result.interpretation)
                                        break
                                else:
                                    continue

                                break
                        
                        if not date_found:
                            row.append("")

                    if abnormal_result_found:
                        filewriter.writerow(row)

            print("Abnormal laboratory results data from Apple Health saved to " + abnormal_results_output_csv)

        except Exception as e:
            print("An error occurred in writing abnormal results data to CSV.")
            if verbose:
                traceback.print_exc()
            verbose_print(e)

    else:
        print("No abnormal results found from current data")


    ## Write all data by datecode to spreadsheet

    try:
        with open(all_data_csv, "w", encoding="utf-8") as csvfile:
            filewriter = csv.writer(csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)

            header = ["Laboratory Observations from Apple Health Data"]

            for date in observation_dates:
                if date in reference_dates:
                    header.append(date + " range")
                header.append(date + " result")

            filewriter.writerow(header)

            for code in sorted(observation_code_ids):
                row = [code]

                for date in observation_dates:
                    date_found = False

                    for code_id in observation_code_ids[code]:
                        datecode = date + code_id
                        if datecode in date_codes:
                            date_found = True
                            observation = observations[date_codes[datecode]]
                            if date in reference_dates:
                                if observation.has_reference:
                                    row.append(" " + observation.result.range_text) # Excel formats as date without space here
                                else:
                                    row.append("")
                            abnormal_result_tag = " " + observation.result.interpretation if observation.has_reference else ""
                            row.append(observation.value_string + abnormal_result_tag)
                            break
                    
                    if not date_found:
                        row.append("")
                        if date in reference_dates:
                            row.append("")

                filewriter.writerow(row)

        print("Laboratory records data from Apple Health saved to " + all_data_csv)

    except Exception as e:
        print("An error occurred in writing observations data to CSV.")
        if verbose:
            traceback.print_exc()
        verbose_print(e)
        exit(1)


    data = {}

    ## Write simplified observations data to JSON

    try:
        meta = {}
        meta["description"] = "Laboratory Observations from Apple Health Data"
        meta["processTime"] = str(datetime.now())
        meta["observationCount"] = len(observations)
        meta["vitalSignsObservationCount"] = len(observations_vital_signs) + xml_vitals_observations_count
        meta["mostRecentResult"] = observation_dates[0]
        meta["earliestResult"] = observation_dates[-1]
        meta["heartRateMonitoringWearableDetected"] = pulse_stats["graphEligible"]
        data["meta"] = meta

        if meta["vitalSignsObservationCount"] > 0:
            vital_signs = {}
            if json_add_all_vitals:
                data["vitalSigns"] = [temperature_stats, pulse_stats, respiration_stats, 
                    height_stats, weight_stats, bmi_stats, blood_pressure_stats]
            else:
                save_stats_objs = [temperature_stats, pulse_stats, respiration_stats,
                        height_stats, weight_stats, bmi_stats, blood_pressure_stats]
                data["vitalSigns"] = []
                for stats_obj in save_stats_objs:
                    new_obj = dict(stats_obj)
                    del new_obj["list"]
                    if "graph" in new_obj:
                        del new_obj["graph"]
                    data["vitalSigns"].append(new_obj)


        if total_abnormal_results > 0:
            abnormal_results_data = {}
            meta = {}
            meta["codesWithAbnormalResultsCount"] = len(abnormal_results)
            meta["totalAbnormalResultsCount"] = total_abnormal_results
            meta["includesInRangeAbnormalities"] = in_range_abnormal_boundary > 0 and not skip_in_range_abnormal_results
            meta["inRangeAbnormalBoundary"] = in_range_abnormal_boundary
            abnormal_results_data["meta"] = meta
            abnormal_results_data["codesWithAbnormalResults"] = abnormal_result_interpretations_by_code
            data["abnormalResults"] = abnormal_results_data
        
        observations_list = []

        for obs_id in observations:
            observations_list.append(observations[obs_id].to_dict(obs_id, tests))

        observations_list.sort(key=lambda obs: obs.get("date"))
        observations_list.reverse()
        data["observations"] = observations_list

        class DateTimeEncoder(json.JSONEncoder):
            def default(self, z):
                if isinstance(z, datetime):
                    return (datetime.strftime(z, datetime_format))
                else:
                    return super().default(z)

        with open(all_data_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, cls=DateTimeEncoder, ensure_ascii=False, indent=4)

        print("Laboratory records data from Apple Health saved to " + all_data_json)

    except Exception as e:
        print("An error occurred in writing observations data to JSON.")
        if verbose:
            traceback.print_exc()
        verbose_print(e)
        exit(1)

    ## Write observations data to PDF report

    try:
        if not json_add_all_vitals:
            data["vitalSigns"] = save_stats_objs

        report = Report(data_export_dir, subject, data["meta"]["processTime"][:10], 
                verbose, report_highlight_abnormal_results)
        report.create_pdf(data,
                          observations,
                          observation_dates,
                          observation_code_ids,
                          ranges,
                          date_codes,
                          reference_dates,
                          abnormal_results,
                          abnormal_result_dates,
                          pulse_stats_graph)
        print("Results report saved to " + os.path.join(data_export_dir, report.filename))
    except Exception as e:
        print("An error occurred in writing observations data to PDF report.")
        if verbose:
            traceback.print_exc()
        verbose_print(e)
        exit(1)

    if verbose and use_custom_data:
        print("\nThe compiled information includes some custom data not exported from Apple Health:")
        for filename in custom_data_files:
            print(filename)

else:
    print("No relevant laboratory records found in exported Apple Health data")
    exit(1)


