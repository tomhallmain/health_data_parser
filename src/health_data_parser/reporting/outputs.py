import csv
from datetime import datetime
import json
import operator
import os
import traceback

from health_data_parser.errors import HealthDataParseError
from health_data_parser.model.reference_range import Interpretation
from health_data_parser.reporting.pdf.report import Report
from health_data_parser.utils.translations import _
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('reporter')

# Version of the observations.json layout; bump when consumers need to adapt
SCHEMA_VERSION = 1


def _csv_writer(csvfile):
    return csv.writer(csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)


class Reporter:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def report_abnormal_results_by_code_then_date(self, filepath, store):
        abnormal_results = store.abnormal_results
        if len(abnormal_results) == 0:
            logger.info("No abnormal results found from current data")
            return
        try:
            with open(filepath, "w", encoding="utf-8") as textfile:
                lines = ["|----- " + _("Laboratory Abnormal Results from Apple Health Data by Code") + " -----|", ""]
                for code in store.codes:
                    for code_id in store.code_ids(code):
                        if code_id not in abnormal_results:
                            continue
                        lines.append(_("Abnormal results found for code {0}:").format(code))
                        for observation in sorted(abnormal_results[code_id], key=operator.attrgetter("date")):
                            reference = observation.reference
                            if reference.is_range_type:
                                line = _("{0}: {1} - observed {2} - range {3}").format(
                                    observation.date, reference.interpretation.label,
                                    observation.value_string, reference.range)
                            else:
                                line = _("{0}: {1} - observed {2}").format(
                                    observation.date, reference.interpretation.label,
                                    observation.value_string)
                            lines.append(line)
                        lines.append("")
                for line in lines:
                    if self.verbose:
                        logger.info(line)
                    textfile.write(line + "\n")
            logger.info(f"Abnormal laboratory results data from Apple Health saved to {filepath}")
        except Exception:
            logger.error("An error occurred in writing abnormal results data.")
            if self.verbose:
                logger.error(traceback.format_exc())

    def report_abnormal_results_by_interpretation(self, filepath, store, options):
        abnormal_results = store.abnormal_results
        if len(abnormal_results) == 0:
            return
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                filewriter = _csv_writer(csvfile)
                interpretations = Interpretation.ordered(
                    include_in_range=not options.skip_in_range_abnormal_results)
                filewriter.writerow([_("Laboratory Abnormal Results by Interpretation from Apple Health Data")]
                                    + [i.label for i in interpretations])
                for code in store.codes:
                    found = {observation.reference.interpretation
                             for code_id in store.code_ids(code)
                             for observation in abnormal_results.get(code_id, [])}
                    if found:
                        filewriter.writerow([code] + [i.value if i in found else "" for i in interpretations])
            logger.info(f"Abnormal laboratory results data from Apple Health sorted by interpretation saved to {filepath}")
        except Exception:
            logger.error("An error occurred in writing abnormal results data.")
            if self.verbose:
                logger.error(traceback.format_exc())

    def report_abnormal_results_by_date(self, filepath, store):
        abnormal_results = store.abnormal_results
        if len(abnormal_results) == 0:
            logger.info("No abnormal results found from current data")
            return
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                filewriter = _csv_writer(csvfile)
                abnormal_dates = store.abnormal_dates
                filewriter.writerow([_("Laboratory Abnormal Results from Apple Health Data")] + abnormal_dates)
                for code in store.codes:
                    code_ids = [code_id for code_id in store.code_ids(code) if code_id in abnormal_results]
                    if not code_ids:
                        continue
                    row = [code]
                    for date in abnormal_dates:
                        observation = next((o for code_id in code_ids for o in abnormal_results[code_id]
                                            if o.date == date), None)
                        row.append("" if observation is None
                                   else observation.value_string + " " + observation.reference.tag)
                    filewriter.writerow(row)
            logger.info(f"Abnormal laboratory results data from Apple Health saved to {filepath}")
        except Exception:
            logger.error("An error occurred in writing abnormal results data to CSV.")
            if self.verbose:
                logger.error(traceback.format_exc())

    def report_all_data_by_datecode(self, filepath, store):
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                filewriter = _csv_writer(csvfile)
                dates = store.dates
                reference_dates = set(store.reference_dates)
                header = [_("Laboratory Observations from Apple Health Data")]
                for date in dates:
                    if date in reference_dates:
                        header.append(_("{0} range").format(date))
                    header.append(_("{0} result").format(date))
                filewriter.writerow(header)
                for code in store.codes:
                    row = [code]
                    for date in dates:
                        observation = store.find_for_code(code, date)
                        if observation is None:
                            row.append("")
                            if date in reference_dates:
                                row.append("")
                            continue
                        if date in reference_dates:
                            # The leading space stops Excel reading a range like "1-5" as a date
                            row.append(" " + observation.reference.range_text
                                       if observation.has_reference else "")
                        tag = " " + observation.reference.tag if observation.has_reference else ""
                        row.append(observation.value_string + tag)
                    filewriter.writerow(row)
            logger.info(f"Laboratory records data from Apple Health saved to {filepath}")
        except Exception as e:
            if self.verbose:
                logger.error(traceback.format_exc())
            raise HealthDataParseError(_("An error occurred in writing observations data to CSV.")) from e

    def report_all_data_json_and_pdf(self, include_observations, filepath, output_dir, store, vital_signs,
                                     custom_data_files, options, vital_stats_graph=None,
                                     symptom_charts=None, food_chart=None):
        try:
            json_data = build_json_data(include_observations, store, vital_signs, options)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, cls=_DateTimeEncoder, ensure_ascii=False, indent=4)
            logger.info(f"Laboratory records data from Apple Health saved to {filepath}")
        except Exception as e:
            if self.verbose:
                logger.error(traceback.format_exc())
            raise HealthDataParseError(_("An error occurred in writing observations data to JSON: {0}").format(e)) from e

        try:
            report = Report(output_dir, options.subject, json_data["meta"]["processTime"][:10],
                            self.verbose, options.report_highlight_abnormal_results)
            report.create_pdf(json_data, store, vital_stats_graph=vital_stats_graph,
                              symptom_charts=symptom_charts, food_chart=food_chart)
            logger.info(f"Results report saved to {os.path.join(output_dir, report.filename)}")
        except Exception as e:
            if self.verbose:
                logger.error(traceback.format_exc())
            raise HealthDataParseError(_("An error occurred in writing observations data to PDF report: {0}").format(e)) from e

        if self.verbose and len(custom_data_files) > 0:
            logger.info("The compiled information includes some custom data not exported from Apple Health:")
            for filename in custom_data_files:
                logger.info(filename)


