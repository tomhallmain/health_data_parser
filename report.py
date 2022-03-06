import operator
import re

from pdf_creator import pdf_creator

# Assumes newlines not already present
def _wrap_text_to_fit_length(text: str, fit_length: int):
    if len(text) <= fit_length:
        return text
    
    if " " in text and text.index(" ") < len(text) - 2:
        test_new_text = text[:fit_length]
        last_space_block = re.findall(" +", test_new_text)[-1]
        last_space_block_index = test_new_text.rfind(last_space_block)
        new_text = text[:last_space_block_index]
        text = text[(last_space_block_index+len(last_space_block)):]
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
            if highlight_abnormal and ("++" in cell_value or "---" in cell_value):
                conditional_formats.append(("BACKGROUND", (c,r), (c,r), "Pink"))
            elif cell_value == "":
                conditional_formats.append(("BACKGROUND", (c,r), (c,r), "Lightgrey"))
    return conditional_formats


def _find_columns_to_skip(table: list):
    if table == None or len(table) == 0:
        return []
    
    columns_to_skip = list(range(len(table[0])))
    columns_to_print = []
    
    for row in table:
        if len(columns_to_skip) == 0:
            return columns_to_skip

        for col_index in range(len(row)):
            if col_index in columns_to_print:
                continue
            cell_value = row[col_index]
            if not cell_value == "" and re.search("[A-z0-9]", cell_value):
                columns_to_print.append(col_index)
                columns_to_skip.remove(col_index)

    return columns_to_skip

def _filter_table_columns(table: list, columns_to_skip: list):
    filtered_table = []
    
    for row in table:
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

    def create_pdf(self, metadata: dict, observations: dict, observation_dates: list, observation_code_ids: dict, 
                   date_codes: dict, reference_dates: list, abnormal_results: dict, abnormal_result_dates: list):
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
        creator.show_text("Earliest result:    " + meta["earliestResult"])
        creator.show_text("Most recent result: " + str(meta["mostRecentResult"]))
        creator.show_text("Report assembled:   " + meta["processTime"][:10])
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

            if includes_in_range:
                in_range_boundary_percent = str(round(abnormal_results_meta["inRangeAbnormalBoundary"] * 100)) + "%"
                creator.show_text("NOTE: Abnormal results may include results within ranges at +/-" + in_range_boundary_percent)
                creator.show_text("ends of the relevant range. These will be labeled as lower severity")
                creator.show_text("with the labels \"High in range\" and \"Low in range\".")
                abnormal_results_table = [["RESULT CODE", "L OUT", "L IN", "OBSERVED", "H IN", "H OUT"]]
            else:
                creator.show_text("NOTE: All listed abnormal results are out of the relevant range.")
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

            creator.add_page()
            creator.set_font("MesloLGS NF Bold", 15)
            creator.set_leading(16)
            creator.newline()
            creator.show_text("Abnormal Results By Code")
            creator.set_leading(12)
            creator.newline()
            
            for code in sorted(observation_code_ids):
                for code_id in observation_code_ids[code]:
                    if code_id in abnormal_results:
                        creator.set_leading(12)
                        creator.set_font("MesloLGS NF Bold", 12)
                        creator.show_text(code)
                        results = abnormal_results[code_id]
                        creator.set_font("MesloLGS NF", 10)
                        creator.set_leading(10)

                        for observation in sorted(results, key=operator.attrgetter("date")):
                            interpretation = observation.result.get_result_interpretation_text()
                            value_string = observation.value_string
                            while len(interpretation) < 20:
                                interpretation += " "
                            while len(value_string) < 15:
                                value_string = " " + value_string
                            if observation.result.is_range_type:
                                line = observation.date + "          " + interpretation + value_string + "       " + observation.result.range
                            else:
                                line = observation.date + "          " + interpretation + value_string
                            creator.show_text(line)

                        creator.newline()

            ranges = {}
            n_dates_in_table_per_page = 9

            if len(reference_dates) > 0:
                header = ["Observation Codes", "Range"]
                
                for code in sorted(observation_code_ids):
                    range_found = False
                    for date in observation_dates:
                        if range_found:
                            break
                        for code_id in observation_code_ids[code]:
                            datecode = date + code_id
                            if datecode in date_codes:
                                observation = observations[date_codes[datecode]]
                                if date in reference_dates and observation.has_reference:
                                    ranges[code] = observation.result.range_text
                                    range_found = True
                                    break
            else:
                header = ["Observation Codes"]

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

            # results_tables is a list of observation date results up to 5 per page
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
                    table_to_show = observations_table[:max_observations_per_page]
                    observations_table = observations_table[max_observations_per_page:]
                    columns_to_skip = _find_columns_to_skip(table_to_show)
                    table_to_show.insert(0, header_row)
                    if len(columns_to_skip) > 0:
                        table_to_show = _filter_table_columns(table_to_show, columns_to_skip)
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

                    creator.show_table(table_to_show, extra_style_commands, 20)


        else:
            creator.show_text("No abnormal results were found in Apple Health data export.")


        #creator.text(": " + meta[""], 100, 120)
        creator.save()




