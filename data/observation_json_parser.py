import json
import os
import traceback

from data.observation import Observation, ObservationVital, CategoryError
from data.units import VitalSignCategory

## PROCESS CLINICAL RECORDS JSON DATA


class ObservationsData:
    def __init__(self):
        self.observations = {}
        self.observations_vital_signs = {}
        self.observation_dates = []
        self.reference_dates = []
        self.observation_codes = {}
        self.observation_code_ids = {}
        self.tests = []
        self.date_codes = {}
        self.ranges = {}
        self.abnormal_results = {}
        self.abnormal_result_dates = []
        self.total_abnormal_results = 0
        self.abnormal_result_interpretations_by_code = {}

    def sort(self):
        self.observation_dates.sort()
        self.observation_dates.reverse()

    def determine_abnormal_results(self, verbose, skip_in_range_abnormal_results, in_range_abnormal_boundary):
        ## APPLY RANGES TO CLINICAL RECORDS RESULTS
        if len(self.reference_dates) > 0:
            if verbose:
                print("\nConsolidating ranges and validating all results where "
                        + "ranges apply are tested for abnormality...\n")
            # Construct ranges object
            for code in sorted(self.observation_code_ids):
                range_found = False
                for date in self.observation_dates:
                    if range_found:
                        break
                    for code_id in self.observation_code_ids[code]:
                        datecode = date + code_id
                        if datecode in self.date_codes:
                            observation = self.observations[self.date_codes[datecode]]
                            if date in self.reference_dates and observation.has_reference:
                                self.ranges[code] = observation.result.range_text
                                range_found = True
                                break
            for code in sorted(self.observation_code_ids):
                if code not in self.ranges:
                    continue
                code_range = self.ranges[code]
                range_list = [{"text": code_range}]
                for date in self.observation_dates:
                    for code_id in self.observation_code_ids[code]:
                        datecode = date + code_id
                        if datecode in self.date_codes:
                            obs = self.observations[self.date_codes[datecode]]
                            if not obs.has_reference:
                                if verbose:
                                    print("Found missing reference range for code "
                                            + code + " on " + date + " - attempting "
                                            + "to apply range from other results")
                                obs.set_reference(skip_in_range_abnormal_results,
                                                in_range_abnormal_boundary,
                                                range_list, obs.unit, True)
                                if obs.has_reference:
                                    if obs.date not in self.reference_dates:
                                        self.reference_dates.append(obs.date)
                                    if obs.result.is_abnormal:
                                        if obs.primary_code_id not in self.abnormal_results:
                                            self.abnormal_results[obs.primary_code_id] = []
                                        results = self.abnormal_results[obs.primary_code_id]
                                        results.append(obs)
                                        self.abnormal_results[obs.primary_code_id] = results
                                        if obs.date not in self.abnormal_result_dates:
                                            self.abnormal_result_dates.append(obs.date)

        self.abnormal_result_dates.sort()
        self.abnormal_result_dates.reverse()
        self.reference_dates.sort()


