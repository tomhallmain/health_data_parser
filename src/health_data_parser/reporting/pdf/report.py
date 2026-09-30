from datetime import datetime
import os
import re

from health_data_parser.reporting.pdf.canvas import pdf_creator
from health_data_parser.reporting.pdf.fonts import bold_font, regular_font
from health_data_parser.model.reference_range import Interpretation
from health_data_parser.model.units import VitalSignCategory
from health_data_parser.model.vitals import vital_label
from health_data_parser.utils.logger import setup_logger
from health_data_parser.utils.translations import _

# Set up logger
logger = setup_logger('report')

# Assumes newlines not already present

def _wrap_text_to_fit_length(text: str, fit_length: int):
    lines = []
    while len(text) > fit_length:
        # A space right after the limit still ends a full-length line
        spaces = list(re.finditer(" +", text[:fit_length + 1]))
        if spaces and spaces[-1].start() > 0:
            lines.append(text[:spaces[-1].start()])
            text = text[spaces[-1].end():].lstrip(" ")
        else:
            lines.append(text[:fit_length])
            text = text[fit_length:]
    if text or not lines:
        lines.append(text)
    return "\n".join(lines)


def _bullet(text: str, width: int = 102):
    """A bulleted paragraph wrapped to `width`, continuation lines indented."""
    lines = _wrap_text_to_fit_length(text, width).split("\n")
    return "\n".join(["• " + lines[0]] + ["  " + line for line in lines[1:]])


def _right_pad_with_spaces(text: str, length: int):
    if len(text) >= length:
        return text

    for i in range(length - len(text)):
        text += " "

    return text


def _get_conditional_format_styles(table: list, highlight_abnormal: bool):
    conditional_formats = []
    for r in range(len(table)):
        row = table[r]
        for c in range(len(row)):
            if c < 2:
                continue
            cell_value = row[c]
            if cell_value is None:
                continue
            elif cell_value == "":
                conditional_formats.append(
                    ("BACKGROUND", (c, r), (c, r), "Lightgrey"))
            elif highlight_abnormal:
                if ("+++" in cell_value or "---" in cell_value):
                    conditional_formats.append(
                        ("BACKGROUND", (c, r), (c, r), "Pink"))
                elif ("++" in cell_value or "--" in cell_value):
                    conditional_formats.append(
                        ("BACKGROUND", (c, r), (c, r), "peachpuff"))
                elif (cell_value[-1] == "+"):
                    conditional_formats.append(
                        ("BACKGROUND", (c, r), (c, r), "peachpuff"))
    return conditional_formats


def _find_rows_and_columns_to_skip(table: list):
    if table is None or len(table) == 0:
        return ([], [])

    rows_to_skip = list(range(len(table) + 1))
    rows_to_skip.remove(0)
    columns_to_skip = list(range(len(table[0])))
    columns_to_print = []

    for row_index in range(len(table)):
        row = table[row_index]
        print_row = False
        for col_index in range(len(row)):
            if print_row and col_index in columns_to_print:
                continue
            cell_value = row[col_index]
            if (cell_value is not None and not cell_value == ""
                    and re.search("[A-z0-9]", cell_value)):
                if col_index in columns_to_skip:
                    columns_to_skip.remove(col_index)
                if col_index not in columns_to_print:
                    columns_to_print.append(col_index)
                if not print_row and col_index > 1:
                    rows_to_skip.remove(row_index + 1)
                    print_row = True

    return (rows_to_skip, columns_to_skip)


def _filter_table(table: list, rows_to_skip: list, columns_to_skip: list):
    filtered_table = []

    for row_index in range(len(table)):
        if row_index in rows_to_skip:
            continue
        row = table[row_index]
        filtered_row = []
        for col_index in range(len(row)):
            if col_index not in columns_to_skip:
                filtered_row.append(row[col_index])
        filtered_table.append(filtered_row)

    return filtered_table


