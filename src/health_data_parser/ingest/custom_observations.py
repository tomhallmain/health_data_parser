from glob import glob
import json
import os
import traceback
import uuid

from health_data_parser.errors import HealthDataParseError
from health_data_parser.ingest.fhir_json import ObservationRules, parse_observation
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.utils.csv_files import read_csv_rows
from health_data_parser.utils.translations import _
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('diagnostic_report_generator')



def validate_csv_file(observation_data_csv: str):
    if observation_data_csv is None or observation_data_csv == "":
        raise HealthDataParseError(_("Missing custom observation results CSV file."))
    elif (not os.path.exists(observation_data_csv)
          or os.path.isdir(observation_data_csv)
          or observation_data_csv[-4:] != ".csv"):
        raise HealthDataParseError(
            _("Custom observation results CSV file \"{0}\" is invalid.").format(observation_data_csv))


def generate_report_id(subject: str, performer: str, date: str, report_desc: str):
    report_id = subject.replace(" ", "").replace(",", "").replace("-", "")
    report_id += "."
    report_id += performer.replace(" ", "").replace(",",
                                                    "").replace("-", "").replace("/", "")
    report_id += "."
    report_id += date
    report_id += "."
    report_id += report_desc.replace(" ", "").replace(",",
                                                      "").replace("-", "").replace("/", "")
    return report_id


def construct_observation(_id, subject, date, code_description, loinc_code, _range, value, units):
    observation = {}
    observation["id"] = _id
    observation["status"] = "final"
    observation["category"] = {"coding": [
        {"system": "http://hl7.org/fhir/observation-category", "code": "laboratory"}]}
    observation["subject"] = {"display": subject}
    observation["effectiveDateTime"] = date + "T12:00:00+00:00"
    observation["issued"] = date + "T12:00:00+00:00"
    observation["resourceType"] = "Observation"
    observation["meta"] = {
        "profile": "http://fhir.org/guides/argonaut/StructureDefinition/argo-observationresults"}
    coding = {}

    if loinc_code != "":
        coding["system"] = "http://loinc.org"
        coding["display"] = code_description
        coding["code"] = loinc_code
    else:
        coding["system"] = "CUSTOM"
        coding["display"] = code_description
        coding["code"] = code_description

    observation["code"] = {"coding": [coding]}

    if _range != "":
        low_high = _range.split("-")
        if "." in _range:
            range_low = float(low_high[0].strip())
            range_high = float(low_high[1].strip())
        else:
            range_low = int(low_high[0].strip())
            range_high = int(low_high[1].strip())

        if units == "":
            observation["referenceRange"] = [{
                    "low": {"value": range_low},
                    "high": {"value": range_high},
                    "text": _range
                }]
        else:
            observation["referenceRange"] = [{
                    "low": {"value": range_low, "unit": units},
                    "high": {"value": range_high, "unit": units},
                    "text": _range + " " + units
                }]

    if isinstance(value, str):
        if "." in value:
            value_quantity = float(value)
        else:
            value_quantity = int(value)
    else:
        value_quantity = value

    if units == "":
        observation["valueQuantity"] = {"value": value_quantity}
    else:
        observation["valueQuantity"] = {
                "value": value_quantity,
                "system": "http://lca.unitsofmeasure.org",
                "unit": units
            }

    return observation


def save_reports_to_json(reports, base_dir, verbose):
    has_saved_report = False
    has_error_in_report = False

    # If file is already saved for this report, delete the previous version
    for _file in glob(os.path.join(base_dir, "*-CUSTOM.json")):
        try:
            file_data = json.load(open(_file))
            if "id" in file_data and file_data["id"] in reports:
                logger.warning(f"Removing previous version of custom DiagnosticReport: {_file}")
                os.remove(_file)
        except Exception as e:
            if verbose:
                logger.error(str(e))

    for report_id in reports:
        try:
            report = reports[report_id]
            # Save JSON
            _uuid = str(uuid.uuid4())
            report_filename = "DiagnosticReport-" + _uuid + "-CUSTOM.json"
            report_path = os.path.join(base_dir, report_filename)
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
                if verbose:
                    logger.info(f"Saved file: {report_path}")
            has_saved_report = True

            with open(report_path, encoding="utf-8") as f:
                validate_report(json.load(f), report_filename)
        except Exception as e:
            if verbose:
                logger.error(traceback.format_exc())
                logger.error(str(e))
            has_error_in_report = True

    if not has_saved_report:
        logger.warning("No reports were saved.")

    return not has_error_in_report


