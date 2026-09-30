from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from health_data_parser.utils.translations import _

ABNORMAL_COLOR = "red"


def sort_key(value):
    """Orders blanks first, then numbers (including numeric text such as a
    lab value string) and datetimes, then other text case-insensitively,
    within a column."""
    if value is None or value == "":
        return (0, 0)
    if isinstance(value, (int, float, datetime)) and not isinstance(value, bool):
        return (1, value)
    try:
        return (1, float(value))
    except (TypeError, ValueError):
        return (2, str(value).casefold())


class RowsModel(QAbstractTableModel):
    """Read-only table of row tuples. `highlight(row)` marks rows shown in red."""

    def __init__(self, headers, rows=(), highlight=None, parent=None):
        super().__init__(parent)
        self._headers = list(headers)
        self._rows = list(rows)
        self._highlight = highlight

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_values(self, row):
        return self._rows[row]

    def sort_value(self, row, column):
        return sort_key(self._rows[row][column])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        value = row[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.ForegroundRole and self._highlight is not None and self._highlight(row):
            return QColor(ABNORMAL_COLOR)
        return None


class SortFilterProxy(QSortFilterProxyModel):
    """Sorts by the source model's sort_value(row, column); the fixed-string
    filter matches any column, ignoring case.

    Sort keys are compared in Python rather than passed through a data role,
    so they keep their Python types (a QVariant round trip would convert
    datetimes and tuples).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)

    def lessThan(self, left, right):
        source = self.sourceModel()
        return source.sort_value(left.row(), left.column()) < source.sort_value(right.row(), right.column())


def lab_results_model(parent=None):
    """Rows from analysis.summary.lab_result_rows; abnormal results in red."""
    return RowsModel([_("Date"), _("Test"), _("Value"), _("Range"), _("Status")],
                     highlight=lambda row: row[4] not in ("", _("Normal")), parent=parent)


def vitals_model(parent=None):
    """Rows from analysis.summary.vital_sign_rows."""
    return RowsModel([_("Vital"), _("Unit"), _("Most Recent"), _("Date"), _("Min"), _("Max"),
                      _("Average"), _("Count")], parent=parent)


class SymptomsModel(QAbstractTableModel):
    """An editable list of Symptoms, one per row."""

    COLUMNS = ("name", "start", "end", "medications", "stimulants", "comment", "severity")

    def __init__(self, symptoms=(), parent=None):
        super().__init__(parent)
        self._symptoms = list(symptoms)

    @property
    def symptoms(self):
        return list(self._symptoms)

    def set_symptoms(self, symptoms):
        self.beginResetModel()
        self._symptoms = list(symptoms)
        self.endResetModel()

    def symptom_at(self, row):
        return self._symptoms[row]

    def append(self, symptom):
        self.insert(len(self._symptoms), symptom)

    def insert(self, row, symptom):
        self.beginInsertRows(QModelIndex(), row, row)
        self._symptoms.insert(row, symptom)
        self.endInsertRows()

    def replace(self, row, symptom):
        self._symptoms[row] = symptom
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.COLUMNS) - 1))

    def remove(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        symptom = self._symptoms.pop(row)
        self.endRemoveRows()
        return symptom

    def sort_value(self, row, column):
        symptom = self._symptoms[row]
        return sort_key({
            "name": symptom.name,
            "start": symptom.start_date,
            "end": symptom.end_date,
            "medications": ", ".join(symptom.medications),
            "stimulants": ", ".join(symptom.stimulants),
            "comment": symptom.comment,
            "severity": symptom.severity,
        }[self.COLUMNS[column]])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._symptoms)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return [_("Name"), _("Start Date"), _("End Date"), _("Medications"), _("Stimulants"),
                    _("Comment"), _("Severity")][section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        symptom = self._symptoms[index.row()]
        column = self.COLUMNS[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return {
                "name": symptom.name,
                "start": symptom.start_text,
                "end": symptom.end_text,
                "medications": ", ".join(symptom.medications),
                "stimulants": ", ".join(symptom.stimulants),
                "comment": symptom.comment,
                "severity": str(symptom.severity),
            }[column]
        return None


class SymptomFilterProxy(SortFilterProxy):
    """Filters symptoms by search text (name, medications, stimulants,
    comment), resolved status, and overlap with a date range."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search = ""
        self._show_resolved = True
        # (first date, last date) as datetime.date, or None for any dates
        self._date_range = None

    def set_search(self, text):
        self._search = text.casefold()
        self.invalidateFilter()

    def set_show_resolved(self, show):
        self._show_resolved = show
        self.invalidateFilter()

    def set_date_range(self, date_range):
        self._date_range = date_range
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        symptom = self.sourceModel().symptom_at(source_row)
        if not self._show_resolved and symptom.is_resolved:
            return False
        if self._date_range is not None:
            first = datetime.combine(self._date_range[0], datetime.min.time())
            last = datetime.combine(self._date_range[1], datetime.max.time())
            start = symptom.start_date or datetime.min
            end = symptom.end_date or datetime.max
            if not (start <= last and end >= first):
                return False
        if self._search:
            text = " ".join([symptom.name, ",".join(symptom.medications),
                             ",".join(symptom.stimulants), symptom.comment]).casefold()
            if self._search not in text:
                return False
        return True
