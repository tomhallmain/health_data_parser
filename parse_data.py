from datetime import datetime
import getopt
import os
import sys

from data.data_parser import DataParser
from data.units import HeightUnit, WeightUnit, TemperatureUnit, get_age

class HealthDataParseArgs:
    def __init__(self, data_export_dir):
        if data_export_dir is None or data_export_dir == "":
            print("Missing Apple Health data export directory path.")
            print(help_text)
            exit(1)
        elif not os.path.exists(data_export_dir) or not os.path.isdir(data_export_dir):
            print(f"Apple Health data export directory path \"{data_export_dir}\" is invalid.")
            print(help_text)
            exit(1)

        self.data_export_dir = data_export_dir
        self.datetime_format = "%Y-%m-%d %X %z"
        self.custom_only = False
        self.only_clinical = False
        self.start_year = 0
        self.skip_long_values = True
        self.start_year = None
        self.verbose = False
        self.skip_long_values = False
        self.skip_in_range_abnormal_results = False
        self.in_range_abnormal_boundary = 0.15
        self.skip_dates = []
        self.report_highlight_abnormal_results = True
        self.only_clinical_records = False
        self.extra_observations_csv = None
        self.food_data_csv = None
        self.symptom_data_csv = None
        self.json_add_all_vitals = False
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

        if not os.path.exists(self.base_dir) or len(os.listdir(self.base_dir)) == 0:
            print("Folder \"clinical-records\" not found in export folder \""
                + data_export_dir + "\".")
            print("Ensure data has been connected to Apple Health before export.")
            exit(1)


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
        include laboratory data not hooked up to your Apple Health in the output

    --symptom_data=path/to/symptom_data.csv
        Fill out the sample CSV with data about current and past symptoms to
        include a timeline chart in the PDF report

    --food_data=path/to/food_data.csv
        Fill out the sample CSV with data and pass the location at runtime to
        include nutritional data in the PDF report

    --report_highlight_abnormal_results=[bool]
        By default abnormal results are highlighted in observations tables on the
        report. To turn this off, set this value to False.

    --birth_date=[YYYY-MM-DD]
        Subject birth date for reporting purposes, if not found in export XML.

    --json_add_all_vitals
        If using a wearable, many vital sign observations may be accumulated.
        By default these are not added to the JSON output - pass to add these.

    --custom_only
        Skip parsing of Apple Health export data and only create a report from
        the custom files provided in the arguments.

    -h, --help
        Print this help text

    -v, --verbose
        Run in verbose mode
"""

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(help_text)
        exit()

    data_export_dir = sys.argv[1]
    parse_args = HealthDataParseArgs(data_export_dir)
    COMMANDS = sys.argv[2:]


    ## VALIDATE AND SET FROM COMMANDS


    try:
        opts, args = getopt.getopt(COMMANDS, ":hv", [
                "filter_abnormal_in_range",
                "help",
                "json_add_all_vitals",
                "only_clinical_records",
                "skip_long_values",
                "verbose",
                "custom_only",
                "birth_date=",
                "extra_observations=",
                "food_data=",
                "in_range_abnormal_boundary=",
                "report_highlight_abnormal_results=",
                "start_year=",
                "skip_dates=",
                "symptom_data=",
                ])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like "option -a not recognized"
        print(help_text)
        sys.exit(2)

    for o, a in opts:
        # basic options
        if o in ("-h", "--help"):
            print(help_text)
            exit()
        elif o in ("-v", "--verbose"):
            parse_args.verbose = True
        elif o == "--json_add_all_vitals":
            parse_args.json_add_all_vitals = True
            print("Including all vital data in JSON output")
        elif o == "--filter_abnormal_in_range":
            parse_args.skip_in_range_abnormal_results = True
            print("Excluding abnormal results within allowed quantitative ranges")
        elif o == "--only_clinical_records":
            parse_args.only_clinical_records = True
            print("Skipping XML parsing")
        elif o == "--skip_long_values":
            parse_args.skip_long_values = True
            print("Skipping observations with result values over 150 characters long")
        # argument options
        elif o == "--birth_date":
            try:
                birth_date = datetime.fromisoformat(a)
            except Exception:
                print(f"\"{a}\" is not a valid list of date in format YYYY-MM-DD.")
                exit(1)
            parse_args.subject["birthDate"] = a
            parse_args.subject["age"] = get_age(birth_date)
        elif o == "--extra_observations":
            parse_args.extra_observations_csv = a
        elif o == "--food_data":
            parse_args.food_data_csv = a
        elif o == "--in_range_abnormal_boundary":
            try:
                parse_args.in_range_abnormal_boundary = float(a)
                if abs(parse_args.in_range_abnormal_boundary) >= 0.5:
                    raise ValueError("Absolute value of boundary must be less than 0.5")
                print(f"In range abnormal boundary set to {a}")
            except Exception:
                print(f"\"{a}\" is not a valid decimal-formatted percentage")
                exit(1)
        elif o == "--report_highlight_abnormal_results":
            if (a == "FALSE" or a == "False" or a == "false"):
                parse_args.report_highlight_abnormal_results = False
            elif (not a == "TRUE" and not a == "True" and not a == "true"):
                print("Found report_highlight_abnormal_results value \""
                    + a + "\" was not a boolean.")
        elif o == "--skip_dates":
            try:
                parse_args.skip_dates = a.split(",")
                for date in parse_args.skip_dates:
                    test = datetime.fromisoformat(date)
            except Exception:
                print(f"\"{a}\" is not a valid list of dates in format YYYY-MM-DD.")
                exit(1)
            if len(parse_args.skip_dates) > 0:
                print("Skipping dates: " + str(parse_args.skip_dates))
        elif o == "--start_year":
            try:
                parse_args.start_year = int(a)
                print(f"Excluding results from before start year {a}")
            except Exception:
                print(f"\"{a}\" is not a valid year.")
                exit(1)
        elif o == "--symptom_data":
            parse_args.symptom_data_csv = a
        elif o == "--custom_only":
            parse_args.custom_only = True
        else:
            assert False, "unhandled option"

    parser = DataParser(parse_args)
    if parse_args.custom_only:
        parser.create_custom_report()
    else:
        parser.run()
