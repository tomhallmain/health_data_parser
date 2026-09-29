from dataclasses import dataclass
import json
import os
import re
import traceback

from health_data_parser.model.lab_test import LabTest
from health_data_parser.model.observation import Observation, SkipObservation
from health_data_parser.model.observation_store import ObservationStore
from health_data_parser.model.reference_range import reference_range_or_none
from health_data_parser.model.units import VitalSignCategory
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('observation_json_parser')

VITAL_SIGNS_CATEGORY = "Vital Signs"
# Observation categories handled as vital signs rather than lab results
VITAL_SIGN_CATEGORIES = [VITAL_SIGNS_CATEGORY] + [c.value for c in VitalSignCategory]
DISALLOWED_CODES = ["NARRATIVE", "REQUEST PROBLEM"]

_LOINC = "http://loinc.org"
_SYSTOLIC_CODE = "8480-6"
_DIASTOLIC_CODE = "8462-4"
_LONG_VALUE_LENGTH = 200


@dataclass(frozen=True)
class ObservationRules:
    """The options that decide whether and how an observation is recorded."""
    start_year: int | None = None
    skip_long_values: bool = False
    skip_in_range_abnormal_results: bool = False
    in_range_abnormal_boundary: float = 0.15

    @classmethod
    def from_options(cls, options):
        return cls(options.start_year, options.skip_long_values,
                   options.skip_in_range_abnormal_results, options.in_range_abnormal_boundary)

    def reference_range(self, range_text, value, value_string, unit, check_units_match=False):
        return reference_range_or_none(
            range_text, value, value_string, unit,
            skip_in_range_abnormal_results=self.skip_in_range_abnormal_results,
            abnormal_boundary=self.in_range_abnormal_boundary,
            check_units_match=check_units_match)


def observation_category(data: dict):
    if "text" in data["category"]:
        return data["category"]["text"]
    return data["category"]["coding"][0]["code"]


def parse_observation(data: dict, obs_id: str, store: ObservationStore, rules: ObservationRules,
                      disallowed_codes=DISALLOWED_CODES):
    """Build an Observation from a FHIR Observation resource.

    Raises SkipObservation for results the report leaves out: no value, before
    the start year, a disallowed code, a date + test already recorded in
    `store`, or an unusable value. Malformed resources raise other errors
    (KeyError for missing fields, ValueError from LabTest for a code with no
    description or id). When the test matches one already in `store` (a
    shared coding), the observation uses that LabTest and adds its codings to
    it.
    """
    if "valueString" not in data and "valueQuantity" not in data and "component" not in data:
        raise SkipObservation("Observation value not found")

    category = observation_category(data)
    date = data["effectiveDateTime"][0:10]
    if rules.start_year is not None and int(date[0:4]) < rules.start_year:
        raise SkipObservation("Observation year is before start year")

    test = LabTest(data["code"].get("text"), data["code"])
    if test.test_desc.upper() in disallowed_codes:
        raise SkipObservation("Skipping observation for code " + test.test_desc)
    test = _saved_test(test, data["code"], store)
    if store.is_recorded(date + test.primary_id):
        raise SkipObservation(f"Datecode {date + test.primary_id} for code {test.test_desc} already recorded")

    value, value2, value_string, unit = _parse_value(data)
    value_string = _clean_value_string(value_string, date, test.test_desc, rules.skip_long_values)

    reference = None
    if "referenceRange" in data:
        reference = rules.reference_range(data["referenceRange"][0].get("text"), value,
                                          value_string, unit)

    return Observation(obs_id=obs_id, date=date, category=category, test=test, value=value,
                       value_string=value_string, unit=unit, value2=value2, reference=reference,
                       comment=data.get("comments"))


def _saved_test(test: LabTest, code: dict, store: ObservationStore):
    """The test already in `store` that `test` matches (with `code`'s codings
    added to it), or `test` itself if it's new."""
    for saved_test in store.tests:
        if test.matches(saved_test):
            saved_test.add_coding(code)
            return saved_test
    return test


