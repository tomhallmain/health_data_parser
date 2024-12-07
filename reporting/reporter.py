from copy import deepcopy
import csv
from datetime import datetime
import json
import operator
import os
import traceback

from data.result import get_interpretation_keys, get_interpretation_text
from reporting.report import Report


class Reporter:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def report_abnormal_results_by_code_then_date(self, filepath, data):
        if len(data.abnormal_results) > 0:
            try:
                with open(filepath, "w") as textfile:
                    line = "|----- Laboratory Abnormal Results from Apple Health Data by Code -----|"
                    if self.verbose:
                        print("\n")
                        print(line)
                        print("\n")
                    textfile.write(line)
                    textfile.write("\n\n")
                    for code in sorted(data.observation_code_ids):
                        for code_id in data.observation_code_ids[code]:
                            if code_id in data.abnormal_results:
                                results = data.abnormal_results[code_id]
                                line = "Abnormal results found for code " + code + ":"
                                if self.verbose:
                                    print(line)
                                textfile.write(line)
                                textfile.write("\n")
                                for observation in sorted(results, key=operator.attrgetter("date")):
                                    data.total_abnormal_results += 1
                                    interpretation = observation.result.get_result_interpretation_text()
                                    value_string = observation.value_string
                                    if observation.result.is_range_type:
                                        line = (observation.date + ": " + interpretation
                                                + " - observed " + value_string
                                                + " - range " + observation.result.range)
                                    else:
                                        line = (observation.date + ": " + interpretation
                                                + " - observed " + value_string)
                                    if self.verbose:
                                        print(line)
                                    textfile.write(line)
                                    textfile.write("\n")
                                if self.verbose:
                                    print("")
                                textfile.write("\n")
                print("Abnormal laboratory results data from Apple Health saved to "
                    + filepath)
            except Exception as e:
                print("An error occurred in writing abnormal results data.")
                if self.verbose:
                    traceback.print_exc()
        else:
            print("No abnormal results found from current data")


    def report_abnormal_results_by_interpretation(self, filepath, data, args):
        # Log abnormal results by interpretation class, code, date

        if len(data.abnormal_results) > 0:
            try:
                with open(filepath, "w") as csvfile:
                    filewriter = csv.writer(
                        csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)
                    interpretation_keys = get_interpretation_keys(args.skip_in_range_abnormal_results)
                    header = [
                        "Laboratory Abnormal Results by Interpretation from Apple Health Data"]
                    interpretations = list(
                        map(lambda key: get_interpretation_text(key), interpretation_keys))
                    header.extend(interpretations)
                    filewriter.writerow(header)
                    for code in sorted(data.observation_code_ids):
                        abnormal_result_found = False
                        row = [code]
                        code_interpretation_keys = []
                        for code_id in data.observation_code_ids[code]:
                            if code_id in data.abnormal_results:
                                results = data.abnormal_results[code_id]
                                abnormal_result_found = True
                                for observation in results:
                                    interpretation_key = observation.result.interpretation
                                    if interpretation_key not in code_interpretation_keys:
                                        code_interpretation_keys.append(
                                            interpretation_key)
                        if abnormal_result_found:
                            code_interpretations = []
                            for interpretation_key in interpretation_keys:
                                if interpretation_key in code_interpretation_keys:
                                    row.append(interpretation_key)
                                    code_interpretations.append(
                                        get_interpretation_text(interpretation_key))
                                else:
                                    row.append("")
                            data.abnormal_result_interpretations_by_code[code] = code_interpretations
                            filewriter.writerow(row)
                print("Abnormal laboratory results data from Apple Health sorted by "
                    + "interpretation saved to " + filepath)
            except Exception as e:
                print("An error occurred in writing abnormal results data.")
                if self.verbose:
                    traceback.print_exc()

    def report_abnormal_results_by_date(self, filepath, data):
        # Write abnormal results by datecode to spreadsheet
        if len(data.abnormal_results) > 0:
            try:
                with open(filepath, "w") as csvfile:
                    filewriter = csv.writer(
                        csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)
                    header = ["Laboratory Abnormal Results from Apple Health Data"]
                    for date in data.abnormal_result_dates:
                        header.append(date)
                    filewriter.writerow(header)
                    for code in sorted(data.observation_code_ids):
                        row = [code]
                        abnormal_result_found = False
                        for date in data.abnormal_result_dates:
                            date_found = False
                            for code_id in data.observation_code_ids[code]:
                                if code_id in data.abnormal_results:
                                    abnormal_result_found = True
                                    results = data.abnormal_results[code_id]
                                    for observation in results:
                                        if (observation.date == date and date + code_id in data.date_codes):
                                            date_found = True
                                            row.append(observation.value_string + " "
                                                    + observation.result.interpretation)
                                            break
                                    else:
                                        continue
                                    break
                            if not date_found:
                                row.append("")
                        if abnormal_result_found:
                            filewriter.writerow(row)
                print("Abnormal laboratory results data from Apple Health saved to " + filepath)
            except Exception as e:
                print("An error occurred in writing abnormal results data to CSV.")
                if self.verbose:
                    traceback.print_exc()
        else:
            print("No abnormal results found from current data")

    def report_all_data_by_datecode(self, filepath, data):
        # Write all data by datecode to spreadsheet

        try:
            with open(filepath, "w", encoding="utf-8") as csvfile:
                filewriter = csv.writer(csvfile, delimiter=",",
                                        quotechar="\"", quoting=csv.QUOTE_MINIMAL)
                header = ["Laboratory Observations from Apple Health Data"]
                for date in data.observation_dates:
                    if date in data.reference_dates:
                        header.append(date + " range")
                    header.append(date + " result")
                filewriter.writerow(header)
                for code in sorted(data.observation_code_ids):
                    row = [code]
                    for date in data.observation_dates:
                        date_found = False
                        for code_id in data.observation_code_ids[code]:
                            datecode = date + code_id
                            if datecode in data.date_codes:
                                date_found = True
                                observation = data.observations[data.date_codes[datecode]]
                                if date in data.reference_dates:
                                    if observation.has_reference:
                                        row.append(" " + observation.result.range_text)
                                        # Excel formats as date without space here
                                    else:
                                        row.append("")
                                abnormal_result_tag = " " + \
                                    observation.result.interpretation if observation.has_reference else ""
                                row.append(observation.value_string
                                        + abnormal_result_tag)
                                break
                        if not date_found:
                            row.append("")
                            if date in data.reference_dates:
                                row.append("")
                    filewriter.writerow(row)
            print("Laboratory records data from Apple Health saved to " + filepath)
        except Exception as e:
            print("An error occurred in writing observations data to CSV.")
            if self.verbose:
                traceback.print_exc()
            exit(1)

    def report_all_data_json_and_pdf(self, include_observations, filepath, data_export_dir, data, xml_data, symptom_data, vital_stats_graph, food_data, custom_data_files, args):
        # Write simplified observations data to JSON

        json_data = {}
        save_stats_objs = {}

        try:
            meta = {}
            meta["description"] = "Health Records Report"
            meta["processTime"] = str(datetime.now())
            if include_observations:
                meta["observationCount"] = len(data.observations)
                meta["vitalSignsObservationCount"] = (
                    len(data.observations_vital_signs) + xml_data.xml_vitals_observations_count)
                meta["mostRecentResult"] = data.observation_dates[0]
                meta["earliestResult"] = data.observation_dates[-1]
                meta["heartRateMonitoringWearableDetected"] = xml_data.pulse_stats["graphEligible"]
            json_data["meta"] = meta
            if include_observations:
                if meta["vitalSignsObservationCount"] > 0:
                    vital_signs = {}
                    if args.json_add_all_vitals:
                        json_data["vitalSigns"] = xml_data.vitals_stats_list
                    else:
                        save_stats_objs = deepcopy(xml_data.vitals_stats_list)
                        json_data["vitalSigns"] = []
                        for stats_obj in save_stats_objs:
                            new_obj = stats_obj.copy()
                            del new_obj["list"]
                            if "graph" in new_obj:
                                del new_obj["graph"]
                            json_data["vitalSigns"].append(new_obj)
                if data.total_abnormal_results > 0:
                    abnormal_results_data = {}
                    meta = {}
                    meta["codesWithAbnormalResultsCount"] = len(data.abnormal_results)
                    meta["totalAbnormalResultsCount"] = data.total_abnormal_results
                    meta["includesInRangeAbnormalities"] = (args.in_range_abnormal_boundary > 0
                                                            and not args.skip_in_range_abnormal_results)
                    meta["inRangeAbnormalBoundary"] = args.in_range_abnormal_boundary
                    abnormal_results_data["meta"] = meta
                    abnormal_results_data["codesWithAbnormalResults"] = data.abnormal_result_interpretations_by_code
                    json_data["abnormalResults"] = abnormal_results_data
                observations_list = []
                for obs_id in data.observations:
                    observations_list.append(data.observations[obs_id].to_dict(obs_id, data.tests))
                observations_list.sort(key=lambda obs: obs.get("date"))
                observations_list.reverse()
                json_data["observations"] = observations_list

            class DateTimeEncoder(json.JSONEncoder):
                def default(self, z):
                    if isinstance(z, datetime):
                        return (datetime.strftime(z, args.datetime_format))
                    else:
                        return super().default(z)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, cls=DateTimeEncoder, ensure_ascii=False, indent=4)
            print("Laboratory records data from Apple Health saved to " + filepath)
        except Exception as e:
            print("An error occurred in writing observations data to JSON.")
            if self.verbose:
                traceback.print_exc()
            if self.verbose:
                print(e)
            exit(1)

        # Write observations data to PDF report

        try:
            if include_observations and not args.json_add_all_vitals:
                json_data["vitalSigns"] = save_stats_objs
            report = Report(data_export_dir, args.subject, json_data["meta"]["processTime"][:10],
                            self.verbose, args.report_highlight_abnormal_results)
            report.create_pdf(json_data, data, symptom_data, vital_stats_graph, food_data)
            print("Results report saved to " + os.path.join(data_export_dir, report.filename))
        except Exception as e:
            print("An error occurred in writing observations data to PDF report.")
            if self.verbose:
                traceback.print_exc()
            if self.verbose:
                print(e)
            exit(1)

        if self.verbose and len(custom_data_files) > 0:
            print("\nThe compiled information includes some custom data not exported from Apple Health:")
            for filename in custom_data_files:
                print(filename)
