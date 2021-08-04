import csv
import json
import operator
import os
import sys

from labtest import LabTest
from observation import Observation

help_text = """
Usage:

   $ python parse_data.py path/to/apple_health_export ${args}

    --start_year=${year} 
        Exclude results from before a certain year

    -v, --verbose
        Run in verbose mode
"""

if len(sys.argv) < 2:
    print(help_text)
    exit()

base_dir = sys.argv[1]

if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
    print("Apple Health data export directory path provided is invalid.")
    print(help_text)
    exit(1)

all_data_output_file = base_dir + "/observations.csv"
abnormal_results_output_csv = base_dir + "/abnormal_results.csv"
abnormal_results_output_text = base_dir + "/abnormal_results_by_code.txt"
base_dir = base_dir + "/clinical-records"

if not os.path.exists(base_dir) or len(os.listdir(base_dir)) == 0:
    print("Clinical records not found in export folder provided.")
    print("Ensure data has been connected to Apple Health before export.")
    exit(1)

COMMANDS = sys.argv[2:]
start_year = None
verbose = False

if len(COMMANDS) > 0:
    for command in COMMANDS:
        if command == "-v" or command == "--verbose":
            verbose = True
        elif command[0:13] == "--start_year=":
            try:
                year = command[13:]
                start_year = int(year)
                print("Excluding results from before start year " + year)
            except Exception:
                print("\"" + year + "\" is not a valid year")


health_files = os.listdir(base_dir)
disallowed_categories = ["Vital Signs", "Height", "Weight", "Pulse", "SpO2"]
disallowed_codes = ["NARRATIVE", "REQUEST PROBLEM"]
observations = {}
observation_dates = []
observation_codes = {}
observation_code_ids = {}
tests = []
date_codes = {}
abnormal_results = {}
abnormal_result_dates = []


def verbose_print(text):
    if verbose:
        print(text)

def process_observation(data, obs_id):
    obs = None
    
    try:
        obs = Observation(data, obs_id, tests, date_codes,
            start_year, disallowed_categories, disallowed_codes)

    except ValueError as e:
        pass
    except AssertionError as e:
        verbose_print(e)
    except Exception as e:
        verbose_print("Exception encountered in gathering data from observation:")
        verbose_print(obs_id)
        if obs != None:
            verbose_print(obs)
        raise e

    if obs == None or not obs.observation_complete:
        return

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

    if obs.date != None and obs.date not in observation_dates:
        observation_dates.append(obs.date)

    date_codes[obs.datecode] = obs_id

    if obs.has_result and obs.result.is_abnormal_result:
        if obs.primary_code_id not in abnormal_results:
            abnormal_results[obs.primary_code_id] = []
        results = abnormal_results[obs.primary_code_id]
        results.append(obs)
        abnormal_results[obs.primary_code_id] = results
        if obs.date not in abnormal_result_dates:
            abnormal_result_dates.append(obs.date)
    
    verbose_print(obs)


for f in health_files:
    file_category = f[0:(f.index("-"))]
    f_addr = base_dir + "/" + f

    ## Get data from Observation files

    if file_category == "Observation":
        file_data = json.load(open(f_addr))
        try:
            process_observation(file_data, f)
        except Exception as e:
            verbose_print(e)
            continue

    ## Get data from Diagnostic Report type files

    elif file_category == "DiagnosticReport":
        file_data = json.load(open(f_addr))
        data_category = file_data["category"]["coding"][0]["code"]

        if data_category not in ["Lab", "LAB"]:
            continue

        ## Some Diagnostic Report files have multiple results contained

        if "contained" in file_data:
            i = 0
            for observation in file_data["contained"]:
                try:
                    process_observation(observation, f + str(i))
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


verbose_print("\nProcessing complete, writing data to files...\n")

observation_dates.sort()
observation_dates.reverse()

abnormal_result_dates.sort()
abnormal_result_dates.reverse()


if len(observations) > 0:
    if len(abnormal_results) > 0:
        
        ## Log abnormal results by code then date
        
        try:
            with open(abnormal_results_output_text, "w") as textfile:
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
                                interpretation = observation.result.get_result_interpretation_text()
                                value = observation.value
                                if observation.result.is_range_type:
                                    line = observation.date + ": " + interpretation + " - actual value " + value + " - range " + observation.result.range
                                else:
                                    line = observation.date + ": " + interpretation + " - actual value " + value
                                verbose_print(line)
                                textfile.write(line)
                                textfile.write("\n")

                            verbose_print("")
                            textfile.write("\n")

            print("Abnormal laboratory results from Apple Health saved to " + abnormal_results_output_text)

        except Exception as e:
            verbose_print(e)
            print("An error occurred in writing abnormal results data")


        ## Write abnormal results by datecode to spreadsheet

        try:
            with open(abnormal_results_output_csv, "w") as csvfile:
                filewriter = csv.writer(csvfile, delimiter=",",
                                        quotechar="\"", quoting=csv.QUOTE_MINIMAL)

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
                                        row.append(observation.value + " " + observation.result.interpretation)
                                        break
                                else:
                                    continue

                                break
                        
                        if not date_found:
                            row.append("")

                    if abnormal_result_found:
                        filewriter.writerow(row)

            print("Abnormal laboratory results from Apple Health saved to " + abnormal_results_output_csv)

        except Exception as e:
            verbose_print(e)
            print("An error occurred in writing abnormal results data to csv")

    else:
        print("No abnormal results found from current data")

    ## Write all data by datecode to spreadsheet

    try:
        with open(all_data_output_file, "w", encoding="utf-8") as csvfile:
            filewriter = csv.writer(csvfile, delimiter=",",
                                    quotechar="\"", quoting=csv.QUOTE_MINIMAL)

            header = ["Laboratory Observations from Apple Health Data"]

            for date in observation_dates:
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
                            if observation.has_result and observation.result.is_range_type:
                                row.append(" " + observation.result.range_text) # Excel formats as date without space here
                            else:
                                row.append("")
                            abnormal_result_tag = observation.result.interpretation if observation.has_result else ""
                            row.append(observation.value_string + " " + abnormal_result_tag)
                            break
                    
                    if not date_found:
                        row.append("")
                        row.append("")

                filewriter.writerow(row)

        print("Laboratory records from Apple Health saved to " + all_data_output_file)

    except Exception as e:
        verbose_print(e)
        print("An error occurred in writing observations data to csv")
        exit(1)

else:
    print("No relevant laboratory records found in exported Apple Health data")
    exit(1)


