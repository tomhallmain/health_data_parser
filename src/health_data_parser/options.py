import os

from health_data_parser.model.units import HeightUnit, WeightUnit, TemperatureUnit
from health_data_parser.errors import HealthDataParseError


class HealthDataParseArgs:
    def __init__(self, data_export_dir):
        if data_export_dir is None or data_export_dir == "":
            raise HealthDataParseError("Missing Apple Health data export directory path.")
        elif not os.path.exists(data_export_dir) or not os.path.isdir(data_export_dir):
            raise HealthDataParseError(
                f"Apple Health data export directory path \"{data_export_dir}\" is invalid.")

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
            raise HealthDataParseError(
                f"Folder \"clinical-records\" not found in export folder \"{data_export_dir}\". "
                "Ensure data has been connected to Apple Health before export.")
