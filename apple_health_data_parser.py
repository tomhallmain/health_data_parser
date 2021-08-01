## Simple observations parser to extract structured results data from laboratory 
## records from exported Apple Health data into a CSV file.
##
## This script has only been tested with data from a few medical institutions in
## eastern US. It likely will need to be updated for other medical institutions if 
## they have minor structural differences in their data.
##
## The following limitations are currently present:
##    - If there is more than one result for the same result code on a single 
##      date, only the first result will be recorded.
##    - Codes that resolve to the same description will be collated regardless 
##      of their id.
##
## Intended to be run from the extracted folder of the extracted health data from 
## Apple Health app.
##
## Usage:
##
##    $ mv apple_health_data_parser.py apple_health_export
##    $ python apple_health_export/apple_health_data_parser ${args}
##
##    --start_year=${year} 
##        Exclude results from before a certain year
##
##    -v, --verbose
##        Run in verbose mode


import csv
import json
import os
import re
import sys


COMMANDS = sys.argv[1:]
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

base_dir = "clinical-records"
health_files = os.listdir(base_dir)
all_data_output_file = "observations.csv"
abnormal_results_output_csv = "abnormal_results.csv"
abnormal_results_output_text = "abnormal_results_by_code.txt"

disallowed_categories = ["Vital Signs", "Height", "Weight", "Pulse", "SpO2"]
disallowed_codes = ["Narrative"]
observations = {}
observation_dates = []
observation_codes = {}
observation_code_ids = {}
codes = {}
date_codes = {}
abnormal_results = {}


def get_key(_dict, _value):
    for key, value in _dict.entries():
        if value == _value:
            return key

    raise Exception("Value " + _value + " not found in dict")

def verbose_print(text):
    if verbose:
        print(text)

def get_result_interpretation_text(interpretation_id):
    if interpretation_id == "---":
        return "LOW OUT OF RANGE"
    elif interpretation_id == "+++":
        return "HIGH OUT OF RANGE"
    elif interpretation_id == "--":
        return "Low in range"
    elif interpretation_id == "++":
        return "High in range"
    elif interpretation_id == "++++":
        return "Non-negative result"
    else:
        return ""

def gather_observation_data(data, obs_id):
    try:
        if 'valueString' not in data and 'valueQuantity' not in data:
            return

        category_dict = data["category"]

        if "text" in category_dict:
            category = category_dict["text"]
        else:
            category = category_dict["coding"][0]["code"]

        if category in disallowed_categories:
            return

        date = data["effectiveDateTime"][0:10]

        if start_year != None:
            year = int(date[0:4])
            if year < start_year:
                return

        code_dict = data["code"]
        
        if "text" in code_dict:
            code = code_dict["text"]
        else:
            code = None

        code_id = None

        if "coding" in code_dict:
            for coding in code_dict["coding"]:
                if coding["system"] == "http://loinc.org":
                    if code == None and "display" in coding:
                        code = coding["display"]
                    code_id = coding["system"] + coding["code"]

            if code_id == None or code_id == "SOLOINC":
                coding = code_dict["coding"][0]
                if code == None and "display" in coding:
                    code = coding["display"]
                code_id = coding["system"] + coding["code"]
        else:
            code_id = code

        if code_id not in observation_codes:
            if code not in observation_code_ids:
                observation_code_ids[code] = []
            code_ids = observation_code_ids[code]
            code_ids.append(code_id)
            observation_code_ids[code] = code_ids
            observation_codes[code_id] = code

        if date not in observation_dates:
            observation_dates.append(date)

        obs = {}
        obs["date"] = date
        obs["category"] = category
        obs["code"] = code
        obs["code_id"] = code_id

        datecode = date + code_id

        if datecode in date_codes:
            raise Exception("Datecode " + datecode + " for code " + code + " already recorded")
        else:
            date_codes[datecode] = obs_id

        if "valueString" in data:
            value_string = data["valueString"]
            obs["value_string"] = value_string
            value = None
        elif "valueQuantity" in data:
            value_quantity = data["valueQuantity"]
            value = value_quantity["value"]
            value = None if value == None else float(value)
            obs["value"] = value
            value_string = str(value_quantity["value"])
            if "unit" in value_quantity:
                value_string = value_string + " " + value_quantity["unit"]
            obs["value_string"] = value_string

        if "referenceRange" in data:
            range_text = data["referenceRange"][0]["text"]
            obs["range"] = " " + range_text # Excel formats as date without space here
            
            if value != None and not isinstance(value, str):
                val_range_matcher = re.search("(\d+\.\d+|\d+) *(-|–) *(\d+\.\d+|\d+)", range_text)
            
                if val_range_matcher:
                    range_lower = float(val_range_matcher.group(1))
                    range_upper = float(val_range_matcher.group(3))
                    
                    if range_lower > range_upper:
                        temp = range_upper
                        range_upper = range_lower
                        range_lower = temp
                    
                    obs["range_lower"] = range_lower
                    obs["range_higher"] = range_upper
                    low_out_of_range = value < range_lower
                    high_out_of_range = value > range_upper
                    range_span = range_upper - range_lower
                    low_end_of_range = high_end_of_range = False
                    
                    if range_span > 0:
                        low_end_of_range = not low_out_of_range and (value - range_lower) / range_span < 0.15
                        high_end_of_range = not high_out_of_range and (range_upper - value) / range_span < 0.15
                    
                    if low_out_of_range or high_out_of_range or low_end_of_range or high_end_of_range:
                        if code_id not in abnormal_results:
                            abnormal_results[code_id] = {}
                        results = abnormal_results[code_id]
                        result = {}
                        result["value"] = value_string
                        _range = str(range_lower) + " - " + str(range_upper)
                        result["range"] = _range

                        if low_out_of_range:
                            result["interpretation"] = "---"
                        elif high_out_of_range:
                            result["interpretation"] = "+++"
                        elif low_end_of_range:
                            result["interpretation"] = "--"
                        elif high_end_of_range:
                            result["interpretation"] = "++"
                        
                        obs["abnormal_result"] = result["interpretation"]
                        results[date] = result
                        abnormal_results[code_id] = results

            elif value == None and value_string != None and isinstance(value_string, str):
                is_abnormal_binary_test_result = False
                
                if range_text == "NEG" or re.match("negative", range_text, flags=re.IGNORECASE):
                    if not value_string == "NEG" and not re.match("negative", value_string, flags=re.IGNORECASE):
                        is_abnormal_binary_test_result = True
                elif re.match("clear", range_text, flags=re.IGNORECASE) and not re.match("clear", value_string, flags=re.IGNORECASE):
                    is_abnormal_binary_test_result = True
                elif re.match("positive", value_string, flags=re.IGNORECASE):
                    is_abnormal_binary_test_result = True
                
                if is_abnormal_binary_test_result:
                    if code_id not in abnormal_results:
                        abnormal_results[code_id] = {}
                    results = abnormal_results[code_id]
                    result = {}
                    result["value"] = value_string
                    result["interpretation"] = "++++"
                    results[date] = result
                    abnormal_results[code_id] = results
                    obs["abnormal_result"] = "++++"

        if "comments" in data:
            obs["comment"] = data["comments"]

        verbose_print(obs)
        observations[obs_id] = obs

    except Exception as e:
        verbose_print(e)


