import re

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLineEdit, QListWidget, QPushButton,
    QVBoxLayout, QWidget)

from health_data_parser.utils.translations import _

ISO_DATE_FORMAT = "yyyy-MM-dd"
MONTH_FORMAT = "yyyy-MM"


def date_edit(parent=None, display_format=ISO_DATE_FORMAT):
    edit = QDateEdit(QDate.currentDate(), parent)
    edit.setCalendarPopup(True)
    edit.setDisplayFormat(display_format)
    return edit


class PathField(QWidget):
    """A path with a Browse button. With `history`, the path is an editable
    combo box that also offers previously used paths."""
    changed = Signal()

    DIRECTORY = "directory"
    FILE = "file"

    def __init__(self, mode, caption, file_filter="", history=False, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._caption = caption
        self._file_filter = file_filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if history:
            self._combo = QComboBox()
            self._combo.setEditable(True)
            self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self._line = self._combo.lineEdit()
            layout.addWidget(self._combo, 1)
        else:
            self._combo = None
            self._line = QLineEdit()
            layout.addWidget(self._line, 1)
        self._line.setClearButtonEnabled(True)
        self._line.textChanged.connect(self.changed)

        self.browse_button = QPushButton(_("Browse..."))
        self.browse_button.clicked.connect(self._browse)
        layout.addWidget(self.browse_button)

    def path(self):
        """The entered path, or "" for none."""
        return self._line.text().strip()

    def set_path(self, path):
        self._line.setText(path or "")

    def set_placeholder(self, text):
        self._line.setPlaceholderText(text)

    def set_history(self, paths):
        """Offer `paths` in the drop-down, keeping the current text."""
        if self._combo is None:
            return
        text = self._line.text()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(paths)
        self._combo.blockSignals(False)
        self._line.setText(text)

    def history(self):
        if self._combo is None:
            return []
        return [self._combo.itemText(i) for i in range(self._combo.count())]

    def _browse(self):
        if self._mode == self.DIRECTORY:
            path = QFileDialog.getExistingDirectory(self, self._caption, self.path())
        else:
            path, selected_filter = QFileDialog.getOpenFileName(
                self, self._caption, self.path(), self._file_filter)
        if path:
            self.set_path(path)


class SkipDatesEditor(QWidget):
    """A sorted list of distinct dates, added with a calendar picker."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.list = QListWidget()
        self.list.setMaximumHeight(90)
        self.date_edit = date_edit()
        self.add_button = QPushButton(_("Add"))
        self.remove_button = QPushButton(_("Remove"))
        self.add_button.clicked.connect(
            lambda: self.add_date(self.date_edit.date().toString(ISO_DATE_FORMAT)))
        self.remove_button.clicked.connect(self.remove_selected)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.date_edit, 1)
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(controls)

    def dates(self):
        """The dates as YYYY-MM-DD strings, in order."""
        return tuple(self.list.item(i).text() for i in range(self.list.count()))

    def set_dates(self, dates):
        self.list.clear()
        self.list.addItems(sorted(set(dates)))
        self.changed.emit()

    def add_date(self, iso_date):
        if iso_date in self.dates():
            return
        self.set_dates(self.dates() + (iso_date,))

    def remove_selected(self):
        selected = {item.text() for item in self.list.selectedItems()}
        if selected:
            self.set_dates([date for date in self.dates() if date not in selected])


class SymptomDateEdit(QWidget):
    """A symptom start or end cell: not set, a month, a day, or other text
    (such as "Chronic") kept as entered."""
    changed = Signal()

    NOT_SET, MONTH, DAY, TEXT = range(4)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.precision = QComboBox()
        self.precision.addItems([_("Not set"), _("Month"), _("Day"), _("Other text")])
        self.date_edit = date_edit()
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText(_("e.g. Chronic"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.precision)
        layout.addWidget(self.date_edit, 1)
        layout.addWidget(self.text_edit, 1)

        self.precision.currentIndexChanged.connect(self._precision_changed)
        self.date_edit.dateChanged.connect(self.changed)
        self.text_edit.textChanged.connect(self.changed)
        self._precision_changed()

    def text(self):
        """The cell text: "", YYYY-MM, YYYY-MM-DD or the other text."""
        precision = self.precision.currentIndex()
        if precision == self.MONTH:
            return self.date_edit.date().toString(MONTH_FORMAT)
        if precision == self.DAY:
            return self.date_edit.date().toString(ISO_DATE_FORMAT)
        if precision == self.TEXT:
            return self.text_edit.text().strip()
        return ""

    def set_text(self, text):
        text = (text or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) and QDate.fromString(text, ISO_DATE_FORMAT).isValid():
            self.date_edit.setDate(QDate.fromString(text, ISO_DATE_FORMAT))
            self.precision.setCurrentIndex(self.DAY)
        elif re.fullmatch(r"\d{4}-\d{2}", text) and QDate.fromString(text, MONTH_FORMAT).isValid():
            self.date_edit.setDate(QDate.fromString(text, MONTH_FORMAT))
            self.precision.setCurrentIndex(self.MONTH)
        elif text:
            self.text_edit.setText(text)
            self.precision.setCurrentIndex(self.TEXT)
        else:
            self.precision.setCurrentIndex(self.NOT_SET)

    def _precision_changed(self):
        precision = self.precision.currentIndex()
        self.date_edit.setHidden(precision not in (self.MONTH, self.DAY))
        self.date_edit.setDisplayFormat(MONTH_FORMAT if precision == self.MONTH else ISO_DATE_FORMAT)
        self.text_edit.setHidden(precision != self.TEXT)
        self.changed.emit()
