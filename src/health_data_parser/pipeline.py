import os
import traceback

from health_data_parser.analysis.abnormal import apply_shared_reference_ranges
from health_data_parser.analysis.vitals import add_clinical_vitals, sort_vital_signs
from health_data_parser.errors import HealthDataParseError
from health_data_parser.ingest.apple_xml import AppleHealthXMLParser
from health_data_parser.ingest.custom_observations import load_custom_reports
from health_data_parser.ingest.fhir_json import ClinicalRecordsParser, ObservationRules
from health_data_parser.model.food import FoodData
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.model.symptom import SymptomSet
from health_data_parser.model.vitals import VitalSigns
from health_data_parser.reporting.charts.food import save_food_chart
from health_data_parser.reporting.charts.symptoms import save_symptom_charts
from health_data_parser.reporting.charts.vitals import VitalsStatsGraph
from health_data_parser.reporting.outputs import Reporter
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('data_parser')


class DataParser:
    """Runs a parse: custom CSVs -> export.xml -> clinical records -> abnormal
    results -> vital signs -> wearable charts -> output files."""

    def __init__(self, options):
        self.options = options
        self.verbose = options.verbose
        self.outputs = options.output_paths
        self.output_dir = self.outputs.directory

        self.store = ObservationStore()
        self.vital_signs = VitalSigns(options.normal_height_unit, options.normal_weight_unit,
                                      options.normal_temperature_unit)
        self.custom_data_files = []
        # Report id -> DiagnosticReport built from --extra_observations
        self.custom_reports = {}
        self.food_data = None
        self.food_chart = None
        self.symptom_data = None
        self.symptom_charts = None
        self.vital_stats_graph = None

    def create_custom_report(self):
        os.makedirs(self.output_dir, exist_ok=True)
        self.process_custom_data()
        self.report(include_observations=False)

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        self.process_custom_data()
        self.process_xml_data()
        self.process_json_data()
        apply_shared_reference_ranges(self.store, ObservationRules.from_options(self.options),
                                      self.verbose)
        add_clinical_vitals(self.store, self.vital_signs, self.options, self.verbose)
        sort_vital_signs(self.vital_signs, self.verbose)
        self.create_wearable_vitals_graph()
        self.report()

    def process_custom_data(self):
        options = self.options
        if options.extra_observations_csv is not None:
            self.custom_data_files.append(options.extra_observations_csv)
            self.custom_reports = load_custom_reports(options.extra_observations_csv, self.verbose)
            if self.custom_reports is None:
                raise HealthDataParseError(
                    f"Failed to read extra observations data \"{options.extra_observations_csv}\".")

        if options.food_data_csv is not None:
            try:
                self.food_data = FoodData(options.food_data_csv, self.verbose)
                if self.food_data.to_print:
                    self.food_chart = save_food_chart(self.food_data, self.output_dir)
            except Exception as e:
                if self.verbose:
                    logger.error(f"Error processing food data: {e}")
                raise HealthDataParseError("Failed to assemble or analyze food data provided.") from e
            if not self.food_data.to_print:
                raise HealthDataParseError("Failed to assemble or analyze food data provided.")
            self.custom_data_files.append(options.food_data_csv)

        if options.symptom_data_csv is not None:
            try:
                self.symptom_data = SymptomSet(options.symptom_data_csv, self.verbose, options.start_year)
                self.symptom_charts = save_symptom_charts(self.symptom_data, self.output_dir)
            except Exception as e:
                if self.verbose:
                    logger.error(f"Error processing symptom data: {e}")
                raise HealthDataParseError("Failed to assemble symptom data provided.") from e
            if self.symptom_charts is not None:
                self.custom_data_files.append(options.symptom_data_csv)

    def process_xml_data(self):
        if self.options.only_clinical_records:
            if self.verbose:
                logger.info("Skipping all data present not in clinical-records folder.")
        elif os.path.exists(self.options.export_xml):
            AppleHealthXMLParser(self.vital_signs, self.options).parse(self.options.export_xml)
        else:
            logger.warning("export.xml not found in export directory.")

    def process_json_data(self):
        ClinicalRecordsParser(self.options, self.custom_data_files, self.store,
                              custom_reports=self.custom_reports).parse()

    def create_wearable_vitals_graph(self):
        # Without a wearable there isn't enough heart rate data for usable charts
        if not self.vital_signs.wearable_heart_rate_detected:
            return
        vitals = self.vital_signs
        try:
            self.vital_stats_graph = VitalsStatsGraph(
                vitals.earliest_xml_ordinal, vitals.pulse, vitals.hrv, vitals.steps, vitals.stand)
            self.vital_stats_graph.save_graph_images(self.output_dir)
        except Exception as e:
            logger.error(f"Error creating wearable vitals graph: {e!r}")
            if self.verbose:
                logger.error(traceback.format_exc())
        if self.vital_stats_graph is None or not self.vital_stats_graph.to_print:
            logger.warning("Failed to generate pulse statistics graph, skipping print.")

    def report(self, include_observations=True):
        if self.verbose:
            logger.info("Processing complete, writing data to files...")

        if include_observations and len(self.store.observations) == 0:
            raise HealthDataParseError("No relevant laboratory records found in exported Apple Health data")

        if len(self.custom_data_files) > 0:
            logger.info("The compiled information includes some custom data not exported from Apple Health:")
            for filename in self.custom_data_files:
                logger.info(filename)

        reporter = Reporter(self.verbose)
        if include_observations:
            reporter.report_abnormal_results_by_code_then_date(self.outputs.abnormal_results_by_code_text, self.store)
            reporter.report_abnormal_results_by_interpretation(
                self.outputs.abnormal_results_by_interpretation_csv, self.store, self.options)
            reporter.report_abnormal_results_by_date(self.outputs.abnormal_results_csv, self.store)
            reporter.report_all_data_by_datecode(self.outputs.all_data_csv, self.store)
        reporter.report_all_data_json_and_pdf(
            include_observations, self.outputs.all_data_json, self.output_dir, self.store, self.vital_signs,
            self.custom_data_files, self.options, vital_stats_graph=self.vital_stats_graph,
            symptom_charts=self.symptom_charts, food_chart=self.food_chart)
