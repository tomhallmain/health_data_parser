import csv
from datetime import datetime
import os
import matplotlib.dates as mdates
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection


markers = [".", "o", "v", "^", "<", ">", "1", "2", "3", "4", "8", "s", "p",
           "P", "*", "h", "H", "+", "x", "X", "D", "d", "|", "_",
           0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


class Symptom:
    def __init__(self, row):
        self.name = row[0]
        self.start_date = None
        self.end_date = None
        alt_datetime_format = "%Y-%m"

        try:
            self.start_date = datetime.fromisoformat(row[1][:10])
        except Exception:
            try:
                self.start_date = datetime.strptime(
                    row[1][:7], alt_datetime_format)
            except Exception:
                pass

        try:
            self.end_date = datetime.fromisoformat(row[2][:10])
        except Exception:
            try:
                self.end_date = datetime.strptime(
                    row[2][:7], alt_datetime_format)
            except Exception:
                pass

        self.is_resolved = self.end_date is not None
        self.medications = [
            x.strip() for x in row[3].upper().split(",") if x != ""]
        self.stimulants = [
            x.strip() for x in row[4].upper().split(",") if x != ""]
        self.comment = row[5]
        self.severity = int(row[6])

    def get_end_date(self):
        if self.end_date is None:
            return datetime.today()
        else:
            return self.end_date


class SymptomSet:
    def __init__(self, symptom_data_loc: str, verbose=False, start_year=1970):
        self.symptom_data_loc = symptom_data_loc
        self.verbose = verbose
        self.start_year = 1970 if start_year is None else start_year
        self.to_print = False
        self.has_chronic_conditions_from_start = False
        self.symptoms = []
        self.dates_recorded = []
        self.severities = []
        self.record_count = 0
        all_symptom_records_valid = True

        if (os.path.exists(self.symptom_data_loc)
                and self.symptom_data_loc[-4:] == ".csv"):
            if self.verbose:
                print("Using symptom data file: " + self.symptom_data_loc)
        else:
            print("WARNING: Symptom data CSV file " + self.symptom_data_loc
                  + " is invalid, skipping symptom analysis.")
            return

        try:
            with open(self.symptom_data_loc, "r") as f:
                reader = csv.reader(f, delimiter=',', quotechar='"')
                has_seen_header = False
                for row in reader:
                    symptom = None
                    if not has_seen_header:
                        has_seen_header = True
                        continue
                    try:
                        symptom = Symptom(row)
                    except Exception as e:
                        all_symptom_records_valid = False
                        if self.verbose:
                            print(e)
                    if (symptom is None
                            or (symptom.end_date is not None
                                and symptom.end_date.year < self.start_year)):
                        continue
                    self.symptoms.append(symptom)
                    if symptom.start_date is None:
                        self.has_chronic_conditions_from_start = True
                    elif symptom.start_date not in self.dates_recorded:
                        self.dates_recorded.append(symptom.start_date)
                    if symptom.severity not in self.severities:
                        self.severities.append(symptom.severity)
                    self.record_count += 1
        except Exception as e:
            if verbose:
                print(e)
            print("WARNING: Failed to parse symptom data CSV file "
                  + self.symptom_data_loc + ", ensure the file is consistent"
                  + " with sample - skipping symptom reporting.")
            return

        self.dates_recorded.sort()
        self.severities.sort()

        if not all_symptom_records_valid:
            print("WARNING: Some symptom records were invalid and could not"
                  + " be processed - ensure file is consistent with sample.")

    def set_chart_start_date(self):
        if len(self.dates_recorded) > 0:
            if self.has_chronic_conditions_from_start:
                ref_date = self.dates_recorded[0]
                if ref_date.month - 3 < 1:
                    self.chart_start_date = datetime(
                        ref_date.year - 1, ref_date.month + 9, ref_date.day)
                else:
                    self.chart_start_date = datetime(
                        ref_date.year, ref_date.month - 3, ref_date.day)
            else:
                self.chart_start_date = self.dates_recorded[0]
        else:
            ref_date = datetime.today()
            self.chart_start_date = datetime(
                ref_date.year - 3, ref_date.month, ref_date.day)

        if (self.start_year is not None
                and self.start_year > self.chart_start_date.year):
            self.chart_start_date = datetime(self.start_year, 1, 1)

        self.chart_span_days = (datetime.today() - self.chart_start_date).days

    def get_start_date(self, symptom):
        if symptom.start_date is not None:
            if symptom.start_date < self.chart_start_date:
                return self.chart_start_date
            else:
                return symptom.start_date
        else:
            return self.chart_start_date

    def generate_chart_data(self):
        severity_colors = {}
        counter = 0

        for severity in self.severities:
            severity_colors[severity] = "C" + str(counter)
            counter += 1

        counter = 0
        self.stimulant_info = {}
        self.medication_info = {}

        for symptom in self.symptoms:
            for cause in symptom.stimulants:
                if cause not in self.stimulant_info:
                    self.stimulant_info[cause] = {"color": "C" + str(counter)}
                    self.stimulant_info[cause]["positions"] = []
                    self.stimulant_info[cause]["marker"] = \
                        markers[counter % len(markers)]
                    counter += 1

        for symptom in self.symptoms:
            for medication in symptom.medications:
                if medication not in self.medication_info:
                    self.medication_info[medication] = {
                        "color": "C" + str(counter)}
                    self.medication_info[medication]["positions"] = []
                    self.medication_info[medication]["marker"] = \
                        markers[counter % len(markers)]
                    counter += 1

        counter = 0
        self.symptoms = sorted(sorted(self.symptoms,
                                      key=lambda s: self.get_start_date(s),
                                      reverse=True),
                               key=lambda s: s.severity, reverse=True)

        bar_verts = []
        bar_colors = []
        seen_symptom_index = {}
        self.seen_symptom_counts = 0

        for symptom in self.symptoms:
            counter += 1
            if symptom.name in seen_symptom_index:
                index = seen_symptom_index[symptom.name]
                self.seen_symptom_counts += 1
            else:
                seen_symptom_index[symptom.name] = counter
                index = counter
            start_date = mdates.date2num(self.get_start_date(symptom))
            end_date = mdates.date2num(symptom.get_end_date())
            v = [(start_date, index-.4),
                 (start_date, index+.4),
                 (end_date, index+.4),
                 (end_date, index-.4),
                 (start_date, index-.4)]
            bar_verts.append(v)
            bar_colors.append(severity_colors[symptom.severity])
            stimulant_marker_offset = self.chart_span_days / 70

            for cause in symptom.stimulants:
                self.stimulant_info[cause]["positions"].append(
                    (start_date - stimulant_marker_offset, index))
                stimulant_marker_offset += self.chart_span_days / 50

            medication_marker_offset = self.chart_span_days / 70

            for medication in symptom.medications:
                self.medication_info[medication]["positions"].append(
                    (start_date + medication_marker_offset, index))
                medication_marker_offset += self.chart_span_days / 50

        self.bars = PolyCollection(bar_verts, facecolors=bar_colors)

    def save_chart(self, graph_cutoff: int, base_dir: str):
        self.save_loc = os.path.join(base_dir, "symptoms.png")

        fig, ax = plt.subplots()
        ax.add_collection(self.bars)
        ax.autoscale()
        loc = mdates.MonthLocator(bymonth=[1, 7])
        ax.xaxis.set_major_locator(loc)
        ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(loc))

        ax.set_yticks([i for i in range(
            len(self.symptoms)+1-self.seen_symptom_counts) if i > 0])
        ax.set_yticklabels(list(dict.fromkeys(
            list(map(lambda s: s.name, self.symptoms)))))
        stimulant_handles = []
        medication_handles = []

        for stimulant in self.stimulant_info:
            info = self.stimulant_info[stimulant]
            color = info["color"]
            marker = info["marker"]
            stimulant_handles.append(mlines.Line2D(
                [], [], color=color, marker=marker, linestyle='None',
                markersize=10, label=stimulant))
            for position in info["positions"]:
                ax.plot(position[0], position[1], marker=marker, color=color,
                        markeredgecolor="black")

        for medication in self.medication_info:
            info = self.medication_info[medication]
            color = info["color"]
            marker = info["marker"]
            medication_handles.append(mlines.Line2D(
                [], [], color=color, marker=marker, linestyle='None',
                markersize=10, label=medication))
            for position in info["positions"]:
                ax.plot(position[0], position[1], marker=marker, color=color,
                        markeredgecolor="black")
        l1 = ax.legend(bbox_to_anchor=(0, 1, 1, 0), loc="lower left",
                       handles=stimulant_handles,
                       title="PRIMARY CAUSE / STIMULANT", mode="expand", ncol=2)
        ax.legend(bbox_to_anchor=(0, -0.05, 1, 0), loc="upper left",
                  handles=medication_handles,
                  title="MEDICATION / TREATMENT", mode="expand", ncol=2)
        ax.add_artist(l1)
        fig.set_size_inches(10, 8)
        fig.savefig(self.save_loc, pad_inches=0.02, bbox_inches='tight')
        fig.clear(True)
        self.to_print = True