def validate_report(report, name):
    """Raise if any result in the report can't be recorded as a lab result
    (SkipObservation, or an error for a malformed result)."""
    for i, observation in enumerate(report["contained"]):
        parse_observation(observation, name + "[" + str(i) + "]",
                          ObservationStore(), ObservationRules(), disallowed_codes=())


def build_custom_reports(observation_data_csv: str):
    """DiagnosticReport resources by report id, one per subject + performer +
    date + report description in a custom observations CSV, each containing
    its rows' Observations. Raises for a row that can't be read."""
    reports = {}
    rows = read_csv_rows(observation_data_csv)
    for row in rows[1:]:  # after the header
        subject = row[0]
        performer = row[1]
        date = row[2]
        report_description = row[3]
        loinc_code = row[4]
        code_description = row[5]
        value = float(row[6])
        _range = row[7]
        units = row[8]

        report_id = generate_report_id(subject, performer, date, report_description)
        if report_id not in reports:
            reports[report_id] = {
                "id": report_id,
                "status": "final",
                "category": {"coding": [{"system": "http://hl7.org/fhir/v2/0074", "code": "LAB"}]},
                "subject": {"display": subject},
                "performer": {"display": performer},
                "effectiveDateTime": date + "T12:00:00+00:00",
                "issued": date + "T12:00:00+00:00",
                "resourceType": "DiagnosticReport",
                "identifier": [{"id": report_id, "system": "CUSTOM"}],
                "meta": {
                    "profile": ["http://fhir.org/guides/argonaut/StructureDefinition/argo-diagnosticreport"],
                    "lastUpdated": "2021-07-14T13:35:46.000+00:00",
                },
                "contained": [],
                "result": [],
            }
        report = reports[report_id]
        observation_id = str(len(report["contained"]) + 1)
        report["contained"].append(construct_observation(
            observation_id, subject, date, code_description, loinc_code, _range, value, units))
        report["result"].append({"reference": "#" + observation_id})
    return reports


def load_custom_reports(observation_data_csv: str, verbose=False):
    """The custom observations CSV's reports, validated, without writing
    anything. None when the file has no rows or a row or result can't be used;
    raises HealthDataParseError for a missing or non-CSV path."""
    validate_csv_file(observation_data_csv)
    try:
        reports = build_custom_reports(observation_data_csv)
        if not reports:
            logger.warning(f"No observations data found in {observation_data_csv}")
            return None
        for report_id, report in reports.items():
            validate_report(report, report_id)
        return reports
    except Exception as e:
        logger.error(f"Custom observations data \"{observation_data_csv}\" can't be used: {e!r}")
        if verbose:
            logger.error(traceback.format_exc())
        return None


def generate_diagnostic_report_files(observation_data_csv: str, base_dir: str, verbose: bool):
    """Write the custom observations CSV's reports as DiagnosticReport JSON
    files into base_dir, replacing earlier files for the same reports; False
    when the file has no rows or a row or report can't be used."""
    validate_csv_file(observation_data_csv)
    try:
        reports = build_custom_reports(observation_data_csv)
    except Exception as e:
        if verbose:
            logger.error(traceback.format_exc())
            logger.error(str(e))
        return False
    if not reports:
        logger.warning(f"No observations data found in {observation_data_csv}")
        return False
    return save_reports_to_json(reports, base_dir, verbose)
