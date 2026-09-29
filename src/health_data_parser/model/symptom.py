from copy import deepcopy
from datetime import datetime
import os

from health_data_parser.utils.logger import setup_logger

logger = setup_logger('symptom_set')


def parse_symptom_date(text: str):
    """The date a symptom CSV cell names: YYYY-MM-DD (day precision) or
    YYYY-MM (month precision, taken as the 1st). None for anything else, such
    as a blank cell or "Chronic"."""
    try:
        return datetime.fromisoformat(text[:10])
    except Exception:
        try:
            return datetime.strptime(text[:7], "%Y-%m")
        except Exception:
            return None


def split_list(text: str):
    """Comma-separated names, trimmed, as entered."""
    return [item.strip() for item in text.split(",") if item.strip()]


class Symptom:
    """One row of a symptom CSV: Name, Start Date, End Date, Medications,
    Stimulants, Comment, Severity.

    The start and end cells are kept as entered (start_text/end_text), so a
    month-only date or text like "Chronic" is written back unchanged;
    start_date/end_date are parsed from them. Medication and stimulant names
    keep their case.
    """

    def __init__(self, row):
        self.name = row[0]
        self.start_text = row[1].strip()
        self.end_text = row[2].strip()
        self.start_date = parse_symptom_date(self.start_text)
        self.end_date = parse_symptom_date(self.end_text)
        self.is_resolved = self.end_date is not None
        self.medications = split_list(row[3])
        self.stimulants = split_list(row[4])
        self.comment = row[5]
        self.severity = int(row[6])

    def to_row(self):
        return [self.name, self.start_text, self.end_text, ",".join(self.medications),
                ",".join(self.stimulants), self.comment, str(self.severity)]

    def get_end_date(self):
        if self.end_date is None:
            return datetime.today()
        else:
            return self.end_date

    def __str__(self):
        if self.start_date is None and self.end_date is None:
            return self.name + " (chronic)"
        elif self.start_date is None and self.end_date is not None:
            return self.name + " chronic until " + str(self.end_date)
        elif self.start_date is not None and self.end_date is None:
            return self.name + " chronic from " + str(self.start_date)
        else:
            return self.name + " " + str(self.start_date) + " " + str(self.end_date)


class SymptomSet:
    """The symptoms from a symptom CSV that the report covers: valid rows not
    resolved before `start_year`."""

    def __init__(self, symptom_data_loc: str, verbose=False, start_year=1970):
        # Imported here: ingest.symptoms_csv builds Symptom objects from this module
        from health_data_parser.ingest.symptoms_csv import read_symptoms

        self.symptom_data_loc = symptom_data_loc
        self.verbose = verbose
        self.start_year = 1970 if start_year is None else start_year
        self.has_chronic_conditions_from_start = False
        self.symptoms = []
        self.dates_recorded = []
        self.severities = []
        self.record_count = 0

        if (os.path.exists(self.symptom_data_loc)
                and self.symptom_data_loc[-4:] == ".csv"):
            if self.verbose:
                logger.info(f"Using symptom data file: {self.symptom_data_loc}")
        else:
            logger.warning(f"Symptom data CSV file {self.symptom_data_loc} is invalid, skipping symptom analysis.")
            return

        try:
            symptoms, errors = read_symptoms(self.symptom_data_loc)
        except Exception as e:
            if verbose:
                logger.error(str(e))
            logger.warning(f"Failed to parse symptom data CSV file {self.symptom_data_loc}, ensure the file is consistent with sample - skipping symptom reporting.")
            return

        if self.verbose:
            for row_number, error in errors:
                logger.error(f"Symptom row {row_number}: {error}")

        for symptom in symptoms:
            if symptom.end_date is not None and symptom.end_date.year < self.start_year:
                continue
            self.symptoms.append(symptom)
            if symptom.start_date is None:
                self.has_chronic_conditions_from_start = True
            elif symptom.start_date not in self.dates_recorded:
                self.dates_recorded.append(symptom.start_date)
            if symptom.severity not in self.severities:
                self.severities.append(symptom.severity)
            self.record_count += 1

        self.dates_recorded.sort()
        self.severities.sort()

        if errors:
            logger.warning("Some symptom records were invalid and could not be processed - ensure file is consistent with sample.")

    def has_both_resolved_and_unresolved_symptoms(self):
        return any([not symptom.is_resolved for symptom in self.symptoms]) \
                and any([symptom.is_resolved for symptom in self.symptoms])

    def get_filtered_symptoms(self, include_historical_symptoms=False):
        if include_historical_symptoms:
            return deepcopy(self.symptoms)
        else:
            return [deepcopy(symptom) for symptom in self.symptoms if not symptom.is_resolved]
