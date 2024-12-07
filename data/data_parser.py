from datetime import datetime, timezone
import operator
import os
import traceback

from data.observation_json_parser import ObservationsData, ObservationJSONDataParser
from data.xml_parser import AppleHealthXMLData, AppleHealthXMLParser
from data.food_data import FoodData
from data.symptom_set import SymptomSet
from data.units import VitalSignCategory, HeightUnit, WeightUnit, TemperatureUnit
from data.units import convert, calculate_bmi, set_stats
from generate_diagnostic_report_files import generate_diagnostic_report_files
from reporting.graph import VitalsStatsGraph
from reporting.reporter import Reporter


### TODO get weighted severity of abnormality by code


class DataParser:
    def __init__(self, args):
        self.args = args
        self.data_export_dir = args.data_export_dir
        self.verbose = args.verbose
        self.food_data_csv = args.food_data_csv
        self.symptom_data_csv = args.symptom_data_csv
        self.json_add_all_vitals = args.json_add_all_vitals
        self.subject = {}
        self.normal_height_unit = HeightUnit.CM
        self.normal_weight_unit = WeightUnit.LB
        self.normal_temperature_unit = TemperatureUnit.C

        self.all_data_csv = os.path.join(self.data_export_dir, "observations.csv")
        self.all_data_json = os.path.join(self.data_export_dir, "observations.json")
        self.abnormal_results_output_csv = os.path.join(self.data_export_dir, "abnormal_results.csv")
        self.abnormal_results_by_interp_csv = os.path.join(self.data_export_dir,
            "abnormal_results_by_interpretation.csv")
        self.abnormal_results_by_code_text = os.path.join(self.data_export_dir, "abnormal_results_by_code.txt")
        self.export_xml = os.path.join(self.data_export_dir, "export.xml")
        self.export_cda_xml = os.path.join(self.data_export_dir, "export_cda.xml")
        self.base_dir = os.path.join(self.data_export_dir, "clinical-records")

        self.xml_data = AppleHealthXMLData(self.normal_height_unit, self.normal_weight_unit)
        self.custom_data_files = []
        self.food_data = None
        self.symptom_data = None
        self.observations_data = ObservationsData()
        self.vital_stats_graph = None

    def create_custom_report(self):
        self.process_custom_data()
        self.report(include_observations=False)

    def run(self):
        self.process_custom_data()
        self.process_xml_data()
        self.process_json_data()
        self.observations_data.determine_abnormal_results(self.verbose,
                self.args.skip_in_range_abnormal_results,
                self.args.in_range_abnormal_boundary)
        self.compile_vital_signs_data()
        self.do_stats_calcs()
        self.create_wearable_vitals_graph(self.xml_data)
        self.report()

    def process_custom_data(self):
        ## PROCESS CUSTOM DATA FILES
        if self.args.extra_observations_csv is not None:
            self.custom_data_files.append(self.args.extra_observations_csv)
            if not generate_diagnostic_report_files(self.args.extra_observations_csv, self.base_dir, self.verbose, False):
                exit(1)

        if self.food_data_csv is not None:
            try:
                self.food_data = FoodData(self.food_data_csv, self.verbose)
                if self.food_data.to_print:
                    self.food_data.save_most_common_foods_chart(80, self.data_export_dir)
                    if self.food_data.to_print:
                        self.custom_data_files.append(self.food_data_csv)
                    else:
                        exit(1)
                else:
                    exit(1)
            except Exception as e:
                if self.verbose:
                    print(e)
                print("Failed to assemble or analyze food data provided.")
                exit(1)

        if self.symptom_data_csv is not None:
            try:
                self.symptom_data = SymptomSet(self.symptom_data_csv, self.verbose, self.args.start_year)
                if len(self.symptom_data.symptoms) > 0:
                    self.symptom_data.set_chart_start_date()
                    self.symptom_data.generate_chart_data()
                    self.symptom_data.save_chart(30, self.data_export_dir)
                    if self.symptom_data.has_both_resolved_and_unresolved_symptoms():
                        self.symptom_data.generate_chart_data(include_historical_symptoms=False)
                        self.symptom_data.save_chart(30, self.data_export_dir, unresolved_only=True)
                    if self.symptom_data.to_print:
                        self.custom_data_files.append(self.symptom_data_csv)
                    else:
                        exit(1)
            except Exception as e:
                if self.verbose:
                    print(e)
                print("Failed to assemble symptom data provided.")
                exit(1)

    def process_xml_data(self):
        ## PROCESS APPLE HEALTH XML DATA
        if self.args.only_clinical_records:
            if self.verbose:
                print("Skipping all data present not in clinical-records folder.")
        elif os.path.exists(self.export_xml):
            xml_parser = AppleHealthXMLParser(self.xml_data, self.args)
            xml_parser.parse(self.export_xml)
        else:
            print("WARNING: export.xml or export_cda.xml not found in export directory.")

    def process_json_data(self):
        json_parser = ObservationJSONDataParser(self.args, self.custom_data_files, self.observations_data)
        json_parser.parse()


    def compile_vital_signs_data(self):
        ## COMPILE VITAL SIGNS DATA
        if self.verbose:
           print("\nCompiling vital signs data from clinical records if present...\n")
        current_tzinfo = timezone(datetime.now().astimezone().tzinfo.utcoffset(None))

        for vitals_date in sorted(self.observations_data.observations_vital_signs.keys()):
            vitals_datetime = datetime.fromisoformat(vitals_date)
            vitals_datetime = vitals_datetime.replace(tzinfo=current_tzinfo)
            this_date_observations = self.observations_data.observations_vital_signs[vitals_date]
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
                    elif obs.value is None or obs.unit is None:
                        if (obs.vital_sign_category is VitalSignCategory.TEMPERATURE
                                and obs.value is not None):
                            obs.unit = "F" if obs.value > 45 else "C"
                        else:
                            print("Skipping obs on date " + vitals_date + " of category "
                                + str(obs.vital_sign_category) + " because value or unit was None")
                            continue
                    if obs.vital_sign_category is VitalSignCategory.BLOOD_PRESSURE:
                        self.xml_data.blood_pressure_stats["unit"] = obs.unit
                        set_stats(self.xml_data.blood_pressure_stats, vitals_datetime,
                                [obs.value, obs.value2])
                    elif obs.vital_sign_category is VitalSignCategory.PULSE:
                        self.xml_data.pulse_stats["unit"] = obs.unit
                        set_stats(self.xml_data.pulse_stats, vitals_datetime, obs.value)
                        self.xml_data.pulse_stats["list"][-1]["motion"] = 0
                        # Assume heart rate observations in clinical-records are not in motion
                    elif obs.vital_sign_category is VitalSignCategory.RESPIRATION:
                        self.xml_data.respiration_stats["unit"] = obs.unit
                        set_stats(self.xml_data.respiration_stats, vitals_datetime, obs.value)
                    elif obs.vital_sign_category is VitalSignCategory.TEMPERATURE:
                        this_temp_unit = TemperatureUnit.from_value(obs.unit)
                        normalized_temperature = round(this_temp_unit.convertTo(
                            self.args.normal_temperature_unit, obs.value), 2)
                        set_stats(self.xml_data.temperature_stats, vitals_datetime,
                                normalized_temperature)
                        self.xml_data.temperature_stats["unit"] = obs.unit
                if this_date_height is not None and this_date_height_unit is not None:
                    normalized_height = convert(self.args.normal_height_unit,
                        HeightUnit.from_value(this_date_height_unit), this_date_height)
                    set_stats(self.xml_data.height_stats, vitals_datetime, normalized_height)
                if this_date_weight is not None and this_date_weight_unit is not None:
                    normalized_weight = convert(self.args.normal_weight_unit,
                        WeightUnit.from_value(this_date_weight_unit), this_date_weight)
                    set_stats(self.xml_data.weight_stats, vitals_datetime, normalized_weight)
                if normalized_height is None or normalized_weight is None:
                    continue
                bmi = calculate_bmi(normalized_height, normalized_weight,
                                    self.args.normal_height_unit, self.args.normal_weight_unit, self.verbose)
                set_stats(self.xml_data.bmi_stats, vitals_datetime, bmi)
            except Exception as e:
                if self.verbose:
                    print(e)


    def do_stats_calcs(self):
        # TODO refactor this logic into a function in a Stats class
        for stats_obj in self.xml_data.vitals_stats_list:
            try:
                stats_obj["list"] = sorted(
                    stats_obj["list"], key=operator.itemgetter("time"))
            except Exception:
                print("WARNING: Encountered a problem comparing timezones between XML and clinical records JSON data."
                    + " Vital signs output that relies on sorting may not be calculated correctly.")
                tzinfos = []
                for obs in stats_obj["list"]:
                    date = obs["time"]
                    if date.tzinfo not in tzinfos:
                        if self.verbose:
                            print("Found new tzinfo for date " + str(date))
                            print(date.tzinfo)
                        tzinfos.append(date.tzinfo)
            if stats_obj["count"] > 0:
                stats_obj["mostRecent"] = stats_obj["list"][-1]
                if stats_obj["mostRecent"]["value"] is None:
                    if self.verbose:
                        print("Stats collection for vital " + str(stats_obj["vital"]) + " failed.")
                elif type(stats_obj["mostRecent"]["value"]) == list:
                    stats_obj["stDev"] = []
                    for i in range(len(stats_obj["mostRecent"])):
                        avg = stats_obj["sum"][i] / stats_obj["count"]
                        stats_obj["avg"][i] = avg
                        sum_sq_diffs = 0
                        for obs in stats_obj["list"]:
                            sum_sq_diffs += (obs["value"][i] - avg) ** 2
                        stats_obj["stDev"].append(
                            (sum_sq_diffs / stats_obj["count"]) ** (1/2))
                    del stats_obj["sum"]
                else:
                    avg = stats_obj["sum"] / stats_obj["count"]
                    stats_obj["avg"] = avg
                    del stats_obj["sum"]
                    sum_sq_diffs = 0
                    for obs in stats_obj["list"]:
                        sum_sq_diffs += (obs["value"] - avg) ** 2
                    stats_obj["stDev"] = (sum_sq_diffs / stats_obj["count"]) ** (1/2)
                if self.verbose:
                    print("Found stats for vital sign: " + stats_obj["vital"])
                    print(str(stats_obj["count"]) + " unique observations with average value "
                        + str(stats_obj["avg"]) + " and standard deviation " + str(stats_obj["stDev"]))


    def create_wearable_vitals_graph(self, data):
        ## WEARABLE VITALS GRAPH CALCS
        # If no wearable data is present, there will not be enough data for a usable graph
        data.pulse_stats["graphEligible"] = data.pulse_stats["count"] > 10000

        if data.pulse_stats["graphEligible"]:
            try:
                self.vital_stats_graph = VitalsStatsGraph(
                    AppleHealthXMLParser.min_xml_ordinal, data.pulse_stats, data.hrv_stats, data.step_stats, data.stand_stats)
                self.vital_stats_graph.save_graph_images(self.data_export_dir)
            except Exception as e:
                if self.verbose:
                    print(e)
                traceback.print_exc()
            if self.vital_stats_graph is None or not self.vital_stats_graph.to_print:
                print("WARNING: Failed to generate pulse statistics graph, skipping print.")

        data.vitals_stats_list.remove(data.step_stats)

    def report(self, include_observations=True):
        ## WRITE DATA TO FILES
        if self.verbose:
            print("\nProcessing complete, writing data to files...\n")

        if include_observations and len(self.observations_data.observations) == 0:
            print("No relevant laboratory records found in exported Apple Health data")
            exit(1)

        if len(self.custom_data_files) > 0:
            print("\nThe compiled information includes some custom data not exported from Apple Health:")
            for filename in self.custom_data_files:
                print(filename)
            print("")

        reporter = Reporter(self.verbose)
        if include_observations:
            reporter.report_abnormal_results_by_code_then_date(self.abnormal_results_by_code_text, self.observations_data)
            reporter.report_abnormal_results_by_interpretation(self.abnormal_results_by_interp_csv, self.observations_data, self.args)
            reporter.report_abnormal_results_by_date(self.abnormal_results_output_csv, self.observations_data)
            reporter.report_all_data_by_datecode(self.all_data_csv, self.observations_data)
        reporter.report_all_data_json_and_pdf(
            include_observations, self.all_data_json, self.data_export_dir, self.observations_data, self.xml_data,
            self.symptom_data, self.vital_stats_graph, self.food_data, self.custom_data_files, self.args)
