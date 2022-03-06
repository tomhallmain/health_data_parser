import csv
import datetime
from enum import Enum
import json
import operator
import os
import sys
import traceback

from labtest import LabTest
from observation import Observation, ObservationVital, CategoryError
from report import Report
from result import get_interpretation_keys, get_interpretation_text
from generate_diagnostic_report_files import generate_diagnostic_report_files

help_text = """
Usage:

   $ python parse_data.py path/to/apple_health_export ${args}

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

    -h, --help
        Print this help text

    -v, --verbose
        Run in verbose mode
"""


### TODO apply ranges found in other observation dates to same codes if not already verified
### TODO get weighted severity of abnormality by code

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
extra_observations_csv = None


class HeightUnit(Enum):
    CM = 100
    M = 1
    FT = 3.28084
    IN = 39.37008

    def from_value(value: str):
        value = value.upper()
        
        for name, unit in HeightUnit.__members__.items():
            if name == value:
                return unit

        try:
            if value in "INCHES" and "INCHES".index(value) == 0:
                return HeightUnit.IN
            elif value in "FEET" and "FEET".index(value) == 0:
                return HeightUnit.FT
            elif value in "METERS" and "METERS".index(value) == 0:
                return HeightUnit.M
            elif value in "CENTIMETERS" and "CENTIMETERS".index(value) == 0:
                return HeightUnit.CM
        except Exception as e:
            print(e)
            return None

class WeightUnit(Enum):
    G = 1000
    KG = 1
    LB = 2.204623

    def from_value(value: str):
        value = value.upper()
        
        for name, unit in WeightUnit.__members__.items():
            if name == value:
                return unit

        try:
            if value in "POUNDS" and "POUNDS".index(value) == 0:
                return WeightUnit.LB
            elif value == "KILOS":
                return WeightUnit.KG
            elif value in "KILOGRAMS" and "KILOGRAMS".index(value) == 0:
                return WeightUnit.KG
            elif value in "GRAMS" and "GRAMS".index(value) == 0:
                return WeightUnit.G
        except Exception as e:
            print(e)
            return None

class TemperatureUnit(Enum):
    C = 0
    F = 32

    def from_value(value: str):
        value = value.upper()
        value.replace("DEGREES", "").replace("°", "").replace(" ", "")
        
        for name, unit in WeightUnit.__members__.items():
            if name == value:
                return unit

        try:
            if value in "FAHRENHEIT" and "FAHRENHEIT".index(value) == 0:
                return TemperatureUnit.F
            elif value in "CELCIUS" and "CELCIUS".index(value) == 0:
                return TemperatureUnit.C
        except Exception as e:
            print(e)
            return None
    
    def convertTo(self, temperatureUnit, value):
        if self is temperatureUnit:
            return value
        elif self is TemperatureUnit.F:
            return (value - 32) * 5/9
        else:
            return value * 9/5 + 32

def convert(to_unit, from_unit, value: float):
    return value / from_unit.value * to_unit.value

normal_height_unit = HeightUnit.CM
normal_weight_unit = WeightUnit.LB
normal_temperature_unit = TemperatureUnit.C

if len(COMMANDS) > 0:
    for command in COMMANDS:
        if command == "-h" or command == "--help":
            print(help_text)
            exit()
        elif command == "-v" or command == "--verbose":
            verbose = True
        
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
                    ymd = date.split("-")
                    if len(ymd) != 3 or len(ymd[0]) != 4 or len(ymd[1]) != 2 or len(ymd[2]) != 2:
                        raise Exception
            except Exception as e:
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


use_custom_data = extra_observations_csv != None
custom_data_files = []

if use_custom_data:
    if not generate_diagnostic_report_files(extra_observations_csv, base_dir, verbose, False):
        exit(1)

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
subject = None

class VitalSignCategory(Enum):
    HEIGHT = "Height"
    PULSE = "Pulse"
    RESPIRATION = "Respiration"
    SPO2 = "SpO2"
    TEMPERATURE = "Temperature"
    WEIGHT = "Weight"

    def matches(self, string: str):
        return self.value in string or self.name in string or self.name.lower() in string

