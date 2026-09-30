from datetime import date, datetime

from PySide6.QtCore import Qt

from health_data_parser.gui.models import (
    RowsModel, SortFilterProxy, SymptomFilterProxy, SymptomsModel, lab_results_model,
    sort_key)
from health_data_parser.model.symptom import Symptom
from health_data_parser.utils.translations import _

DISPLAY = Qt.ItemDataRole.DisplayRole


def column(model, col=0):
    return [model.index(row, col).data(DISPLAY) for row in range(model.rowCount())]


def symptom(name, start="", end="", medications="", comment="", severity=1):
    return Symptom([name, start, end, medications, "", comment, str(severity)])


class TestSortKey:
    def test_numbers_and_numeric_text_sort_by_value(self):
        assert sorted(["10", 9, "2.5"], key=sort_key) == ["2.5", 9, "10"]

    def test_blanks_first_then_numbers_then_text(self):
        assert sorted(["b", 3, "", None, "A"], key=sort_key) == ["", None, 3, "A", "b"]

    def test_datetimes(self):
        assert sort_key(datetime(2020, 1, 1)) < sort_key(datetime(2021, 1, 1))


class TestRowsModel:
    def test_display_and_headers(self):
        model = RowsModel(["A", "B"], [("x", 1.5), ("y", None)])

        assert (model.rowCount(), model.columnCount()) == (2, 2)
        assert model.headerData(1, Qt.Orientation.Horizontal) == "B"
        assert column(model, 1) == ["1.5", ""]
        assert model.sort_value(0, 1) == (1, 1.5)

    def test_lab_results_highlight_abnormal_status(self):
        model = lab_results_model()
        model.set_rows([
            ("2023-01-01", "Glucose", "105", "70-99", _("High")),
            ("2023-01-01", "Iron", "80", "50-150", _("Normal")),
            ("2023-01-01", "Note", "text", "", ""),
        ])

        colors = [model.index(row, 0).data(Qt.ItemDataRole.ForegroundRole) for row in range(3)]
        assert colors[0] is not None
        assert colors[1:] == [None, None]

    def test_proxy_sorts_numeric_text_by_value_and_filters(self):
        model = RowsModel(["Test", "Value"], [("A", "10"), ("b", "9"), ("C", "100")])
        proxy = SortFilterProxy()
        proxy.setSourceModel(model)

        proxy.sort(1, Qt.SortOrder.AscendingOrder)
        assert column(proxy, 1) == ["9", "10", "100"]

        proxy.setFilterFixedString("B")
        assert column(proxy) == ["b"]


class TestSymptomsModel:
    def test_display_and_sort_values(self):
        model = SymptomsModel([symptom("Headache", "2021-02", "Chronic", "Med A, Med B", severity=3)])

        assert [model.index(0, c).data(DISPLAY) for c in range(7)] == [
            "Headache", "2021-02", "Chronic", "Med A, Med B", "", "", "3"]
        assert model.sort_value(0, 1) == (1, datetime(2021, 2, 1))
        assert model.sort_value(0, 6) == (1, 3)

    def test_editing(self):
        model = SymptomsModel([symptom("A"), symptom("B")])

        model.append(symptom("C"))
        model.replace(0, symptom("A2"))
        removed = model.remove(1)
        model.insert(0, removed)

        assert [s.name for s in model.symptoms] == ["B", "A2", "C"]

    def test_sort_by_start_date_puts_undated_first(self):
        model = SymptomsModel([symptom("Later", "2022-01-01"), symptom("Undated"), symptom("Earlier", "2020-05")])
        proxy = SymptomFilterProxy()
        proxy.setSourceModel(model)

        proxy.sort(1, Qt.SortOrder.AscendingOrder)

        assert column(proxy) == ["Undated", "Earlier", "Later"]


class TestSymptomFilterProxy:
    def make(self):
        model = SymptomsModel([
            symptom("Headache", "2021-02", "2021-06-15", medications="Medication A"),
            symptom("Fatigue", "2020-03", comment="Afternoons"),
            symptom("Rash", "2023-01-10", "2023-02-01"),
        ])
        proxy = SymptomFilterProxy()
        proxy.setSourceModel(model)
        return proxy

    def test_search_covers_medications_and_comments_ignoring_case(self):
        proxy = self.make()

        proxy.set_search("medication a")
        assert column(proxy) == ["Headache"]
        proxy.set_search("AFTERNOON")
        assert column(proxy) == ["Fatigue"]

    def test_hide_resolved(self):
        proxy = self.make()

        proxy.set_show_resolved(False)

        assert column(proxy) == ["Fatigue"]

    def test_date_range_keeps_overlapping_symptoms(self):
        proxy = self.make()

        proxy.set_date_range((date(2021, 6, 15), date(2022, 1, 1)))
        assert column(proxy) == ["Headache", "Fatigue"]

        proxy.set_date_range(None)
        assert proxy.rowCount() == 3