class ObservationJSONDataParser:
    category_vital_signs = "Vital Signs"
    disallowed_codes = ["NARRATIVE", "REQUEST PROBLEM"]

    def __init__(self, args, custom_data_files, observations_data):
        self.args = args
        self.verbose = args.verbose
        self.base_dir = args.base_dir
        self.subject = args.subject
        self.health_files = os.listdir(self.base_dir)
        self.custom_data_files = custom_data_files
        self.data = observations_data if observations_data else ObservationsData()
        self.vital_sign_categories = [
            member.value for name, member in VitalSignCategory.__members__.items()]
        self.vital_sign_categories.insert(0, ObservationJSONDataParser.category_vital_signs)

    def parse(self):
        print("Parsing clinical-records JSON...")        
        for f in self.health_files:
            file_category = f[0:(f.index("-"))]
            f_addr = os.path.join(self.base_dir, f)
            # Get data from Observation files
            if file_category == "Observation":
                file_data = json.load(open(f_addr))
                if "name" not in self.subject and "subject" in file_data:
                    subject_data = file_data["subject"]
                    if (subject_data is not None and "display" in subject_data
                            and subject_data["display"] is not None):
                        self.subject["name"] = subject_data["display"]
                        if self.verbose:
                            print("Identified subject: " + self.subject["name"])
                try:
                    self.process_observation(file_data, f)
                except Exception as e:
                    if self.verbose:
                        print(e)
                    continue
            # Get data from Diagnostic Report type files
            elif file_category == "DiagnosticReport":
                if "-CUSTOM" in f_addr:
                    self.custom_data_files.append(f_addr)
                file_data = json.load(open(f_addr))
                data_category = file_data["category"]["coding"][0]["code"]
                if data_category not in ["Lab", "LAB"]:
                    continue
                # Some Diagnostic Report files have multiple results contained
                if "contained" in file_data:
                    i = 0
                    for observation in file_data["contained"]:
                        try:
                            self.process_observation(observation, f + "[" + str(i) + "]")
                        except Exception as e:
                            if self.verbose:
                                print(e)
                            continue
                        i += 1
                else:
                    try:
                        self.process_observation(file_data, f)
                    except Exception as e:
                        if self.verbose:
                            print(e)
                        continue

        self.data.sort()
        return self.data



    def handle_vital_sign_category_observation(self, data: dict, obs_id: str,
                                            start_year: int, skip_long_values: bool,
                                            skip_in_range_abnormal_results: bool,
                                            in_range_abnormal_boundary: float):
        obs_v = None

        try:
            obs_v = ObservationVital(data, obs_id, self.data.tests, self.data.date_codes,
                                    start_year, skip_long_values, skip_in_range_abnormal_results,
                                    in_range_abnormal_boundary)
        except ValueError as e:
            if self.verbose:
                print(e)
            pass
        except AssertionError as e:
            if self.verbose:
                print(e)
        except Exception as e:
            if self.verbose:
                print("Exception encountered in gathering data from observation:")
                print(obs_id)
            if obs_v is not None and obs_v.datecode is not None:
                if self.verbose:
                    print(obs_v.datecode)
            traceback.print_exc()
            raise e
        if obs_v is not None:
            force_presence = str(obs_v.observation_complete)
        if obs_v is None or not obs_v.observation_complete:
            return
        if obs_v.date is not None and obs_v.date in self.args.skip_dates:
            raise Exception("Skipping observation on date " + obs_v.date)

        if obs_v.category == ObservationJSONDataParser.category_vital_signs:
            for category in list(VitalSignCategory):
                if obs_v.code and category.matches(obs_v.code):
                    obs_v.set_vital_sign_category(category)
                    break
            if obs_v.vital_sign_category is None:
                raise AssertionError("Vital sign observation category not identified: "
                                    + obs_v.category)
        else:
            for category in list(VitalSignCategory):
                if category.matches(obs_v.category):
                    obs_v.set_vital_sign_category(category)
                    break
            if obs_v.vital_sign_category is None:
                raise AssertionError("Vital sign observation category not identified: "
                                    + obs_v.category)

        if obs_v.date in self.data.observations_vital_signs:
            this_date_observations = self.data.observations_vital_signs[obs_v.date]
        else:
            this_date_observations = []

        this_date_observations.append(obs_v)
        self.data.observations_vital_signs[obs_v.date] = this_date_observations

        if self.verbose:
            print(f"Vital sign observation recorded for {obs_v.code} on {obs_v.date}")


    def process_observation(self, data: dict, obs_id: str):
        obs = None
        try:
            obs = Observation(data, obs_id, self.data.tests, self.data.date_codes, self.args.start_year,
                    self.args.skip_long_values, self.args.skip_in_range_abnormal_results,
                    self.args.in_range_abnormal_boundary, self.vital_sign_categories,
                    ObservationJSONDataParser.disallowed_codes)
        except ValueError:
            pass
        except CategoryError:
            self.handle_vital_sign_category_observation(data, obs_id,
                    self.args.start_year,
                    self.args.skip_long_values,
                    self.args.skip_in_range_abnormal_results,
                    self.args.in_range_abnormal_boundary)
            return
        except AssertionError as e:
            if self.verbose:
                print(e)
        except Exception as e:
            if self.verbose:
                print("Exception encountered in gathering data from observation:")
                print(obs_id)
            if obs is not None and obs.datecode is not None:
                if self.verbose:
                    print(obs.datecode)
            traceback.print_exc()
            raise e
        if obs is None or not obs.observation_complete:
            return
        if obs.date is not None and obs.date in self.args.skip_dates:
            raise Exception("Skipping observation on date " + obs.date)

        self.data.observations[obs_id] = obs
        if obs.is_seen_test:
            self.data.tests[obs.test_index] = obs.test
        else:
            self.data.tests.append(obs.test)
        if obs.primary_code_id not in self.data.observation_codes:
            self.data.observation_codes[obs.primary_code_id] = obs.code
        if obs.code not in self.data.observation_code_ids:
            self.data.observation_code_ids[obs.code] = []
        code_ids = self.data.observation_code_ids[obs.code]
        if obs.primary_code_id not in code_ids:
            code_ids.append(obs.primary_code_id)
            self.data.observation_code_ids[obs.code] = code_ids
        if obs.date is not None:
            if obs.date not in self.data.observation_dates:
                self.data.observation_dates.append(obs.date)
            if obs.has_reference and obs.date not in self.data.reference_dates:
                self.data.reference_dates.append(obs.date)

        self.data.date_codes[obs.datecode] = obs_id

        if obs.has_reference and obs.result and obs.result.is_abnormal:
            if obs.primary_code_id not in self.data.abnormal_results:
                self.data.abnormal_results[obs.primary_code_id] = []
            results = self.data.abnormal_results[obs.primary_code_id]
            results.append(obs)
            self.data.abnormal_results[obs.primary_code_id] = results
            if obs.date not in self.data.abnormal_result_dates:
                self.data.abnormal_result_dates.append(obs.date)
        if self.verbose:
            print(f"Observation recorded for {obs.code} on {obs.date}")