def build_json_data(include_observations, store, vital_signs, options):
    """The observations.json content. Datetimes are left as datetime objects
    (the PDF uses them); the JSON encoder writes them as ISO 8601."""
    meta = {
        "schemaVersion": SCHEMA_VERSION,
        "description": "Health Records Report",
        "processTime": str(datetime.now()),
    }
    json_data = {"meta": meta}
    if not include_observations:
        return json_data

    dates = store.dates
    meta["observationCount"] = len(store.observations)
    meta["vitalSignsObservationCount"] = vital_signs.observation_count
    meta["mostRecentResult"] = dates[0]
    meta["earliestResult"] = dates[-1]
    meta["heartRateMonitoringWearableDetected"] = vital_signs.wearable_heart_rate_detected

    if vital_signs.observation_count > 0:
        json_data["vitalSigns"] = [series.to_dict(include_readings=options.json_add_all_vitals)
                                   for series in vital_signs.reported_series]

    abnormal_count = store.abnormal_count
    if abnormal_count > 0:
        json_data["abnormalResults"] = {
            "meta": {
                "codesWithAbnormalResultsCount": len(store.abnormal_results),
                "totalAbnormalResultsCount": abnormal_count,
                "includesInRangeAbnormalities": (options.in_range_abnormal_boundary > 0
                                                 and not options.skip_in_range_abnormal_results),
                "inRangeAbnormalBoundary": options.in_range_abnormal_boundary,
            },
            "codesWithAbnormalResults": store.interpretations_by_code(
                include_in_range=not options.skip_in_range_abnormal_results),
        }

    observations = [observation.to_dict() for observation in store.observations.values()]
    observations.sort(key=lambda obs: obs.get("date"))
    observations.reverse()
    json_data["observations"] = observations
    return json_data


class _DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