category_vital_signs = "Vital Signs"
category_height = "Height"
category_pulse = "Pulse"
category_respiration = "Respiration"
category_spo2 = "SpO2"
category_temperature = "Temperature"
category_weight = "Weight"
observations_vital_signs = {}
vital_sign_dates = []
vital_sign_categories = [category_vital_signs, category_height, category_respiration, category_pulse, category_spo2, category_temperature, category_weight]
disallowed_codes = ["NARRATIVE", "REQUEST PROBLEM"]


def verbose_print(text: str):
    if verbose:
        print(text)

def handle_disallowed_category_observation(data: dict, obs_id: str, tests: list, start_year: int,
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
    
    verbose_print("Observation recorded for " + obs_v.code + " on " + obs_v.date)



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
        handle_disallowed_category_observation(data, obs_id, tests, start_year,
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


## Process the exported health data

for f in health_files:
    file_category = f[0:(f.index("-"))]
    f_addr = base_dir + "/" + f

    ## Get data from Observation files

    if file_category == "Observation":
        file_data = json.load(open(f_addr))

        if subject == None and "subject" in file_data:
            subject_data = file_data["subject"]
            if subject_data != None and "display" in subject_data and subject_data["display"] != None:
                subject = subject_data["display"]
                verbose_print("Identified subject: " + subject)

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
abnormal_result_dates.sort()
abnormal_result_dates.reverse()
reference_dates.sort()


## Vital Signs

verbose_print("\nCompiling vital signs data if present...\n")

respiration_stats = {"vital": VitalSignCategory.RESPIRATION.value, "count": 0, "sum": 0, "avg": None, "mostRecent": None, "unit": None, "list": []}
pulse_stats = {"vital": VitalSignCategory.PULSE.value, "count": 0, "sum": 0, "avg": None, "mostRecent": None, "unit": None, "list": []}
temperature_stats = {"vital": VitalSignCategory.TEMPERATURE.value, "count": 0, "sum": 0, "avg": None, "mostRecent": None, "unit": None, "list": []}
height_stats = {"vital": VitalSignCategory.HEIGHT.value, "count": 0, "sum": 0, "avg": None, "mostRecent": None, "unit": normal_height_unit.name.lower(), "list": []}
weight_stats = {"vital": VitalSignCategory.WEIGHT.value, "count": 0, "sum": 0, "avg": None, "mostRecent": None, "unit": normal_weight_unit.name.lower(), "list": []}
bmi_stats = {"vital": "BMI", "count": 0, "sum": 0, "avg": None, "mostRecent": None, "unit": "BMI", "list": []}

def calculate_bmi(normalized_height: float, normalized_weight: float):
    height_meters = convert(HeightUnit.M, normal_height_unit, normalized_height)
    weight_kilos = convert(WeightUnit.KG, normal_weight_unit, normalized_weight)
    bmi = round(weight_kilos / (height_meters ** 2), 2)
    verbose_print("Calculated BMI " + str(bmi) + " (" + str(round(weight_kilos, 2)) + " kg / " + str(round(height_meters, 2)) + " m^2)")
    return bmi

for vitals_date in sorted(observations_vital_signs.keys()):
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
            
            if obs.vital_sign_category is VitalSignCategory.PULSE:
                pulse_stats["list"].append({"date": vitals_date, "value": obs.value})
                pulse_stats["unit"] = obs.unit
                pulse_stats["mostRecent"] = obs.value
                pulse_stats["count"] += 1
                pulse_stats["sum"] += obs.value
            elif obs.vital_sign_category is VitalSignCategory.RESPIRATION:
                respiration_stats["list"].append({"date": vitals_date, "value": obs.value})
                respiration_stats["unit"] = obs.unit
                respiration_stats["mostRecent"] = obs.value
                respiration_stats["count"] += 1
                respiration_stats["sum"] += obs.value
            elif obs.vital_sign_category is VitalSignCategory.TEMPERATURE:
                this_temp_unit = TemperatureUnit.from_value(obs.unit)
                normalized_temperature = round(this_temp_unit.convertTo(normal_temperature_unit, obs.value), 2)
                temperature_stats["list"].append({"date": vitals_date, "value": normalized_temperature})
                temperature_stats["unit"] = obs.unit
                temperature_stats["mostRecent"] = normalized_temperature
                temperature_stats["count"] += 1
                temperature_stats["sum"] += normalized_temperature

        if this_date_height != None and this_date_height_unit != None:
            normalized_height = convert(normal_height_unit, HeightUnit.from_value(this_date_height_unit), this_date_height)
            height_stats["list"].append({"date": vitals_date, "value": normalized_height})
            height_stats["mostRecent"] = normalized_height
            height_stats["count"] += 1
            height_stats["sum"] += normalized_height
        if this_date_weight != None and this_date_weight_unit != None:
            normalized_weight = convert(normal_weight_unit, WeightUnit.from_value(this_date_weight_unit), this_date_weight)
            weight_stats["list"].append({"date": vitals_date, "value": normalized_weight})
            weight_stats["mostRecent"] = normalized_weight
            weight_stats["count"] += 1
            weight_stats["sum"] += normalized_weight
        if normalized_height == None or normalized_weight == None:
            continue
        bmi = calculate_bmi(normalized_height, normalized_weight)
        bmi_stats["list"].append({"date": vitals_date, "value": bmi})
        bmi_stats["mostRecent"] = bmi
        bmi_stats["count"] += 1
        bmi_stats["sum"] += bmi
    except Exception as e:
        verbose_print(e)


for stats_obj in [height_stats, weight_stats, bmi_stats, temperature_stats, pulse_stats, respiration_stats]:
    if stats_obj["count"] > 0:
        avg = stats_obj["sum"] / stats_obj["count"]
        stats_obj["avg"] = avg
        del stats_obj["sum"]
        sum_sq_diffs = 0
        for obs in stats_obj["list"]:
            sum_sq_diffs += (obs["value"] - avg) ** 2
        stats_obj["stDev"] = (sum_sq_diffs / stats_obj["count"]) ** (1/2)
        if verbose:
            print("Found stats for vital sign: " + stats_obj["vital"])
            print(str(stats_obj["count"]) + " unique dates with average value " + str(stats_obj["avg"]) 
                + " and standard deviation " + str(stats_obj["stDev"]))

## Write the data to files

verbose_print("\nProcessing complete, writing data to files...\n")
total_abnormal_results = 0
abnormal_result_interpretations_by_code = {}

if len(observations) > 0:
    if use_custom_data:
        print("The compiled information includes some custom data not exported from Apple Health:")
        for filename in custom_data_files:
            print(filename)
    
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
        meta["processTime"] = str(datetime.datetime.now())
        meta["observationCount"] = len(observations)
        meta["vitalSignsObservationCount"] = len(observations_vital_signs)
        meta["mostRecentResult"] = observation_dates[0]
        meta["earliestResult"] = observation_dates[-1]
        data["meta"] = meta

        if meta["vitalSignsObservationCount"] > 0:
            vital_signs = {}
            data["vitalSigns"] = [temperature_stats, pulse_stats, 
                respiration_stats, height_stats, weight_stats, bmi_stats]


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

        with open(all_data_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print("Laboratory records data from Apple Health saved to " + all_data_json)

    except Exception as e:
        print("An error occurred in writing observations data to JSON.")
        if verbose:
            traceback.print_exc()
        verbose_print(e)
        exit(1)

    ## Write observations data to PDF report

    try:
        report = Report(data_export_dir, subject, data, verbose, report_highlight_abnormal_results)
        report.create_pdf(data,
                          observations,
                          observation_dates,
                          observation_code_ids,
                          date_codes,
                          reference_dates,
                          abnormal_results,
                          abnormal_result_dates)
        print("Results report saved to " + report.filename)
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


