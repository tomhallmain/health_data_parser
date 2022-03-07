from datetime import datetime
import operator
import re
import matplotlib.pyplot as plt

from pdf_creator import pdf_creator

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



def _get_conditional_format_styles(table: list, highlight_abnormal: bool):
    conditional_formats = []
    for r in range(len(table)):
        row = table[r]
        for c in range(len(row)):
            if c < 2:
                continue
            cell_value = row[c]
            if cell_value == None:
                continue
            elif cell_value == "":
                conditional_formats.append(("BACKGROUND", (c,r), (c,r), "Lightgrey"))
            elif highlight_abnormal:
                if ("+++" in cell_value or "---" in cell_value):
                    conditional_formats.append(("BACKGROUND", (c,r), (c,r), "Pink"))
                elif ("++" in cell_value or "--" in cell_value):
                    conditional_formats.append(("BACKGROUND", (c,r), (c,r), "peachpuff"))
                elif (cell_value[-1] == "+"):
                    conditional_formats.append(("BACKGROUND", (c,r), (c,r), "peachpuff"))
    return conditional_formats


def _find_rows_and_columns_to_skip(table: list):
    if table == None or len(table) == 0:
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
            if not cell_value == None and not cell_value == "" and re.search("[A-z0-9]", cell_value):
                if col_index in columns_to_skip:
                    columns_to_skip.remove(col_index)
                if not col_index in columns_to_print:
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
            if not col_index in columns_to_skip:
                filtered_row.append(row[col_index])
        filtered_table.append(filtered_row)
    
    return filtered_table