for f in health_files:
    file_cat = f[0:(f.index("-"))]
    f_addr = base_dir + "/" + f

    ## Get data from Observation files

    if file_cat == "Observation":
        file_data = json.load(open(f_addr))
        gather_observation_data(file_data, f)

    ## Get data from Diagnostic Report type files

    elif file_cat == "DiagnosticReport":
        file_data = json.load(open(f_addr))
        category = file_data["category"]["coding"][0]["code"]

        if category not in ["Lab", "LAB"]:
            continue

        ## Some Diagnostic Report files have multiple results contained

        if "contained" in file_data:
            i = 0
            for observation in file_data["contained"]:
                gather_observation_data(observation, f + str(i))
                i += 1
        else:
            gather_observation_data(file_data, f)



observation_dates.sort()
observation_dates.reverse()


if len(observations) > 0:

    ## Log abnormal results by code then date

    try:
        with open(abnormal_results_output_text, "w") as textfile:
            for code in sorted(observation_code_ids):
                for code_id in observation_code_ids[code]:
                    if code_id in abnormal_results:
                        results = abnormal_results[code_id]
                        line = "Abnormal results found for code " + code + ":"
                        verbose_print(line)
                        textfile.write(line)
                        textfile.write("\n")

                        for date in sorted(results):
                            interpretation = get_result_interpretation_text(results[date]["interpretation"])
                            value = results[date]["value"]
                            if "range" in results[date]:
                                _range = results[date]["range"]
                                line = date + ": " + interpretation + " - actual value " + value + " - range " + _range
                            else:
                                line = date + ": " + interpretation + " - actual value " + value
                            verbose_print(line)
                            textfile.write(line)
                            textfile.write("\n")

                        verbose_print("")
                        textfile.write("\n")

        print("Abnormal laboratory results from Apple Health saved to " + abnormal_results_output_text)

    except Exception as e:
        verbose_print(e)
        print ("An error occurred in writing abnormal results data")


    ## Write abnormal results by datecode to spreadsheet

    try:
        with open(abnormal_results_output_csv, "w") as csvfile:
            filewriter = csv.writer(csvfile, delimiter=',',
                                    quotechar="\"", quoting=csv.QUOTE_MINIMAL)

            header = ["Apple Health Data Laboratory Abnormal Results"]

            for date in observation_dates:
                header.append(date)

            filewriter.writerow(header)

            for code in sorted(observation_code_ids):
                row = [code]
                abnormal_result_found = False
                
                for date in observation_dates:
                    date_found = False
                    
                    for code_id in observation_code_ids[code]:
                        if code_id in abnormal_results:
                            abnormal_result_found = True
                            results = abnormal_results[code_id]

                            if date in results:
                                date_found = True
                                row.append(results[date]["value"] + " " + results[date]["interpretation"])
                                break
                    
                    if not date_found:
                        row.append("")

                if abnormal_result_found:
                    filewriter.writerow(row)

        print("Abnormal laboratory results from Apple Health saved to " + abnormal_results_output_csv)

    except Exception as e:
        verbose_print(e)
        print("An error occurred in writing abnormal results data to csv")

    ## Write all data by datecode to spreadsheet

    try:
        with open(all_data_output_file, "w", encoding="utf-8") as csvfile:
            filewriter = csv.writer(csvfile, delimiter=",",
                                    quotechar="\"", quoting=csv.QUOTE_MINIMAL)

            header = ["Apple Health Data Laboratory Observations"]

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
                            if "range" in observation:
                                row.append(observation["range"])
                            else:
                                row.append("")
                            abnormal_result_tag = observation["abnormal_result"] if "abnormal_result" in observation else ""
                            row.append(observation["value_string"] + " " + abnormal_result_tag)
                            break
                    
                    if not date_found:
                        row.append("")
                        row.append("")

                filewriter.writerow(row)

        print("Laboratory records from Apple Health saved to " + all_data_output_file)

    except Exception as e:
        verbose_print(e)
        print("An error occurred in writing observations data to csv")

else:
    print("No relevant laboratory records found")