def _parse_value(data: dict):
    """(value, value2, value_string, unit) from a FHIR Observation's value."""
    if "valueString" in data:
        return None, None, data["valueString"], None

    if "valueQuantity" in data:
        value_quantity = data["valueQuantity"]
        raw_value = value_quantity["value"]
        number = None
        if isinstance(raw_value, str):
            match = re.search(r"(\d+\.\d+|\d+)", raw_value)
            if match:
                number = match.group(1)
        elif raw_value is not None:
            number = raw_value
        value = float(number) if number is not None else None
        value_string = str(raw_value)
        unit = value_quantity.get("unit")
        if unit is not None:
            value_string += " " + unit
        return value, None, value_string, unit

    # Blood pressure: systolic and diastolic LOINC components
    systolic = diastolic = unit = None
    for component in data["component"]:
        if not ("code" in component
                and "valueQuantity" in component
                and "value" in component["valueQuantity"]
                and "coding" in component["code"]
                and len(component["code"]["coding"]) > 0
                and component["code"]["coding"][0].get("system") == _LOINC
                and "code" in component["code"]["coding"][0]):
            continue
        component_code = component["code"]["coding"][0]["code"]
        if component_code == _SYSTOLIC_CODE:
            systolic = float(component["valueQuantity"]["value"])
        elif component_code == _DIASTOLIC_CODE:
            diastolic = float(component["valueQuantity"]["value"])
        if "unit" in component["valueQuantity"]:
            unit = component["valueQuantity"]["unit"]
    if systolic is None or diastolic is None:
        raise SkipObservation("Systolic or Diastolic value not found for assumed blood pressure observation.")
    value_string = f"{systolic}/{diastolic} {unit if unit is not None else 'mm[Hg]'}"
    return systolic, diastolic, value_string, unit


def _clean_value_string(value_string, date, code, skip_long_values):
    """`value_string` without a "SEE BELOW" pointer to text elsewhere in the
    report; raises SkipObservation if nothing usable is left or it's too long."""
    unparseable = SkipObservation(
        f"Skipping observation with unparseable value for [date / code] {date} / {code}")
    if value_string is None or value_string == "" or not re.search("[A-z0-9]", value_string):
        raise unparseable
    if "SEE BELOW" in value_string or "See Below" in value_string:
        for marker in ["SEE BELOW\n\n", "SEE BELOW\n", "SEE BELOW",
                       "See Below\n\n", "See Below\n", "See Below"]:
            value_string = value_string.replace(marker, "")
        if not re.search("[A-z0-9]", value_string):
            raise unparseable
    elif skip_long_values and len(value_string) > _LONG_VALUE_LENGTH:
        raise SkipObservation(
            f"Skipping observation with excessively long value for [date / code] {date} / {code}")
    return value_string


