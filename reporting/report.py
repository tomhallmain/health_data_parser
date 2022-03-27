from datetime import datetime
import re

from reporting.pdf_creator import pdf_creator
from data.units import VitalSignCategory


# Assumes newlines not already present

def _wrap_text_to_fit_length(text: str, fit_length: int):
    if len(text) <= fit_length:
        return text

    if " " in text and text.index(" ") < len(text) - 2:
        test_new_text = text[:fit_length]
        if " " in test_new_text:
            last_space_block = re.findall(" +", test_new_text)[-1]
            last_space_block_index = test_new_text.rfind(last_space_block)
            new_text = text[:last_space_block_index]
            text = text[(last_space_block_index+len(last_space_block)):]
        else:
            new_text = test_new_text
            text = text[fit_length:]
        while len(text) > 0:
            new_text += "\n"
            test_new_text = text[:fit_length]
            if len(test_new_text) <= fit_length:
                new_text += test_new_text
                text = text[fit_length:]
            elif " " in test_new_text and test_new_text.index(" ") < len(test_new_text) - 2:
                last_space_block = re.findall(" +", test_new_text)[-1]
                last_space_block_index = test_new_text.rfind(last_space_block)
                new_text += text[:last_space_block_index]
                text = text[(last_space_block_index+len(last_space_block)):]
            else:
                new_text += test_new_text
                text = text[fit_length:]
    else:
        new_text = text[:fit_length]
        text = text[fit_length:]
        while len(text) > 0:
            new_text += "\n"
            new_text += text[:fit_length]
            text = text[fit_length:]

    return new_text


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
    def __init__(self, output_path: str, subject: dict, filename_affix: str,
                 verbose=False, highlight_abnormal=True):
        self.output_path = output_path
        self.subject = subject
        self.verbose = verbose
        self.highlight_abnormal = highlight_abnormal
        self.filename = "HealthReport" + filename_affix + ".pdf"
        self.filepath = self.output_path + "/" + self.filename

    def create_pdf(self, data: dict, observations: dict, observation_dates: list,
                   observation_code_ids: dict, ranges: dict, date_codes: dict,
                   reference_dates: list, abnormal_results: dict,
                   abnormal_result_dates: list, symptom_data,
                   pulse_stats_graph, food_data):
        if self.verbose:
            print("\nCreating report cover page...")

        meta = data["meta"]
        report_date = meta["processTime"][:10]
        has_abnormal_results = "abnormalResults" in data
        print_symptom_data = symptom_data is not None and symptom_data.to_print
        print_pulse_stats_graph = (meta["heartRateMonitoringWearableDetected"]
                                   and pulse_stats_graph is not None
                                   and pulse_stats_graph.to_print)
        print_food_data = food_data is not None and food_data.to_print

        if self.subject is None or self.subject["name"] == "":
            footer_text = "Subject: UNKNOWN" + " | Report created: " + report_date
            subject_known = False
        else:
            footer_text = "Subject: " + \
                self.subject["name"] + " | Report created: " + report_date
            subject_known = True

        creator = pdf_creator(800, 50, self.filepath,
                              footer_text, self.verbose)
        creator.set_font("MesloLGS NF Bold", 15)
        creator.show_text(meta["description"])
        creator.set_font("MesloLGS NF", 12)
        creator.set_leading(14)
        creator.newline()
        creator.newline()

        if subject_known:
            creator.show_text("Subject                " + self.subject["name"])
            if "birthDate" in self.subject:
                creator.show_text("DOB                    " + datetime.fromisoformat(
                        self.subject["birthDate"]).strftime("%B %d, %Y"))
                creator.show_text("Age                    "
                                  + str(self.subject["age"]))
            if "sex" in self.subject:
                creator.show_text("Sex                    "
                                  + str(self.subject["sex"]))
        else:
            creator.show_text("Subject                UNKNOWN")

        creator.show_text("Lab records count      " + str(
                meta["observationCount"]))
        creator.show_text("Earliest record        " + datetime.fromisoformat(
                meta["earliestResult"]).strftime("%B %d, %Y"))
        creator.show_text("Most recent record     " + datetime.fromisoformat(
                meta["mostRecentResult"]).strftime("%B %d, %Y"))
        creator.show_text("Report assembled       " + datetime.fromisoformat(
                report_date).strftime("%B %d, %Y"))

        if meta["vitalSignsObservationCount"] > 0:
            creator.newline()
            creator.newline()
            creator.set_font("MesloLGS NF Bold", 12)
            creator.show_text("Summary of Vitals")
            creator.newline()

            creator.set_font("MesloLGS NF", 8)
            creator.set_leading(8)

            # TODO add Trend column and/or graph of these vitals
            vital_signs_table = [["Vital", "Unit", "Most Recent", "Date", "Max",
                                  "Min", "Average", "StDev", "Count"]]

            for vital in data["vitalSigns"]:
                if vital["count"] > 0:
                    most_recent_obs = vital["list"][-1]
                    if type(vital["mostRecent"]["value"]) == list:
                        for i in range(len(vital["mostRecent"]["value"])):
                            row = [vital["labels"][i], vital["unit"]]
                            row.append(
                                str(round(most_recent_obs["value"][i], 1)))
                            row.append(datetime.strftime(
                                most_recent_obs["time"], "%B %d, %Y"))
                            row.append(round(vital["max"][i], 1))
                            row.append(round(vital["min"][i], 1))
                            row.append(round(vital["avg"][i], 1))
                            row.append(round(vital["stDev"][i], 1))
                            row.append(vital["count"])
                            vital_signs_table.append(row)
                    else:
                        row = [vital["vital"], vital["unit"]]
                        row.append(str(round(most_recent_obs["value"], 1)))
                        row.append(datetime.strftime(
                            most_recent_obs["time"], "%B %d, %Y"))
                        row.append(round(vital["max"], 1))
                        row.append(round(vital["min"], 1))
                        row.append(round(vital["avg"], 1))
                        row.append(round(vital["stDev"], 1))
                        row.append(vital["count"])
                        vital_signs_table.append(row)

            creator.show_table(vital_signs_table, None, 50)

        creator.set_font("MesloLGS NF", 12)
        creator.set_leading(14)
        creator.newline()
        creator.newline()

        if has_abnormal_results:
            creator.set_font("MesloLGS NF Bold", 12)
            creator.show_text("WARNING: Abnormal results were found.")
            creator.set_font("MesloLGS NF", 12)
            creator.newline()
            abnormal_results_meta = data["abnormalResults"]["meta"]
            creator.show_text("Lab codes with abnormal results " + str(
                abnormal_results_meta["codesWithAbnormalResultsCount"]))
            creator.show_text("Total abnormal observations     " + str(
                abnormal_results_meta["totalAbnormalResultsCount"]))
            creator.newline()
            includes_in_range = abnormal_results_meta["includesInRangeAbnormalities"]
            creator.set_leading(10)
            creator.set_font("MesloLGS NF", 9)
            creator.show_text(
                "NOTE: Reference ranges for tests are not static. The range displayed in all tables")
            creator.show_text(
                "represents the most recent range available. A result classified as abnormal by an old")
            creator.show_text("range may be acceptable within current ranges.")
            creator.newline()

            if includes_in_range:
                in_range_boundary_percent = str(
                    round(abnormal_results_meta["inRangeAbnormalBoundary"] * 100)) + "%"
                creator.show_text("Abnormal results may include results within ranges at +/-"
                                  + in_range_boundary_percent + " ends of the relevant range.")
                creator.show_text(
                    "These are labeled as lower severity with the labels \"High in range\" and \"Low in range\"")
                creator.show_text(
                    "or tags \"++\" and \"--\". Tags \"+++\" and \"---\" indicate high and low out of range.")
                creator.show_text("Tag \"+\" indicates a positive result.")
                abnormal_results_table = [
                    ["RESULT CODE", "L OUT", "L IN", "OBSERVED", "H IN", "H OUT"]]
            else:
                creator.show_text(
                    "All listed abnormal results are out of the relevant range. Tags \"+++\" and \"---\" indicate")
                creator.show_text(
                    "high and low out of range. Tag \"+\" indicates a positive result.")
                abnormal_results_table = [
                    ["RESULT CODE", "LOW OUT OF RANGE", "OBSERVED", "HIGH OUT OF RANGE"]]

        #############################################################
        ##
        ## TABLE OF CONTENTS
        ##
        #############################################################

        creator.newline()
        creator.newline()
        creator.newline()
        creator.set_font("MesloLGS NF Bold", 12)
        creator.show_text("Sections included in this report")
        creator.newline()
        creator.set_leading(10)
        creator.set_font("MesloLGS NF", 10)

        if print_symptom_data:
            creator.show_text(" • Symptoms Report")
        if has_abnormal_results:
            creator.show_text(" • Abnormal Results By Code Summary")
            creator.show_text(" • Abnormal Results By Code Detail")
        creator.show_text(" • All Lab Observations")
        if print_pulse_stats_graph:
            creator.show_text(" • Heart Rate Data Analysis")
        if print_food_data:
            creator.show_text(" • Food Data Analysis")

        #############################################################
        ##
        ## SYMPTOM SET REPORT
        ##
        #############################################################

        if print_symptom_data:
            if self.verbose:
                print("Adding symptoms report...")
            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(16)
            creator.show_text("Symptoms Report")
            creator.newline()
            creator.set_leading(10)
            creator.set_font("MesloLGS NF", 10)
            creator.show_image(symptom_data.save_loc, 550,
                               width=720, height=500, rotate=True)

        if has_abnormal_results:
            abnormal_results_meta = data["abnormalResults"]["meta"]
            includes_in_range = abnormal_results_meta["includesInRangeAbnormalities"]

            #############################################################
            ##
            ## ABNORMAL RESULTS SUMMARY TABLE
            ##
            #############################################################

            if self.verbose:
                print("Writing abnormal results summary and detail tables...")

            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(20)
            creator.show_text("Abnormal Results By Code Summary")
            creator.set_leading(10)
            creator.newline()
            abnormal_result_interpretations_by_code = data["abnormalResults"]["codesWithAbnormalResults"]

            for code in sorted(abnormal_result_interpretations_by_code.keys()):
                if len(code) > 35:
                    code_row = [code[0:20] + ".." + code[-6:]]
                else:
                    code_row = [code]
                interpretations = abnormal_result_interpretations_by_code[code]
                if "LOW OUT OF RANGE" in interpretations:
                    code_row.append("---")
                else:
                    code_row.append("")
                if includes_in_range:
                    if "Low in range" in interpretations:
                        code_row.append("--")
                    else:
                        code_row.append("")
                if "Non-negative result" in interpretations:
                    code_row.append("+")
                else:
                    code_row.append("")
                if includes_in_range:
                    if "High in range" in interpretations:
                        code_row.append("++")
                    else:
                        code_row.append("")
                if "HIGH OUT OF RANGE" in interpretations:
                    code_row.append("+++")
                else:
                    code_row.append("")

                abnormal_results_table.append(code_row)

            creator.show_table(abnormal_results_table, None, -1)

            #############################################################
            ##
            ## ABNORMAL OBSERVATIONS BY DATE TABLES
            ##
            #############################################################

            n_dates_in_table_per_page = 9
            header = ["Observation Code", "Range"] if len(
                reference_dates) > 0 else ["Observation Code"]
            header_dates_tables = []
            header_dates = []
            table_counter = 0
            date_counter = 0
            has_unappended_row = False

            for date in abnormal_result_dates:
                header_dates.append(date)
                date_counter += 1
                has_unappended_row = True
                if date_counter % n_dates_in_table_per_page == 0:
                    if len(header_dates_tables) > table_counter:
                        header_dates_tables[table_counter] = header_dates
                    else:
                        header_dates_tables.append(header_dates)
                    header_dates = []
                    has_unappended_row = False
                    table_counter += 1
                    header_dates = header_dates_tables[table_counter] if len(
                        header_dates_tables) > table_counter else []

            if has_unappended_row:
                if len(header_dates_tables) > table_counter:
                    header_dates_tables[table_counter] = header_dates
                else:
                    header_dates_tables.append(header_dates)

            code_ranges_table = []

            for code in sorted(observation_code_ids):
                for code_id in observation_code_ids[code]:
                    if code_id in abnormal_results:
                        if len(reference_dates) > 0:
                            if code in ranges:
                                row = [_wrap_text_to_fit_length(
                                    code, 20), _wrap_text_to_fit_length(ranges[code], 15)]
                            else:
                                row = [code, ""]
                        else:
                            row = [code]

                        code_ranges_table.append(row)

            # abnormal_results_tables is a list of abnormal observation date
            # results with columsn of up to n_dates_in_table_per_page per page
            abnormal_results_tables = []

            for code in sorted(observation_code_ids):
                date_counter = 0
                table_counter = 0
                table = abnormal_results_tables[table_counter] if len(
                    abnormal_results_tables) > table_counter else []
                row = []
                has_unappended_row = False
                abnormal_result_found = False

                for date in abnormal_result_dates:
                    date_counter += 1
                    date_found = False
                    has_unappended_row = True

                    for code_id in observation_code_ids[code]:
                        if code_id in abnormal_results:
                            abnormal_result_found = True
                            results = abnormal_results[code_id]
                            for observation in results:
                                if observation.date == date and date + code_id in date_codes:
                                    date_found = True
                                    value = observation.value_string[:15]
                                    if observation.has_reference:
                                        abnormal_result_tag = observation.result.interpretation
                                    else:
                                        abnormal_result_tag = ""
                                    row.append(_wrap_text_to_fit_length(
                                        value + abnormal_result_tag, 10))
                                    break
                            else:
                                continue

                            break

                    if not date_found:
                        row.append("")

                    if abnormal_result_found and date_counter % n_dates_in_table_per_page == 0:
                        table.append(row)
                        row = []
                        if len(abnormal_results_tables) > table_counter:
                            abnormal_results_tables[table_counter] = table
                        else:
                            abnormal_results_tables.append(table)
                        has_unappended_row = False
                        table_counter += 1
                        table = abnormal_results_tables[table_counter] if len(
                            abnormal_results_tables) > table_counter else []

                if abnormal_result_found and has_unappended_row:
                    table.append(row)
                    if len(abnormal_results_tables) > table_counter:
                        abnormal_results_tables[table_counter] = table
                    else:
                        abnormal_results_tables.append(table)

            has_shown_first_page = False
            max_observations_per_page = 40

            for i in range(len(abnormal_results_tables)):
                header_row = list(header)
                header_row.extend(header_dates_tables[i])
                table = abnormal_results_tables[i]
                observations_table = []

                for i in range(len(table)):
                    row = list(code_ranges_table[i])
                    row.extend(table[i])
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
                                print("Extended table by " + str(extension_amount)
                                      + " as some rows skipped. New table length: " + str(len(table_to_show)))
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
                    creator.set_font("MesloLGS NF Bold", 15)
                    creator.set_leading(16)
                    if has_shown_first_page:
                        creator.show_text(
                            "Abnormal Results By Code (continued)")
                    else:
                        creator.show_text("Abnormal Results By Code")
                        creator.newline()
                        has_shown_first_page = True
                    creator.set_leading(7)
                    creator.newline()
                    creator.set_font("MesloLGS NF", 6)
                    extra_style_commands = [
                        ("BACKGROUND", (1, 1), (1, -1), "oldlace"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 2)
                        ]

                    extra_style_commands.extend(
                        _get_conditional_format_styles(table_to_show, False))
                    x_offset = 50 if len(table_to_show[0]) <= 9 else 30
                    creator.show_table(
                        table_to_show, extra_style_commands, x_offset)

            #############################################################
            ##
            ## ALL OBSERVATIONS BY DATE TABLES
            ##
            #############################################################

            if self.verbose:
                print("Writing all observations detail tables...")

            header_dates_tables = []
            header_dates = []
            table_counter = 0
            date_counter = 0
            has_unappended_row = False

            for date in observation_dates:
                header_dates.append(date)
                date_counter += 1
                has_unappended_row = True
                if date_counter % n_dates_in_table_per_page == 0:
                    if len(header_dates_tables) > table_counter:
                        header_dates_tables[table_counter] = header_dates
                    else:
                        header_dates_tables.append(header_dates)
                    header_dates = []
                    has_unappended_row = False
                    table_counter += 1
                    header_dates = header_dates_tables[table_counter] if len(
                        header_dates_tables) > table_counter else []

            if has_unappended_row:
                if len(header_dates_tables) > table_counter:
                    header_dates_tables[table_counter] = header_dates
                else:
                    header_dates_tables.append(header_dates)

            code_ranges_table = []

            for code in sorted(observation_code_ids):
                if len(reference_dates) > 0:
                    if code in ranges:
                        row = [_wrap_text_to_fit_length(
                            code, 20), _wrap_text_to_fit_length(ranges[code], 15)]
                    else:
                        row = [code, ""]
                else:
                    row = [code]

                code_ranges_table.append(row)

            # results_tables is a list of observation date results with columns
            # of up to n_dates_in_table_per_page per page
            results_tables = []

            for code in sorted(observation_code_ids):
                date_counter = 0
                table_counter = 0
                table = results_tables[table_counter] if len(
                    results_tables) > table_counter else []
                row = []
                has_unappended_row = False

                for date in observation_dates:
                    date_counter += 1
                    date_found = False
                    has_unappended_row = True

                    for code_id in observation_code_ids[code]:
                        datecode = date + code_id
                        if datecode in date_codes:
                            date_found = True
                            observation = observations[date_codes[datecode]]
                            if observation.has_reference:
                                abnormal_result_tag = observation.result.interpretation
                            else:
                                abnormal_result_tag = ""
                            value = observation.value_string[:15]
                            row.append(_wrap_text_to_fit_length(
                                value + abnormal_result_tag, 10))
                            break

                    if not date_found:
                        row.append("")

                    if date_counter % n_dates_in_table_per_page == 0:
                        table.append(row)
                        row = []
                        if len(results_tables) > table_counter:
                            results_tables[table_counter] = table
                        else:
                            results_tables.append(table)
                        has_unappended_row = False
                        table_counter += 1
                        table = results_tables[table_counter] if len(
                            results_tables) > table_counter else []

                if has_unappended_row:
                    table.append(row)
                    if len(results_tables) > table_counter:
                        results_tables[table_counter] = table
                    else:
                        results_tables.append(table)

            has_shown_first_page = False
            max_observations_per_page = 40

            for i in range(len(results_tables)):
                header_row = list(header)
                header_row.extend(header_dates_tables[i])
                table = results_tables[i]
                observations_table = []

                for i in range(len(table)):
                    row = list(code_ranges_table[i])
                    row.extend(table[i])
                    observations_table.append(row)

                while len(observations_table) > 0:
                    rows_to_skip = []
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
                                print("Extended table by " + str(extension_amount)
                                      + " as some rows skipped. New table length "
                                      + "including skipped: " + str(len(table_to_show)))
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
                    creator.set_font("MesloLGS NF Bold", 15)
                    creator.set_leading(16)
                    if has_shown_first_page:
                        creator.show_text("All Lab Observations (continued)")
                    else:
                        creator.show_text("All Lab Observations")
                        has_shown_first_page = True
                    creator.set_leading(7)
                    creator.newline()
                    creator.set_font("MesloLGS NF", 6)
                    extra_style_commands = [
                        ("BACKGROUND", (1, 1), (1, -1), "oldlace"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 2)
                        ]

                    extra_style_commands.extend(_get_conditional_format_styles(
                            table_to_show, self.highlight_abnormal))
                    x_offset = 50 if len(table_to_show[0]) <= 9 else 30
                    creator.show_table(
                        table_to_show, extra_style_commands, x_offset)

        else:
            creator.show_text(
                "No abnormal results were found in Apple Health data export.")

        if print_pulse_stats_graph:
            if self.verbose:
                print("Adding pulse stats graphs sections...")
            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(16)
            creator.show_text("Heart Rate Data Analysis")
            creator.newline()
            creator.set_leading(10)
            creator.set_font("MesloLGS NF", 10)
            for vital in data["vitalSigns"]:
                if vital["vital"] == VitalSignCategory.PULSE.value:
                    text1 = _right_pad_with_spaces("Total readings:           "
                                                   + str(vital["count"]), 45)
                    text2 = _right_pad_with_spaces("Pulse average:            "
                                                   + str(round(vital["avg"], 1)), 45)
                    text3 = _right_pad_with_spaces("Pulse standard deviation: "
                                                   + str(round(vital["stDev"], 1)), 45)
                    percent_in_motion = len(
                        pulse_stats_graph.values_in_motion) / len(pulse_stats_graph.values_resting) * 100
                    creator.show_text(text1 + "Percent in motion: "
                                      + str(round(percent_in_motion)) + "%")
                    creator.show_text(text2 + "Average in motion: "
                                      + str(round(pulse_stats_graph.avg_in_motion, 1)))
                    creator.show_text(text3 + "  Average resting: "
                                      + str(round(pulse_stats_graph.avg_resting, 1)))
                    creator.newline()
            creator.show_image(
                pulse_stats_graph.save_loc_minutes_data, 45, width=500)

            creator.newline()
            creator.set_leading(9)
            creator.set_font("MesloLGS NF", 8)
            creator.show_text(
                "                                                   NOTES")
            creator.newline()
            creator.show_text(
                "• \"Motion\" data found in Apple wearable observations. All pulse observations in clinical records data")
            creator.show_text(
                "  are assumed to be obtained in a non-motion state. The reliability of motion data may be questionable.")
            creator.show_text(
                "• \"Pulse spikes\" are instances where there is an increase of pulse by at least 40 BPM during 5 or")
            creator.show_text("  fewer minutes.")

            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(16)
            creator.show_text("Heart Rate Data Analysis")
            creator.newline()
            creator.set_leading(10)
            creator.set_font("MesloLGS NF", 10)
            creator.show_text("Dates recorded:   "
                              + str(len(pulse_stats_graph.pulse_dates)))
            creator.show_text("Earliest date:    " + datetime.fromordinal(
                pulse_stats_graph.pulse_dates[0]).strftime("%B %d, %Y"))
            creator.show_text("Most recent date: " + datetime.fromordinal(
                pulse_stats_graph.pulse_dates[-1]).strftime("%B %d, %Y"))
            creator.newline()
            creator.show_image(
                pulse_stats_graph.save_loc_dates_data, 45, width=500)
            creator.newline()
            creator.set_leading(9)
            creator.set_font("MesloLGS NF", 8)
            creator.show_text(
                "                                                   NOTES")
            creator.newline()
            creator.show_text(
                "• \"Steps\" and \"Stand minutes\" data found in Apple wearable observations. Stand minutes are")
            creator.show_text(
                "  usually only counted when in motion, so true stand minutes will be higher, while true step")
            creator.show_text(
                "  count may vary in either direction from recorded values.")

        if print_food_data:
            if self.verbose:
                print("Adding food data report...")
            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(16)
            creator.show_text("Food Data Analysis")
            creator.newline()
            creator.set_leading(10)
            creator.set_font("MesloLGS NF", 10)
            text1 = _right_pad_with_spaces("Total food records:      "
                                           + str(food_data.record_count), 45)
            text2 = _right_pad_with_spaces("Earliest food record:    "
                                           + food_data.meal_times[0].strftime("%B %d, %Y"), 45)
            text3 = _right_pad_with_spaces("Most recent food record: "
                                           + food_data.meal_times[-1].strftime("%B %d, %Y"), 45)
            creator.show_text(text1 + " Total meals recorded:  "
                              + str(len(food_data.meal_times)))
            creator.show_text(text2 + " Total dates recorded:  "
                              + str(len(food_data.dates_recorded)))
            creator.show_text(text3 + " Average meals per day: "
                              + str(food_data.avg_meals_per_day))
            creator.newline()
            creator.newline()
            creator.set_font("MesloLGS NF Bold", 10)
            creator.show_text("Most common foods recorded")
            creator.newline()
            creator.show_image(food_data.save_loc, 150, width=250)

            creator.newline()
            creator.set_leading(9)
            creator.set_font("MesloLGS NF", 8)
            creator.show_text(
                "                                                   NOTES")

            if food_data.has_warning_diets() or food_data.has_danger_diets():
                creator.show_text(
                    "Certain diets are contraindicated by the foods found. These include:")
                if food_data.has_danger_diets():
                    creator.show_text(_wrap_text_to_fit_length(
                        "   DANGER: " + ", ".join(food_data.get_top_n_danger_diets(10)), 100))
                if food_data.has_warning_diets():
                    creator.show_text(_wrap_text_to_fit_length(
                        "  WARNING: " + ", ".join(food_data.get_top_n_warning_diets(10)), 100))

        creator.add_header_and_footer()
        creator.save()
