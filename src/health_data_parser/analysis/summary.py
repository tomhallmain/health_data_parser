from collections import Counter
from datetime import datetime
import json
import os

from health_data_parser.model.reference_range import Interpretation
from health_data_parser.model.vitals import vital_label
from health_data_parser.utils.translations import _

OBSERVATIONS_JSON_FILENAME = "observations.json"


def load_observations_json(data_dir: str):
    """Return the parsed observations.json in data_dir, or {} if none exists yet."""
    path = os.path.join(data_dir, OBSERVATIONS_JSON_FILENAME)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _reference_range(observation: dict):
    return observation.get("observedResult", {}).get("referenceRange", {})


def _test_description(observation: dict):
    return observation.get("testMeta", {}).get("testDescription", "")


def summarize(json_data: dict):
    meta = json_data.get("meta", {})
    observations = json_data.get("observations", [])
    abnormal_meta = json_data.get("abnormalResults", {}).get("meta", {})
    return {
        "observation_count": meta.get("observationCount", len(observations)),
        "vital_signs_observation_count": meta.get("vitalSignsObservationCount", 0),
        "unique_test_count": len({_test_description(o) for o in observations if _test_description(o)}),
        "earliest_result": meta.get("earliestResult"),
        "most_recent_result": meta.get("mostRecentResult"),
        "abnormal_result_count": abnormal_meta.get("totalAbnormalResultsCount", 0),
        "codes_with_abnormal_results_count": abnormal_meta.get("codesWithAbnormalResultsCount", 0),
    }


def summary_lines(json_data: dict):
    summary = summarize(json_data)
    lines = [
        _("Total Observations: {0}").format(summary['observation_count']),
        _("Vital Signs Observations: {0}").format(summary['vital_signs_observation_count']),
        _("Unique Tests: {0}").format(summary['unique_test_count']),
    ]
    if summary["earliest_result"] and summary["most_recent_result"]:
        lines.append(_("Date Range: {0} to {1}").format(summary['earliest_result'], summary['most_recent_result']))
    lines.append(_("Abnormal Results: {0}").format(summary['abnormal_result_count']))
    lines.append(_("Tests With Abnormal Results: {0}").format(summary['codes_with_abnormal_results_count']))
    return lines


def result_status(observation: dict):
    """The abnormal interpretation's label, "Normal", or "" when there is no
    reference range (translated)."""
    reference_range = _reference_range(observation)
    if not reference_range:
        return ""
    if reference_range.get("isAbnormal"):
        return _interpretation_label(reference_range.get("interpretation")) or _("Abnormal")
    return _("Normal")


def _interpretation_label(text):
    """The translated label for an interpretation's English name in
    observations.json; unknown names as given."""
    interpretation = Interpretation.from_text(text)
    return interpretation.label if interpretation else text


def lab_result_rows(json_data: dict):
    """(date, test, value, expected range, status) per observation, in file order."""
    rows = []
    for observation in json_data.get("observations", []):
        rows.append((
            observation.get("date", ""),
            _test_description(observation),
            observation.get("observedResult", {}).get("valueString", ""),
            _reference_range(observation).get("expectedValue", ""),
            result_status(observation),
        ))
    return rows


def _round(value):
    return round(value, 1) if isinstance(value, (int, float)) else ""


def _item(values, i: int):
    return values[i] if isinstance(values, list) and i < len(values) else None


def vital_sign_rows(json_data: dict):
    """(vital, unit, most recent, most recent date, min, max, average, count) per vital.

    Blood pressure stores [systolic, diastolic] in each stat, so it yields one
    row per component, named by the vital's "labels".
    """
    rows = []
    for vital in json_data.get("vitalSigns", []):
        count = vital.get("count") or 0
        if count == 0:
            continue
        unit = vital.get("unit") or ""
        most_recent = vital.get("mostRecent")
        if not isinstance(most_recent, dict):
            most_recent = {}
        most_recent_value = most_recent.get("value")
        # Times are strings starting with the date: ISO 8601, or "%Y-%m-%d %X %z"
        # in files written before schemaVersion 1
        most_recent_date = str(most_recent.get("time") or "")[:10]
        if isinstance(most_recent_value, list):
            labels = vital.get("labels") or [vital.get("vital", "")] * len(most_recent_value)
            for i, value in enumerate(most_recent_value):
                rows.append((
                    vital_label(_item(labels, i) or ""), unit, _round(value), most_recent_date,
                    _round(_item(vital.get("min"), i)), _round(_item(vital.get("max"), i)),
                    _round(_item(vital.get("avg"), i)), count))
        else:
            rows.append((
                vital_label(vital.get("vital", "")), unit, _round(most_recent_value), most_recent_date,
                _round(vital.get("min")), _round(vital.get("max")),
                _round(vital.get("avg")), count))
    return rows


def observation_counts_by_year(json_data: dict):
    counts = Counter()
    for observation in json_data.get("observations", []):
        date = observation.get("date")
        if date:
            counts[date[:4]] += 1
    return sorted(counts.items())


def abnormal_counts_by_interpretation(json_data: dict):
    """(interpretation label, count) pairs ordered from low out of range to high
    out of range, then any other interpretations; labels translated."""
    counts = Counter()
    for observation in json_data.get("observations", []):
        reference_range = _reference_range(observation)
        if reference_range.get("isAbnormal"):
            counts[reference_range.get("interpretation")] += 1
    ordered = [interpretation.text for interpretation in Interpretation if interpretation.text in counts]
    ordered += sorted((text for text in counts if text not in ordered), key=lambda text: text or "")
    return [(_interpretation_label(text) or _("Unclassified"), counts[text]) for text in ordered]


def observation_counts_by_date(json_data: dict, abnormal_only=False):
    """(datetime, count) pairs in ascending date order."""
    counts = Counter()
    for observation in json_data.get("observations", []):
        date = observation.get("date")
        if not date:
            continue
        if abnormal_only and not _reference_range(observation).get("isAbnormal"):
            continue
        counts[date] += 1
    return [(datetime.fromisoformat(date), counts[date]) for date in sorted(counts)]
