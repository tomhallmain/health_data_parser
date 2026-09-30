import calendar
from dataclasses import dataclass
from datetime import datetime
import os

import matplotlib.dates as mdates
import matplotlib.lines as mlines
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure

from health_data_parser.utils.translations import _

MARKERS = [".", "o", "v", "^", "<", ">", "1", "2", "3", "4", "8", "s", "p",
           "P", "*", "h", "H", "+", "x", "X", "D", "d", "|", "_",
           0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


@dataclass
class SymptomCharts:
    symptoms: object
    all_symptoms_path: str
    # Only drawn when there are both resolved and unresolved symptoms
    unresolved_path: str | None


def save_symptom_charts(symptom_set, output_dir):
    """Draw the symptom timeline charts into output_dir; None when there are
    no symptoms to chart."""
    if not symptom_set.symptoms:
        return None
    chart_start = chart_start_date(symptom_set)
    all_path = os.path.join(output_dir, "symptoms.png")
    _save_timeline(symptom_set, symptom_set.get_filtered_symptoms(include_historical_symptoms=True),
                   chart_start, all_path)
    unresolved_path = None
    if symptom_set.has_both_resolved_and_unresolved_symptoms():
        unresolved_path = os.path.join(output_dir, "symptoms_unresolved.png")
        _save_timeline(symptom_set, symptom_set.get_filtered_symptoms(include_historical_symptoms=False),
                       chart_start, unresolved_path)
    return SymptomCharts(symptom_set, all_path, unresolved_path)


def _shift_date(date, years=0, months=0):
    """`date` moved by whole years/months, with the day clamped to the
    target month's length."""
    month_index = date.year * 12 + (date.month - 1) + years * 12 + months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)


def chart_start_date(symptom_set):
    """The earliest recorded start date (3 months earlier when some symptoms
    have no start date), or 3 years ago with no start dates; never before the
    start year."""
    if symptom_set.dates_recorded:
        start = symptom_set.dates_recorded[0]
        if symptom_set.has_chronic_conditions_from_start:
            start = _shift_date(start, months=-3)
    else:
        start = _shift_date(datetime.today(), years=-3)
    if symptom_set.start_year is not None and symptom_set.start_year > start.year:
        start = datetime(symptom_set.start_year, 1, 1)
    return start


def _save_timeline(symptom_set, symptoms, chart_start, path):
    """A bar per symptom from start to end (or today), grouped by name and
    sorted by severity, with markers for its stimulants before the bar and
    its medications after."""
    chart_span_days = (datetime.today() - chart_start).days

    def start_of(symptom):
        if symptom.start_date is None or symptom.start_date < chart_start:
            return chart_start
        return symptom.start_date

    severity_colors = {severity: "C" + str(i) for i, severity in enumerate(symptom_set.severities)}

    # Case-insensitive name -> {"label", "color", "marker", "positions"}; stimulants
    # and medications share one color/marker sequence
    counter = 0
    stimulant_info = {}
    medication_info = {}
    for info, names_of in [(stimulant_info, lambda s: s.stimulants), (medication_info, lambda s: s.medications)]:
        for symptom in symptoms:
            for name in names_of(symptom):
                if name.casefold() not in info:
                    info[name.casefold()] = {"label": name, "color": "C" + str(counter),
                                             "marker": MARKERS[counter % len(MARKERS)], "positions": []}
                    counter += 1

    symptoms = sorted(sorted(symptoms, key=start_of, reverse=True),
                      key=lambda s: s.severity, reverse=False)

    bar_verts = []
    bar_colors = []
    row_by_name = {}
    for symptom in symptoms:
        row = row_by_name.setdefault(symptom.name, len(row_by_name) + 1)
        start = mdates.date2num(start_of(symptom))
        end = mdates.date2num(symptom.get_end_date())
        bar_verts.append([(start, row - .4), (start, row + .4), (end, row + .4),
                          (end, row - .4), (start, row - .4)])
        bar_colors.append(severity_colors[symptom.severity])

        offset = chart_span_days / 70
        for name in symptom.stimulants:
            stimulant_info[name.casefold()]["positions"].append((start - offset, row))
            offset += chart_span_days / 50
        offset = chart_span_days / 70
        for name in symptom.medications:
            medication_info[name.casefold()]["positions"].append((start + offset, row))
            offset += chart_span_days / 50

    fig = Figure()
    ax = fig.subplots()
    ax.add_collection(PolyCollection(bar_verts, facecolors=bar_colors))
    ax.autoscale()
    loc = mdates.MonthLocator(bymonth=[1, 7])
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(loc))
    ax.set_yticks(list(row_by_name.values()))
    ax.set_yticklabels(list(row_by_name))

    handles = {}
    for kind, info in [("stimulant", stimulant_info), ("medication", medication_info)]:
        handles[kind] = []
        for entry in info.values():
            handles[kind].append(mlines.Line2D(
                [], [], color=entry["color"], marker=entry["marker"], linestyle='None',
                markersize=10, label=entry["label"]))
            for x, y in entry["positions"]:
                ax.plot(x, y, marker=entry["marker"], color=entry["color"], markeredgecolor="black")
    stimulant_legend = ax.legend(bbox_to_anchor=(0, -0.05, 1, 0), loc="upper left",
                                 handles=handles["stimulant"],
                                 title=_("PRIMARY CAUSE / STIMULANT"), ncol=4, prop={"size": 7})
    ax.legend(bbox_to_anchor=(-0.4, -0.05, 1, 0), loc="upper left",
              handles=handles["medication"],
              title=_("MEDICATION / TREATMENT"), ncol=2, prop={"size": 7})
    ax.add_artist(stimulant_legend)
    fig.set_size_inches(11, 9)
    fig.savefig(path, pad_inches=0.02, bbox_inches='tight')
