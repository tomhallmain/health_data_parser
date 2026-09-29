import csv

from health_data_parser.model.symptom import Symptom
from health_data_parser.utils.csv_files import read_csv_rows

# Written by the symptom manager
HEADER = ["Name", "Start Date", "End Date", "Medications", "Stimulants", "Comment", "Severity"]
# sample_templates/sample_symptoms_data.csv; same columns, different names
TEMPLATE_HEADER = ["Symptom/Condition", "Onset/Time of Diagnosis", "Conclusion", "Medications",
                   "Stimulants", "Comment", "Severity"]


class InvalidSymptomFile(ValueError):
    """The file's header isn't one of the known symptom CSV headers."""


def read_symptoms(path, require_known_header=False):
    """(symptoms, errors) from a symptom CSV, where errors lists
    (row number, message) for rows that couldn't be read.

    The first row is the header. With `require_known_header`, a header other
    than HEADER or TEMPLATE_HEADER raises InvalidSymptomFile.
    """
    rows = read_csv_rows(path)
    if not rows:
        return [], []
    header, *data = rows
    if require_known_header and [cell.strip() for cell in header] not in (HEADER, TEMPLATE_HEADER):
        raise InvalidSymptomFile("Invalid CSV format. Expected columns: " + ", ".join(HEADER))
    symptoms = []
    errors = []
    for row_number, row in enumerate(data, start=2):
        try:
            symptoms.append(Symptom(row))
        except Exception as e:
            errors.append((row_number, str(e)))
    return symptoms, errors


def write_symptoms(path, symptoms):
    # utf-8-sig: the byte order mark lets Excel detect UTF-8
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for symptom in symptoms:
            writer.writerow(symptom.to_row())
