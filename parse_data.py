import csv
import datetime
import json
import operator
import os
import sys
import traceback

from labtest import LabTest
from observation import Observation
from report import Report
from result import get_interpretation_keys, get_interpretation_text

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



health_files = os.listdir(base_dir)
disallowed_categories = ["Vital Signs", "Height", "Weight", "Pulse", "SpO2"]
disallowed_codes = ["NARRATIVE", "REQUEST PROBLEM"]
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


def verbose_print(text: str):
    if verbose:
        print(text)

def process_observation(data: dict, obs_id: str):
    obs = None

    try:
        obs = Observation(data, obs_id, tests, date_codes,
            start_year, skip_long_values, skip_in_range_abnormal_results, 
            in_range_abnormal_boundary, disallowed_categories, disallowed_codes)
    except ValueError as e:
        pass
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

## Write the data to files

verbose_print("\nProcessing complete, writing data to files...\n")
total_abnormal_results = 0
abnormal_result_interpretations_by_code = {}

if len(observations) > 0:
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
        meta["mostRecentResult"] = observation_dates[0]
        meta["earliestResult"] = observation_dates[-1]
        data["meta"] = meta

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

else:
    print("No relevant laboratory records found in exported Apple Health data")
    exit(1)