class Report:
    def __init__(self, output_path: str, subject: str, metadata: dict, verbose: bool, highlight_abnormal: bool):
        self.output_path = output_path
        self.subject = subject
        self.verbose = verbose
        self.highlight_abnormal = highlight_abnormal
        self.filename = "LaboratoryResultsReport" + metadata["meta"]["processTime"][:10] + ".pdf"
        self.filepath = self.output_path + "/" + self.filename

        if not "meta" in metadata or not "observations" in metadata:
            raise AssertionError("Observations data not found.")
        elif len(metadata["observations"]) == 0:
            raise AssertionError("Observations data not found.")

    def create_pdf(self, metadata: dict, observations: dict, observation_dates: list, observation_code_ids: dict, ranges: dict, 
                   date_codes: dict, reference_dates: list, abnormal_results: dict, abnormal_result_dates: list):
        if self.verbose:
            print("\nCreating report cover page...")
        creator = pdf_creator(800, 50, self.filepath, self.verbose)
        creator.set_font("MesloLGS NF Bold", 15)
        meta = metadata["meta"]
        creator.show_text(meta["description"])
        creator.set_font("MesloLGS NF", 12)
        creator.set_leading(14)
        creator.newline()
        creator.newline()
        creator.newline()

        if self.subject == None or self.subject == "":
            creator.show_text("Subject:            UNKNOWN")
        else:
            creator.show_text("Subject:            " + self.subject)
        
        creator.show_text("Observation count:  " + str(meta["observationCount"]))
        creator.show_text("Earliest result:    " + datetime.fromisoformat(meta["earliestResult"]).strftime("%B %d, %Y"))
        creator.show_text("Most recent result: " + datetime.fromisoformat(meta["mostRecentResult"]).strftime("%B %d, %Y"))
        creator.show_text("Report assembled:   " + datetime.fromisoformat(meta["processTime"][:10]).strftime("%B %d, %Y"))
        
        if meta["vitalSignsObservationCount"] > 0:
            creator.newline()
            creator.newline()
            creator.newline()

            creator.set_font("MesloLGS NF Bold", 12)
            creator.show_text("Summary of Vitals")
            creator.set_font("MesloLGS NF", 12)

            creator.newline()
            creator.show_text("Vital sign observation dates count:  " + str(meta["vitalSignsObservationCount"]))
            creator.newline()

            creator.set_font("MesloLGS NF", 8)
            creator.set_leading(8)

            # TODO add Trend column and/or graph of these vitals
            vital_signs_table = [["Vital", "Unit", "Most Recent", "Date", "Average", "StDev"]]
            
            for vital in metadata["vitalSigns"]:
                row = [vital["vital"], vital["unit"]]
                if vital["count"] > 0:
                    most_recent_obs = vital["list"][-1]
                    row.append(str(round(most_recent_obs["value"], 1)))
                    row.append(most_recent_obs["date"])
                    row.append(round(vital["avg"], 1))
                    row.append(round(vital["stDev"], 1))
                    vital_signs_table.append(row)
            
            creator.show_table(vital_signs_table, None, 120)
        
        creator.set_font("MesloLGS NF", 12)
        creator.set_leading(14)
        creator.newline()
        creator.newline()
        creator.newline()

        if "abnormalResults" in metadata:
            creator.set_font("MesloLGS NF Bold", 12)
            creator.show_text("WARNING: Abnormal results were found.")
            creator.set_font("MesloLGS NF", 12)
            creator.newline()
            abnormal_results_meta = metadata["abnormalResults"]["meta"]
            creator.show_text("Lab codes with abnormal observed values: " + str(abnormal_results_meta["codesWithAbnormalResultsCount"]))
            creator.show_text("Total abnormal observations:             " + str(abnormal_results_meta["totalAbnormalResultsCount"]))
            creator.newline()
            includes_in_range = abnormal_results_meta["includesInRangeAbnormalities"]

            ##################################################################################
            ##
            ## ABNORMAL RESULTS SUMMARY TABLE
            ##
            ##################################################################################

            if self.verbose:
                print("Writing abnormal results summary and detail tables...")

            creator.set_leading(10)
            creator.set_font("MesloLGS NF", 9)
            creator.show_text("NOTE: Reference ranges for tests are not static. The range displayed in all tables")
            creator.show_text("represents the most recent range available. A result classified as abnormal by an old")
            creator.show_text("range may be acceptable within current ranges.")
            creator.newline()

            if includes_in_range:
                in_range_boundary_percent = str(round(abnormal_results_meta["inRangeAbnormalBoundary"] * 100)) + "%"
                creator.show_text("Abnormal results may include results within ranges at +/-" + in_range_boundary_percent + " ends of the relevant range.")
                creator.show_text("These are labeled as lower severity with the labels \"High in range\" and \"Low in range\"")
                creator.show_text("or tags \"++\" and \"--\". Tags \"+++\" and \"---\" indicate high and low out of range.")
                creator.show_text("Tag \"+\" indicates a positive result.")
                abnormal_results_table = [["RESULT CODE", "L OUT", "L IN", "OBSERVED", "H IN", "H OUT"]]
            else:
                creator.show_text("All listed abnormal results are out of the relevant range. Tags \"+++\" and \"---\" indicate")
                creator.show_text("high and low out of range. Tag \"+\" indicates a positive result.")
                abnormal_results_table = [["RESULT CODE", "LOW OUT OF RANGE", "OBSERVED", "HIGH OUT OF RANGE"]]

            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(20)
            creator.show_text("Abnormal Results By Code Summary")
            creator.set_leading(10)
            creator.newline()

            abnormal_result_interpretations_by_code = metadata["abnormalResults"]["codesWithAbnormalResults"]

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


            ##################################################################################
            ##
            ## ABNORMAL OBSERVATIONS BY DATE TABLES
            ##
            ##################################################################################
            

            n_dates_in_table_per_page = 9
            header = ["Observation Code", "Range"] if len(reference_dates) > 0 else ["Observation Code"]
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
                    header_dates = header_dates_tables[table_counter] if len(header_dates_tables) > table_counter else []

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
                                row = [_wrap_text_to_fit_length(code, 20), _wrap_text_to_fit_length(ranges[code], 15)]
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
                table = abnormal_results_tables[table_counter] if len(abnormal_results_tables) > table_counter else []
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
                                    abnormal_result_tag = observation.result.interpretation if observation.has_reference else ""
                                    row.append(_wrap_text_to_fit_length(value + abnormal_result_tag, 10))
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
                        table = abnormal_results_tables[table_counter] if len(abnormal_results_tables) > table_counter else []

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
                    rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(table_to_show)
                    if len(rows_to_skip) > 0:
                        extension_amount = len(rows_to_skip)
                        while (len(observations_table) > observation_cutoff
                                and not len(table_to_show) - len(rows_to_skip) >= max_observations_per_page):
                            table_to_show.extend(observations_table[observation_cutoff:(observation_cutoff+extension_amount)])
                            observation_cutoff += extension_amount
                            if self.verbose:
                                print("Extended table by " + str(extension_amount) + " as some rows skipped. New table length: " + str(len(table_to_show)))
                            rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(table_to_show)
                            extension_amount = max_observations_per_page - (len(table_to_show) - len(rows_to_skip))
                    observations_table = observations_table[len(table_to_show):]
                    table_to_show.insert(0, header_row)
                    if len(rows_to_skip) > 0 or len(columns_to_skip) > 0:
                        table_to_show = _filter_table(table_to_show, rows_to_skip, columns_to_skip)
                    creator.add_page()
                    creator.set_font("MesloLGS NF Bold", 15)
                    creator.set_leading(16)
                    if has_shown_first_page:
                        creator.show_text("Abnormal Results By Code (continued)")
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

                    extra_style_commands.extend(_get_conditional_format_styles(table_to_show, False))
                    x_offset = 50 if len(table_to_show[0]) <= 9 else 30
                    creator.show_table(table_to_show, extra_style_commands, x_offset)





            ##################################################################################
            ##
            ## ALL OBSERVATIONS BY DATE TABLES
            ##
            ##################################################################################

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
                    header_dates = header_dates_tables[table_counter] if len(header_dates_tables) > table_counter else []

            if has_unappended_row:
                if len(header_dates_tables) > table_counter:
                    header_dates_tables[table_counter] = header_dates
                else:
                    header_dates_tables.append(header_dates)

            code_ranges_table = []

            for code in sorted(observation_code_ids):
                if len(reference_dates) > 0:
                    if code in ranges:
                        row = [_wrap_text_to_fit_length(code, 20), _wrap_text_to_fit_length(ranges[code], 15)]
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
                table = results_tables[table_counter] if len(results_tables) > table_counter else []
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
                            abnormal_result_tag = observation.result.interpretation if observation.has_reference else ""
                            value = observation.value_string[:15]
                            row.append(_wrap_text_to_fit_length(value + abnormal_result_tag, 10))
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
                        table = results_tables[table_counter] if len(results_tables) > table_counter else []
                 
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
                    rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(table_to_show)
                    if len(rows_to_skip) > 0:
                        extension_amount = len(rows_to_skip)
                        while (len(observations_table) > observation_cutoff
                                and not len(table_to_show) - len(rows_to_skip) >= max_observations_per_page):
                            table_to_show.extend(observations_table[observation_cutoff:(observation_cutoff+extension_amount)])
                            observation_cutoff += extension_amount
                            if self.verbose:
                                print("Extended table by " + str(extension_amount) + " as some rows skipped. New table length including skipped: " + str(len(table_to_show)))
                            rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(table_to_show)
                            extension_amount = max_observations_per_page - (len(table_to_show) - len(rows_to_skip))
                    observations_table = observations_table[len(table_to_show):]
                    table_to_show.insert(0, header_row)
                    if len(rows_to_skip) > 0 or len(columns_to_skip) > 0:
                        table_to_show = _filter_table(table_to_show, rows_to_skip, columns_to_skip)
                    creator.add_page()
                    creator.set_font("MesloLGS NF Bold", 15)
                    creator.set_leading(16)
                    if has_shown_first_page:
                        creator.show_text("All Observations (continued)")
                    else:
                        creator.show_text("All Observations")
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

                    extra_style_commands.extend(_get_conditional_format_styles(table_to_show, self.highlight_abnormal))
                    x_offset = 50 if len(table_to_show[0]) <= 9 else 30
                    creator.show_table(table_to_show, extra_style_commands, x_offset)


        else:
            creator.show_text("No abnormal results were found in Apple Health data export.")


        #creator.text(": " + meta[""], 100, 120)
        creator.save()