class ClinicalRecordsParser:
    """Reads the FHIR Observation and DiagnosticReport files in an export's
    clinical-records folder, plus any custom DiagnosticReports built in
    memory (from --extra_observations), into an ObservationStore."""

    def __init__(self, options, custom_data_files, store=None, custom_reports=None):
        self.options = options
        self.verbose = options.verbose
        self.base_dir = options.base_dir
        self.subject = options.subject
        self.skip_dates = options.skip_dates
        self.rules = ObservationRules.from_options(options)
        self.custom_data_files = custom_data_files
        self.store = store if store is not None else ObservationStore()
        # Report id -> DiagnosticReport
        self.custom_reports = custom_reports or {}

    def parse(self):
        logger.info("Parsing clinical-records JSON...")
        for f in os.listdir(self.base_dir):
            # Records are named "<ResourceType>-<id>.json"; anything else (e.g.
            # .DS_Store) gets a category matching neither branch and is skipped
            file_category = f.split("-", 1)[0]
            f_addr = os.path.join(self.base_dir, f)
            if file_category == "Observation":
                with open(f_addr, encoding="utf-8") as file:
                    file_data = json.load(file)
                self._note_subject(file_data)
                self._process_safely(file_data, f)
            elif file_category == "DiagnosticReport":
                with open(f_addr, encoding="utf-8") as file:
                    file_data = json.load(file)
                if "-CUSTOM" in f_addr:
                    # Written into the export by earlier versions of this app;
                    # the in-memory version of the same report replaces it
                    if file_data.get("id") in self.custom_reports:
                        if self.verbose:
                            logger.info(f"Skipping {f}: superseded by extra observations data")
                        continue
                    self.custom_data_files.append(f_addr)
                self._parse_diagnostic_report(file_data, f)
        for report_id, report in self.custom_reports.items():
            self._parse_diagnostic_report(report, f"DiagnosticReport-{report_id}-CUSTOM")
        return self.store

    def _parse_diagnostic_report(self, report, name):
        if report["category"]["coding"][0]["code"] not in ["Lab", "LAB"]:
            return
        # Some Diagnostic Report files have multiple results contained.
        # Their ids number them in order, but an index is reused after
        # a result that failed, was on a skipped date, or was an
        # unidentified vital sign.
        if "contained" in report:
            i = 0
            for observation in report["contained"]:
                if self._process_safely(observation, name + "[" + str(i) + "]"):
                    i += 1
        else:
            self._process_safely(report, name)

    def _note_subject(self, file_data):
        if "name" not in self.subject and "subject" in file_data:
            subject_data = file_data["subject"]
            if subject_data is not None and subject_data.get("display") is not None:
                self.subject["name"] = subject_data["display"]
                if self.verbose:
                    logger.info(f"Identified subject: {self.subject['name']}")

    def _process_safely(self, data, obs_id):
        """Process one observation; returns whether its id is used (see parse)."""
        try:
            return self.process_observation(data, obs_id)
        except Exception as e:
            logger.error(f"Error processing observation {obs_id}: {e!r}")
            if self.verbose:
                logger.error(traceback.format_exc())
            return False

    def process_observation(self, data: dict, obs_id: str):
        """Record one observation if the report includes it.

        Returns False when the observation is on a skipped date or is an
        unidentified vital sign, the cases that don't use up a contained
        result's id; True otherwise, whether or not it was recorded.
        """
        if observation_category(data) in VITAL_SIGN_CATEGORIES:
            return self._process_vital_sign(data, obs_id)
        try:
            obs = parse_observation(data, obs_id, self.store, self.rules)
        except SkipObservation as e:
            if self.verbose:
                logger.info(f"Skipped observation {obs_id}: {e}")
            return True
        if obs.date in self.skip_dates:
            if self.verbose:
                logger.info(f"Skipping observation on date {obs.date}")
            return False
        self.store.add(obs)
        if self.verbose:
            logger.info(f"Observation recorded for {obs.code} on {obs.date}")
        return True

    def _process_vital_sign(self, data: dict, obs_id: str):
        try:
            obs = parse_observation(data, obs_id, self.store, self.rules, disallowed_codes=())
        except SkipObservation as e:
            if self.verbose:
                logger.info(f"Skipped vital sign observation {obs_id}: {e}")
            return True
        if obs.date in self.skip_dates:
            if self.verbose:
                logger.info(f"Skipping observation on date {obs.date}")
            return False

        # "Vital Signs" observations name the vital in their code; others in their category
        text = obs.code if obs.category == VITAL_SIGNS_CATEGORY else obs.category
        obs.vital_sign_category = next(
            (category for category in VitalSignCategory if text and category.matches(text)), None)
        if obs.vital_sign_category is None:
            if self.verbose:
                logger.info(f"Vital sign observation category not identified: {obs.category} / {obs.code}")
            return False

        self.store.add_vital(obs)
        if self.verbose:
            logger.info(f"Vital sign observation recorded for {obs.code} on {obs.date}")
        return True
