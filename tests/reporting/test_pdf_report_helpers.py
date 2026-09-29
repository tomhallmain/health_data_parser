import pytest

from health_data_parser.reporting.pdf.report import (
    _filter_table, _find_rows_and_columns_to_skip, _get_conditional_format_styles,
    _right_pad_with_spaces, _wrap_text_to_fit_length)


class TestWrapTextToFitLength:
    def test_short_text_is_unchanged(self):
        assert _wrap_text_to_fit_length("Glucose", 10) == "Glucose"

    def test_breaks_at_last_space_within_limit(self):
        assert _wrap_text_to_fit_length("Hemoglobin A1c", 12) == "Hemoglobin\nA1c"

    def test_text_without_spaces_is_cut_at_limit(self):
        assert _wrap_text_to_fit_length("abcdefghij", 4) == "abcd\nefgh\nij"

    def test_no_line_exceeds_limit(self):
        wrapped = _wrap_text_to_fit_length("Comprehensive Metabolic Panel With eGFR", 15)
        assert all(len(line) <= 15 for line in wrapped.split("\n"))

    def test_later_lines_also_break_at_spaces(self):
        assert _wrap_text_to_fit_length("one two three four", 9) == "one two\nthree\nfour"


def test_right_pad_with_spaces():
    assert _right_pad_with_spaces("abc", 6) == "abc   "
    assert _right_pad_with_spaces("abcdef", 3) == "abcdef"


class TestConditionalFormatStyles:
    TABLE = [["Glucose", "70-99", "105 mg/dL+++", "", "90 mg/dL"],
             ["Hemoglobin", "13.5-17.5", "13.6 g/dL--", "POSITIVE+", None]]

    def test_highlights_abnormal_results(self):
        styles = _get_conditional_format_styles(self.TABLE, True)
        assert styles == [
            ("BACKGROUND", (2, 0), (2, 0), "Pink"),
            ("BACKGROUND", (3, 0), (3, 0), "Lightgrey"),
            ("BACKGROUND", (2, 1), (2, 1), "peachpuff"),
            ("BACKGROUND", (3, 1), (3, 1), "peachpuff"),
        ]

    def test_without_highlighting_only_empty_cells_are_shaded(self):
        assert _get_conditional_format_styles(self.TABLE, False) == [
            ("BACKGROUND", (3, 0), (3, 0), "Lightgrey")]


class TestTableFiltering:
    # Rows as built for the PDF, before the header row is inserted at index 0
    TABLE = [["Glucose", "70-99", "105 mg/dL+++", ""],
             ["Iron", "", "", ""],
             ["Ferritin", "30-400", "", "20 ng/mL---"]]

    def test_rows_and_columns_without_results_are_skipped(self):
        rows_to_skip, columns_to_skip = _find_rows_and_columns_to_skip(self.TABLE)
        # Row indexes are offset by one for the header row
        assert rows_to_skip == [2]
        assert columns_to_skip == []

    def test_empty_result_column_is_skipped(self):
        table = [row[:3] + [""] for row in self.TABLE[:1]]
        assert _find_rows_and_columns_to_skip(table) == ([], [3])

    def test_empty_table(self):
        assert _find_rows_and_columns_to_skip([]) == ([], [])

    def test_filter_table(self):
        header = ["Observation Code", "Range", "2023-04-05", "2022-11-20"]
        table = [header] + self.TABLE
        assert _filter_table(table, [2], [1]) == [
            ["Observation Code", "2023-04-05", "2022-11-20"],
            ["Glucose", "105 mg/dL+++", ""],
            ["Ferritin", "", "20 ng/mL---"],
        ]