class Report:
    """Builds the PDF report from the observations.json content, the
    observation store, and whichever optional charts were produced."""

    # Result dates per by-date table; later dates continue in another table
    n_dates_in_table_per_page = 9
    # Rows with results per page of a by-date table
    max_observations_per_page = 40

    def __init__(self, output_path: str, subject: dict, filename_affix: str,
                 verbose=False, highlight_abnormal=True):
        self.output_path = output_path
        self.subject = subject
        self.verbose = verbose
        self.highlight_abnormal = highlight_abnormal
        self.filename = "HealthReport" + filename_affix + ".pdf"
        self.filepath = os.path.join(self.output_path, self.filename)

    def create_pdf(self, json_data: dict, store, vital_stats_graph=None,
                   symptom_charts=None, food_chart=None):
        include_observations = "observations" in json_data
        meta = json_data["meta"]
        has_abnormal_results = include_observations and "abnormalResults" in json_data
        print_pulse_stats_graph = (include_observations
                                   and meta["heartRateMonitoringWearableDetected"]
                                   and vital_stats_graph is not None
                                   and vital_stats_graph.to_print)

        creator = pdf_creator(800, 50, self.filepath, self._footer_text(meta), self.verbose)
        self.add_cover_page(creator, json_data, include_observations)
        if has_abnormal_results:
            self.add_abnormal_results_notice(creator, json_data)
        self.add_table_of_contents_section(creator, symptom_charts is not None,
                                           has_abnormal_results, include_observations,
                                           print_pulse_stats_graph, food_chart is not None)
        if symptom_charts is not None:
            self.add_symptom_data(creator, symptom_charts)
        if has_abnormal_results:
            self.add_abnormal_results_summary_table(creator, json_data)
            self.add_abnormal_observations_by_date_tables(creator, store)
        elif include_observations:
            creator.show_text(_("No abnormal results were found in Apple Health data export."))
        if include_observations:
            self.add_observations_by_date_tables(creator, store)
        if print_pulse_stats_graph:
            self.add_heart_stats(creator, json_data, vital_stats_graph)
        if food_chart is not None:
            self.add_food_data(creator, food_chart)
        self.close(creator)

    def _footer_text(self, meta):
        report_date = meta["processTime"][:10]
        name = self.subject["name"] if self._subject_known() else _("UNKNOWN")
        return _("Subject: {0} | Report created: {1}").format(name, report_date)

    def _subject_known(self):
        return self.subject is not None and bool(self.subject.get("name"))

    def add_cover_page(self, creator, json_data, include_observations):
        if self.verbose:
            logger.info("Creating report cover page...")
        meta = json_data["meta"]
        creator.set_font(bold_font(), 15)
        creator.show_text(_("Health Records Report"))
        creator.set_font(regular_font(), 12)
        creator.set_leading(14)
        creator.newline()
        creator.newline()

        if include_observations:
            # Labels padded to a column
            width = 23
            if self._subject_known():
                creator.show_text(_("Subject").ljust(width) + self.subject["name"])
                if "birthDate" in self.subject:
                    creator.show_text(_("DOB").ljust(width) + datetime.fromisoformat(
                            self.subject["birthDate"]).strftime("%B %d, %Y"))
                    creator.show_text(_("Age").ljust(width) + str(self.subject["age"]))
                if "sex" in self.subject:
                    creator.show_text(_("Sex").ljust(width) + str(self.subject["sex"]))
            else:
                creator.show_text(_("Subject").ljust(width) + _("UNKNOWN"))

            creator.show_text(_("Lab records count").ljust(width) + str(
                    meta["observationCount"]))
            creator.show_text(_("Earliest record").ljust(width) + datetime.fromisoformat(
                    meta["earliestResult"]).strftime("%B %d, %Y"))
            creator.show_text(_("Most recent record").ljust(width) + datetime.fromisoformat(
                    meta["mostRecentResult"]).strftime("%B %d, %Y"))
            creator.show_text(_("Report assembled").ljust(width) + datetime.fromisoformat(
                    meta["processTime"][:10]).strftime("%B %d, %Y"))

            if meta["vitalSignsObservationCount"] > 0:
                self.add_vitals_summary(creator, json_data["vitalSigns"])

        creator.set_font(regular_font(), 12)
        creator.set_leading(14)
        creator.newline()
        creator.newline()

    def add_vitals_summary(self, creator, vital_signs):
        creator.newline()
        creator.newline()
        creator.set_font(bold_font(), 12)
        creator.show_text(_("Summary of Vitals"))
        creator.newline()

        creator.set_font(regular_font(), 8)
        creator.set_leading(8)

        # TODO add Trend column and/or graph of these vitals
        vital_signs_table = [[_("Vital"), _("Unit"), _("Most Recent"), _("Date"), _("Max"),
                              _("Min"), _("Average"), _("StDev"), _("Count")]]

        for vital in vital_signs:
            if vital["count"] == 0:
                continue
            most_recent = vital["mostRecent"]
            date = datetime.strftime(most_recent["time"], "%B %d, %Y")
            if isinstance(most_recent["value"], list):
                # Blood pressure: one row per component
                for i in range(len(most_recent["value"])):
                    vital_signs_table.append([
                        vital_label(vital["labels"][i]), vital["unit"], str(round(most_recent["value"][i], 1)), date,
                        round(vital["max"][i], 1), round(vital["min"][i], 1), round(vital["avg"][i], 1),
                        round(vital["stDev"][i], 1), vital["count"]])
            else:
                vital_signs_table.append([
                    vital_label(vital["vital"]), vital["unit"], str(round(most_recent["value"], 1)), date,
                    round(vital["max"], 1), round(vital["min"], 1), round(vital["avg"], 1),
                    round(vital["stDev"], 1), vital["count"]])

        creator.show_table(vital_signs_table, [], 50)

    def add_abnormal_results_notice(self, creator, json_data):
        abnormal_results_meta = json_data["abnormalResults"]["meta"]
        creator.set_font(bold_font(), 12)
        creator.show_text(_("WARNING: Abnormal results were found."))
        creator.set_font(regular_font(), 12)
        creator.newline()
        width = 32
        creator.show_text(_("Lab codes with abnormal results").ljust(width) + str(
            abnormal_results_meta["codesWithAbnormalResultsCount"]))
        creator.show_text(_("Total abnormal observations").ljust(width) + str(
            abnormal_results_meta["totalAbnormalResultsCount"]))
        creator.newline()
        creator.set_leading(10)
        creator.set_font(regular_font(), 9)
        creator.show_text(_wrap_text_to_fit_length(_(
            "NOTE: Reference ranges for tests are not static. The range displayed in all tables "
            "represents the most recent range available. A result classified as abnormal by an old "
            "range may be acceptable within current ranges."), 88))
        creator.newline()

        if abnormal_results_meta["includesInRangeAbnormalities"]:
            in_range_boundary_percent = str(
                round(abnormal_results_meta["inRangeAbnormalBoundary"] * 100)) + "%"
            creator.show_text(_wrap_text_to_fit_length(_(
                "Abnormal results may include results within ranges at +/-{0} ends of the relevant "
                "range. These are labeled as lower severity with the labels \"High in range\" and "
                "\"Low in range\" or tags \"++\" and \"--\". Tags \"+++\" and \"---\" indicate high and "
                "low out of range. Tag \"+\" indicates a positive result.").format(in_range_boundary_percent), 88))
        else:
            creator.show_text(_wrap_text_to_fit_length(_(
                "All listed abnormal results are out of the relevant range. Tags \"+++\" and \"---\" "
                "indicate high and low out of range. Tag \"+\" indicates a positive result."), 88))

    def add_table_of_contents_section(self, creator, print_symptom_data,
                                      has_abnormal_results, include_observations,
                                      print_pulse_stats_graph, print_food_data):
        creator.newline()
        creator.newline()
        creator.newline()
        creator.set_font(bold_font(), 12)
        creator.show_text(_("Sections included in this report"))
        creator.newline()
        creator.set_leading(10)
        creator.set_font(regular_font(), 10)

        if print_symptom_data:
            creator.show_text(" • " + _("Symptoms Report"))
        if has_abnormal_results:
            creator.show_text(" • " + _("Abnormal Results By Code Summary"))
            creator.show_text(" • " + _("Abnormal Results By Code Detail"))
        if include_observations:
            creator.show_text(" • " + _("All Lab Observations"))
        if print_pulse_stats_graph:
            creator.show_text(" • " + _("Heart Rate Data Analysis"))
        if print_food_data:
            creator.show_text(" • " + _("Food Data Analysis"))

    def add_symptom_data(self, creator, symptom_charts):
        if self.verbose:
            logger.info("Adding symptoms report...")
        pages = [(_("Symptoms Report - Including Historical"), symptom_charts.all_symptoms_path)]
        if symptom_charts.unresolved_path is not None:
            pages.append((_("Symptoms Report - Unresolved"), symptom_charts.unresolved_path))
        for title, image_path in pages:
            creator.add_page()
            creator.set_font(bold_font(), 15)
            creator.set_leading(16)
            creator.show_text(title)
            creator.newline()
            creator.set_leading(10)
            creator.set_font(regular_font(), 10)
            creator.show_image(image_path, 550, width=720, height=500, rotate=True)

    def add_abnormal_results_summary_table(self, creator, json_data):
        if self.verbose:
            logger.info("Writing abnormal results summary and detail tables...")
        abnormal_results = json_data["abnormalResults"]
        includes_in_range = abnormal_results["meta"]["includesInRangeAbnormalities"]
        interpretations_by_code = abnormal_results["codesWithAbnormalResults"]

        creator.add_page()
        creator.set_font(bold_font(), 15)
        creator.set_leading(20)
        creator.show_text(_("Abnormal Results By Code Summary"))
        creator.set_leading(10)
        creator.newline()

        if includes_in_range:
            table = [[_("RESULT CODE"), _("L OUT"), _("L IN"), _("OBSERVED"), _("H IN"), _("H OUT")]]
        else:
            table = [[_("RESULT CODE"), _("LOW OUT OF RANGE"), _("OBSERVED"), _("HIGH OUT OF RANGE")]]
        interpretations = Interpretation.ordered(include_in_range=includes_in_range)
        for code in sorted(interpretations_by_code):
            code_label = code[0:20] + ".." + code[-6:] if len(code) > 35 else code
            found = interpretations_by_code[code]
            table.append([code_label] + [i.value if i.text in found else "" for i in interpretations])

        creator.show_table(table, [], -1)

    def add_abnormal_observations_by_date_tables(self, creator, store):
        abnormal_results = store.abnormal_results
        codes = [code for code in store.codes
                 if any(code_id in abnormal_results for code_id in store.code_ids(code))]

        def abnormal_result(code, date):
            for code_id in store.code_ids(code):
                for observation in abnormal_results.get(code_id, []):
                    if observation.date == date:
                        return observation
            return None

        self._add_by_date_tables(creator, store, store.abnormal_dates, codes, abnormal_result,
                                 _("Abnormal Results By Code"), highlight_abnormal=False,
                                 gap_after_first_title=True)

    def add_observations_by_date_tables(self, creator, store):
        if self.verbose:
            logger.info("Writing all observations detail tables...")
        self._add_by_date_tables(creator, store, store.dates, store.codes, store.find_for_code,
                                 _("All Lab Observations"), highlight_abnormal=self.highlight_abnormal,
                                 gap_after_first_title=False)

    def _add_by_date_tables(self, creator, store, dates, codes, result_for, title,
                            highlight_abnormal, gap_after_first_title):
        """Tables of results with a row per code and a column per date.

        Dates are split into tables of n_dates_in_table_per_page, and each
        table into pages of max_observations_per_page rows that have results;
        rows and columns without any result are left out of a page.
        result_for(code, date) gives the observation for a cell, or None.
        """
        has_reference_dates = len(store.reference_dates) > 0
        header = [_("Observation Code"), _("Range")] if has_reference_dates else [_("Observation Code")]
        code_columns = []
        for code in codes:
            if not has_reference_dates:
                code_columns.append([code])
            elif code in store.ranges:
                code_columns.append([_wrap_text_to_fit_length(code, 20),
                                     _wrap_text_to_fit_length(store.ranges[code], 15)])
            else:
                code_columns.append([code, ""])

        has_shown_first_page = False
        max_observations_per_page = self.max_observations_per_page
        for start in range(0, len(dates), self.n_dates_in_table_per_page):
            table_dates = dates[start:start + self.n_dates_in_table_per_page]
            header_row = header + table_dates
            observations_table = []
            for code, code_column in zip(codes, code_columns):
                row = list(code_column)
                for date in table_dates:
                    observation = result_for(code, date)
                    if observation is None:
                        row.append("")
                    else:
                        tag = observation.reference.tag if observation.has_reference else ""
                        row.append(_wrap_text_to_fit_length(observation.value_string[:15] + tag, 10))
                observations_table.append(row)

            while len(observations_table) > 0:
                observation_cutoff = max_observations_per_page
                table_to_show = observations_table[:observation_cutoff]
                rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(
                    table_to_show)
                if len(rows_to_skip) > 0:
                    extension_amount = len(rows_to_skip)
                    while (len(observations_table) > observation_cutoff
                            and not len(table_to_show) - len(rows_to_skip) >= max_observations_per_page):
                        table_to_show.extend(observations_table[observation_cutoff:(
                            observation_cutoff+extension_amount)])
                        observation_cutoff += extension_amount
                        if self.verbose:
                            logger.info(f"Extended table by {extension_amount} as some rows skipped. New table length including skipped: {len(table_to_show)}")
                        rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(
                            table_to_show)
                        extension_amount = max_observations_per_page - \
                            (len(table_to_show) - len(rows_to_skip))
                observations_table = observations_table[len(
                    table_to_show):]
                table_to_show.insert(0, header_row)
                if len(rows_to_skip) > 0 or len(columns_to_skip) > 0:
                    table_to_show = _filter_table(
                        table_to_show, rows_to_skip, columns_to_skip)
                creator.add_page()
                creator.set_font(bold_font(), 15)
                creator.set_leading(16)
                if has_shown_first_page:
                    creator.show_text(_("{0} (continued)").format(title))
                else:
                    creator.show_text(title)
                    if gap_after_first_title:
                        creator.newline()
                    has_shown_first_page = True
                creator.set_leading(7)
                creator.newline()
                creator.set_font(regular_font(), 6)
                extra_style_commands = [
                    ("BACKGROUND", (1, 1), (1, -1), "oldlace"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2)
                    ]
                extra_style_commands.extend(
                    _get_conditional_format_styles(table_to_show, highlight_abnormal))
                x_offset = 50 if len(table_to_show[0]) <= 9 else 30
                creator.show_table(
                    table_to_show, extra_style_commands, x_offset)

    def add_heart_stats(self, creator, json_data, pulse_stats_graph):
        if self.verbose:
            logger.info("Adding pulse stats graphs sections...")
        creator.add_page()
        creator.set_font(bold_font(), 15)
        creator.set_leading(16)
        creator.show_text(_("Heart Rate Data Analysis"))
        creator.newline()
        creator.set_leading(10)
        creator.set_font(regular_font(), 10)
        for vital in json_data["vitalSigns"]:
            if vital["vital"] == VitalSignCategory.PULSE.value:
                text1 = _right_pad_with_spaces(_("Total readings:").ljust(26)
                                               + str(vital["count"]), 45)
                text2 = _right_pad_with_spaces(_("Pulse average:").ljust(26)
                                               + str(round(vital["avg"], 1)), 45)
                text3 = _right_pad_with_spaces(_("Pulse standard deviation:").ljust(26)
                                               + str(round(vital["stDev"], 1)), 45)
                in_motion_count = len(pulse_stats_graph.values_in_motion)
                total_count = in_motion_count + len(pulse_stats_graph.values_resting)
                percent_in_motion = in_motion_count / total_count * 100 if total_count else 0
                # Right-aligned labels, followed by a space
                creator.show_text(text1 + _("Percent in motion:").rjust(18) + " "
                                  + str(round(percent_in_motion)) + "%")
                creator.show_text(text2 + _("Average in motion:").rjust(18) + " "
                                  + str(round(pulse_stats_graph.avg_in_motion, 1)))
                creator.show_text(text3 + _("Average resting:").rjust(18) + " "
                                  + str(round(pulse_stats_graph.avg_resting, 1)))
                creator.newline()
        creator.show_image(
            pulse_stats_graph.save_loc_minutes_data, 45, width=500)

        creator.newline()
        creator.set_leading(9)
        creator.set_font(regular_font(), 8)
        creator.show_text(" " * 51 + _("NOTES"))
        creator.newline()
        creator.show_text(_bullet(_(
            "\"Motion\" data found in Apple wearable observations. All pulse observations in clinical "
            "records data are assumed to be obtained in a non-motion state. The reliability of motion "
            "data may be questionable.")))
        creator.show_text(_bullet(_(
            "\"Pulse spikes\" are instances where there is an increase of pulse by at least 40 BPM "
            "during 5 or fewer minutes.")))

        creator.add_page()
        creator.set_font(bold_font(), 15)
        creator.set_leading(16)
        creator.show_text(_("Heart Rate Data Analysis"))
        creator.newline()
        creator.set_leading(10)
        creator.set_font(regular_font(), 10)
        creator.show_text(_("Dates recorded:").ljust(18)
                          + str(len(pulse_stats_graph.pulse_dates)))
        creator.show_text(_("Earliest date:").ljust(18) + datetime.fromordinal(
            pulse_stats_graph.pulse_dates[0]).strftime("%B %d, %Y"))
        creator.show_text(_("Most recent date:").ljust(18) + datetime.fromordinal(
            pulse_stats_graph.pulse_dates[-1]).strftime("%B %d, %Y"))
        creator.newline()
        creator.show_image(
            pulse_stats_graph.save_loc_dates_data, 45, width=500)
        creator.newline()
        creator.set_leading(9)
        creator.set_font(regular_font(), 8)
        creator.show_text(" " * 51 + _("NOTES"))
        creator.newline()
        creator.show_text(_bullet(_(
            "\"Steps\" and \"Stand minutes\" data found in Apple wearable observations. Stand minutes "
            "are usually only counted when in motion, so true stand minutes will be higher, while true "
            "step count may vary in either direction from recorded values.")))

    def add_food_data(self, creator, food_chart):
        food_data = food_chart.food
        if self.verbose:
            logger.info("Adding food data report...")
        creator.add_page()
        creator.set_font(bold_font(), 15)
        creator.set_leading(16)
        creator.show_text(_("Food Data Analysis"))
        creator.newline()
        creator.set_leading(10)
        creator.set_font(regular_font(), 10)
        text1 = _right_pad_with_spaces(_("Total food records:").ljust(25)
                                       + str(food_data.record_count), 45)
        text2 = _right_pad_with_spaces(_("Earliest food record:").ljust(25)
                                       + food_data.meal_times[0].strftime("%B %d, %Y"), 45)
        text3 = _right_pad_with_spaces(_("Most recent food record:").ljust(25)
                                       + food_data.meal_times[-1].strftime("%B %d, %Y"), 45)
        creator.show_text(text1 + " " + _("Total meals recorded:").ljust(23)
                          + str(len(food_data.meal_times)))
        creator.show_text(text2 + " " + _("Total dates recorded:").ljust(23)
                          + str(len(food_data.dates_recorded)))
        creator.show_text(text3 + " " + _("Average meals per day:").ljust(23)
                          + str(food_data.avg_meals_per_day))
        creator.newline()
        creator.newline()
        creator.set_font(bold_font(), 10)
        creator.show_text(_("Most common foods recorded"))
        creator.newline()
        creator.show_image(food_chart.path, 150, width=250)

        creator.newline()
        creator.set_leading(9)
        creator.set_font(regular_font(), 8)
        creator.show_text(" " * 51 + _("NOTES"))

        if food_data.has_warning_diets() or food_data.has_danger_diets():
            creator.show_text(
                _("Certain diets are contraindicated by the foods found. These include:"))
            if food_data.has_danger_diets():
                creator.show_text(_wrap_text_to_fit_length(
                    _("DANGER:").rjust(10) + " " + ", ".join(food_data.get_top_n_danger_diets(10)), 100))
            if food_data.has_warning_diets():
                creator.show_text(_wrap_text_to_fit_length(
                    _("WARNING:").rjust(10) + " " + ", ".join(food_data.get_top_n_warning_diets(10)), 100))

    def close(self, creator):
        creator.add_header_and_footer()
        creator.save()
