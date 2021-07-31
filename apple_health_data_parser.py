## Simple observations parser to extract structured results data from exported 
## Apple Health laboratory records data into a CSV file.
##
## This script has only been tested with data from a few medical institutions in
## eastern US. It very likely will need to be updated for other medical
## institutions if they have minor structural differences in their data.
##
## The following restrictions are currently present:
##    - If there is more than one result for the same result code on a single 
##      date, only the first result will be recorded.
##    - Output is all string data and meant to be analyzed in spreadsheet 
##      form.
##
## Intended to be run from the extracted folder of the extracted health data from 
## Apple Health app.
##
## To run in verbose mode, pass arg --verbose at runtime.


import csv
import json
import os
import sys

COMMANDS = sys.argv[1:]
verbose = len(COMMANDS) > 0 and ("-v" in COMMANDS or "--verbose" in COMMANDS)
base_dir = "clinical-records"
health_files = os.listdir(base_dir)
output_file = "observations.csv"
disallowed_categories = ["Vital Signs", "Height", "Weight", "Pulse", "SpO2"]
disallowed_codes = ["Narrative"]
observations = {}
observation_dates = []
observation_codes = {}
date_codes = {}


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
                    code_id = coding["code"]
            
            if code_id == None or code_id == "SOLOINC":
                coding = code_dict["coding"][0]
                if code == None and "display" in coding:
                    code = coding["display"]
                code_id = coding["code"]
        else:
            code_id = code

        date = data["effectiveDateTime"][0:10]

        obs = {}
        obs["date"] = date
        obs["cat"] = category
        obs["code"] = code
        obs["code_id"] = code_id

        if date not in observation_dates:
            observation_dates.append(date)

        if code_id not in observation_codes:
            observation_codes[code_id] = code

        datecode = date + code_id

        if datecode in date_codes:
            raise Exception("Datecode " + datecode + " for code " + code + " already recorded")
        else:
            date_codes[date + code_id] = obs_id

        if "valueString" in data:
            obs["val"] = data["valueString"]
        elif "valueQuantity" in data:
            value_quantity = data["valueQuantity"]
            value = str(value_quantity["value"])
            if "unit" in value_quantity:
                value = value + value_quantity["unit"]
            obs["val"] = value

        if "referenceRange" in data:
            obs["range"] = " " + data["referenceRange"][0]["text"]

        if "comments" in data:
            obs["comment"] = data["comments"]

        if verbose:
            print(obs)
        
        observations[obs_id] = obs

    except Exception as e:
        if verbose:
            print(e)


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
    with open(output_file, 'w') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',',
                                quotechar="\"", quoting=csv.QUOTE_MINIMAL)
        
        header = ["Apple Health Laboratory Observations"]

        for date in observation_dates:
            header.append(date + " range")
            header.append(date + " result")

        filewriter.writerow(header)

        for code_id in sorted(observation_codes, key=observation_codes.__getitem__):
            row = [observation_codes[code_id]]
            
            for date in observation_dates:
                datecode = date + code_id
                if datecode in date_codes:
                    observation = observations[date_codes[datecode]]
                    if "range" in observation:
                        row.append(observation["range"])
                    else:
                        row.append("")
                    row.append(observation["val"])
                else:
                    row.append("")
                    row.append("")

            filewriter.writerow(row)
    
    print("Laboratory records from Apple Health saved to " + output_file)

else:
    print("No valid laboratory records found with current parser implementation.")


