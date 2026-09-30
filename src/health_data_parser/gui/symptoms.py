import os

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QRadioButton, QSpinBox, QTableView, QVBoxLayout, QWidget)

from health_data_parser.gui.models import SymptomFilterProxy, SymptomsModel
from health_data_parser.gui.widgets import SymptomDateEdit, date_edit
from health_data_parser.ingest.symptoms_csv import InvalidSymptomFile, read_symptoms, write_symptoms
from health_data_parser.model.symptom import ImportMode, Symptom, import_symptoms, parse_symptom_date
from health_data_parser.utils.logger import setup_logger
from health_data_parser.utils.translations import _

logger = setup_logger('symptom_manager')

_CSV_FILTER = "CSV (*.csv);;All files (*)"


class SymptomDialog(QDialog):
    """Adds or edits one symptom. After exec() returns Accepted, symptom()
    is the entered symptom."""

    def __init__(self, symptom=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Edit Symptom") if symptom else _("Add Symptom"))

        self.name = QLineEdit()
        self.start = SymptomDateEdit()
        self.end = SymptomDateEdit()
        self.medications = QLineEdit()
        self.medications.setPlaceholderText(_("Comma-separated"))
        self.stimulants = QLineEdit()
        self.stimulants.setPlaceholderText(_("Comma-separated"))
        self.comment = QLineEdit()
        self.severity = QSpinBox()
        self.severity.setRange(1, 10)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        form = QFormLayout()
        form.addRow(_("Name:"), self.name)
        form.addRow(_("Start date:"), self.start)
        form.addRow(_("End date:"), self.end)
        form.addRow(_("Medications:"), self.medications)
        form.addRow(_("Stimulants:"), self.stimulants)
        form.addRow(_("Comment:"), self.comment)
        form.addRow(_("Severity (1-10):"), self.severity)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        if symptom is not None:
            self.name.setText(symptom.name)
            self.start.set_text(symptom.start_text)
            self.end.set_text(symptom.end_text)
            self.medications.setText(", ".join(symptom.medications))
            self.stimulants.setText(", ".join(symptom.stimulants))
            self.comment.setText(symptom.comment)
            self.severity.setValue(max(1, min(10, symptom.severity)))

    def validation_error(self):
        """Why the entries can't be saved, or None."""
        if not self.name.text().strip():
            return _("Name is required.")
        start = parse_symptom_date(self.start.text())
        end = parse_symptom_date(self.end.text())
        if start is not None and end is not None and end < start:
            return _("The end date is before the start date.")
        return None

    def symptom(self):
        return Symptom([self.name.text().strip(), self.start.text(), self.end.text(),
                        self.medications.text(), self.stimulants.text(), self.comment.text().strip(),
                        str(self.severity.value())])

    def accept(self):
        error = self.validation_error()
        if error is not None:
            self.error_label.setText(error)
            self.error_label.show()
            return
        super().accept()


class ImportModeDialog(QDialog):
    """Asks how imported symptoms combine with the current ones."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Import Symptoms"))
        self._group = QButtonGroup(self)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Import mode:")))
        for mode, label in [
                (ImportMode.APPEND, _("Append to the current symptoms")),
                (ImportMode.REPLACE, _("Replace the current symptoms")),
                (ImportMode.MERGE, _("Merge: update symptoms with the same name and dates, add the rest"))]:
            button = QRadioButton(label)
            button.setProperty("mode", mode.value)
            button.setChecked(mode is ImportMode.APPEND)
            self._group.addButton(button)
            layout.addWidget(button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def mode(self):
        return ImportMode(self._group.checkedButton().property("mode"))


class SymptomManager(QWidget):
    """Edits a symptom CSV: search, filter, sort, add/edit/delete with undo,
    import and export.

    Every question to the user goes through an ask_* method, so tests can
    replace them.
    """
    # The file shown, or "" for none
    file_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = ""
        self.dirty = False
        # (row, symptom) per delete, most recent last
        self._deleted = []

        self.model = SymptomsModel(parent=self)
        self.proxy = SymptomFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.set_show_resolved(False)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(lambda index: self.edit_symptom())

        self.file_label = QLabel()
        self.buttons = {}
        toolbar = QHBoxLayout()
        for key, label, slot in [
                ("open", _("Open..."), self.open_file_dialog),
                ("save", _("Save"), self.save),
                ("import", _("Import..."), self.import_csv),
                ("export", _("Export..."), self.export_csv),
                ("add", _("Add..."), self.add_symptom),
                ("edit", _("Edit..."), self.edit_symptom),
                ("delete", _("Delete"), self.delete_symptom),
                ("undo", _("Undo Delete"), self.undo_delete)]:
            button = QPushButton(label)
            button.clicked.connect(slot)
            self.buttons[key] = button
            toolbar.addWidget(button)
        toolbar.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Search names, medications, stimulants and comments"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.proxy.set_search)
        self.show_resolved = QCheckBox(_("Show resolved"))
        self.show_resolved.toggled.connect(self.proxy.set_show_resolved)
        self.date_filter = QCheckBox(_("Between"))
        self.date_from = date_edit()
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_to = date_edit()
        self.date_filter.toggled.connect(self._update_date_filter)
        self.date_from.dateChanged.connect(self._update_date_filter)
        self.date_to.dateChanged.connect(self._update_date_filter)

        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(self.show_resolved)
        filters.addWidget(self.date_filter)
        filters.addWidget(self.date_from)
        filters.addWidget(QLabel(_("and")))
        filters.addWidget(self.date_to)

        layout = QVBoxLayout(self)
        layout.addWidget(self.file_label)
        layout.addLayout(toolbar)
        layout.addLayout(filters)
        layout.addWidget(self.table, 1)

        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self.model.modelReset.connect(self._update_buttons)
        self._update_date_filter()
        self._update_state()

    # --- Questions to the user; tests replace these ---------------------------

    def ask_symptom(self, symptom=None):
        """The added or edited symptom, or None if cancelled."""
        dialog = SymptomDialog(symptom, self)
        if dialog.exec():
            return dialog.symptom()
        return None

    def ask_import_mode(self):
        dialog = ImportModeDialog(self)
        if dialog.exec():
            return dialog.mode()
        return None

    def ask_open_path(self, title):
        path, selected_filter = QFileDialog.getOpenFileName(self, title, self._directory(), _CSV_FILTER)
        return path

    def ask_save_path(self, title):
        path, selected_filter = QFileDialog.getSaveFileName(self, title, self.path or self._directory(),
                                                            _CSV_FILTER)
        return path

    def ask_yes_no(self, title, text):
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def ask_unsaved_changes(self):
        """Save, Discard or Cancel."""
        return QMessageBox.question(
            self, _("Unsaved Symptoms"), _("Save the changes to the symptoms first?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)

    def show_message(self, title, text, error=False):
        if error:
            QMessageBox.critical(self, title, text)
        else:
            QMessageBox.information(self, title, text)

    # --- Files ----------------------------------------------------------------

    def _directory(self):
        return os.path.dirname(self.path) if self.path else ""

    def open_file(self, path):
        """Show the symptoms in `path` (a missing file shows none, and is
        created on save). False if the file couldn't be read."""
        symptoms = []
        if os.path.exists(path):
            try:
                symptoms, errors = read_symptoms(path)
            except Exception as e:
                self.show_message(_("Error"), _("Failed to read \"{0}\": {1}").format(path, e), error=True)
                return False
            for row_number, error in errors:
                logger.error(f"Error loading symptom in row {row_number}: {error}")
            if errors:
                self.show_message(_("Invalid Rows"), _("{0} rows could not be read and were left out.")
                                  .format(len(errors)), error=True)
        self.path = path
        self.model.set_symptoms(symptoms)
        self._deleted = []
        self.dirty = False
        self._update_state()
        self.file_changed.emit(path)
        return True

    def open_file_dialog(self):
        if not self.maybe_save():
            return
        path = self.ask_open_path(_("Open Symptoms"))
        if path:
            self.open_file(path)

    def save(self):
        """Write the symptoms to the current file (asking for one if there is
        none). True if saved."""
        if not self.path:
            path = self.ask_save_path(_("Save Symptoms"))
            if not path:
                return False
            self.path = path
            self.file_changed.emit(path)
        try:
            write_symptoms(self.path, self.model.symptoms)
        except Exception as e:
            self.show_message(_("Error"), _("Failed to save symptoms: {0}").format(e), error=True)
            return False
        self.dirty = False
        self._update_state()
        return True

    def maybe_save(self):
        """Resolve unsaved changes before they would be lost. False if the
        user cancelled."""
        if not self.dirty:
            return True
        answer = self.ask_unsaved_changes()
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def import_csv(self):
        path = self.ask_open_path(_("Import Symptoms"))
        if not path:
            return
        try:
            imported, errors = read_symptoms(path, require_known_header=True)
        except InvalidSymptomFile as e:
            self.show_message(_("Error"), str(e), error=True)
            return
        except Exception as e:
            self.show_message(_("Error"), _("Failed to import CSV: {0}").format(e), error=True)
            return
        for row_number, error in errors:
            logger.error(f"Error in row {row_number}: {error}")
        if errors and not self.ask_yes_no(
                _("Invalid Rows"),
                _("Found {0} invalid rows. Continue importing valid rows?").format(len(errors))):
            return
        mode = self.ask_import_mode()
        if mode is None:
            return
        symptoms, updated = import_symptoms(self.model.symptoms, imported, mode)
        self.model.set_symptoms(symptoms)
        self._deleted = []
        self._mark_dirty()
        if mode is ImportMode.MERGE:
            message = _("Updated {0} symptoms and added {1}.").format(updated, len(imported) - updated)
        elif mode is ImportMode.REPLACE:
            message = _("Replaced the symptoms with {0} imported symptoms.").format(len(imported))
        else:
            message = _("Added {0} symptoms.").format(len(imported))
        self.show_message(_("Import Complete"), message)

    def export_csv(self):
        path = self.ask_save_path(_("Export Symptoms"))
        if not path:
            return
        try:
            write_symptoms(path, self.model.symptoms)
        except Exception as e:
            self.show_message(_("Error"), _("Failed to export CSV: {0}").format(e), error=True)
            return
        self.show_message(_("Export Complete"),
                          _("Exported {0} symptoms.").format(self.model.rowCount()))

    # --- Editing --------------------------------------------------------------

    def selected_row(self):
        """The model row of the selected symptom, or None."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.proxy.mapToSource(rows[0]).row()

    def select_row(self, row):
        index = self.proxy.mapFromSource(self.model.index(row, 0))
        if index.isValid():
            self.table.selectRow(index.row())

    def add_symptom(self):
        symptom = self.ask_symptom()
        if symptom is None:
            return
        self.model.append(symptom)
        self._mark_dirty()
        self.select_row(self.model.rowCount() - 1)

    def edit_symptom(self):
        row = self.selected_row()
        if row is None:
            return
        symptom = self.ask_symptom(self.model.symptom_at(row))
        if symptom is None:
            return
        self.model.replace(row, symptom)
        self._mark_dirty()

    def delete_symptom(self):
        row = self.selected_row()
        if row is None:
            return
        self._deleted.append((row, self.model.remove(row)))
        self._mark_dirty()

    def undo_delete(self):
        if not self._deleted:
            return
        row, symptom = self._deleted.pop()
        row = min(row, self.model.rowCount())
        self.model.insert(row, symptom)
        self._mark_dirty()
        self.select_row(row)

    # --- State ----------------------------------------------------------------

    def _mark_dirty(self):
        self.dirty = True
        self._update_state()

    def _update_state(self):
        name = self.path or _("(no file)")
        self.file_label.setText(_("{0} (unsaved changes)").format(name) if self.dirty else name)
        self._update_buttons()

    def _update_buttons(self, *args):
        has_selection = self.selected_row() is not None
        self.buttons["edit"].setEnabled(has_selection)
        self.buttons["delete"].setEnabled(has_selection)
        self.buttons["undo"].setEnabled(bool(self._deleted))

    def _update_date_filter(self, *args):
        enabled = self.date_filter.isChecked()
        self.date_from.setEnabled(enabled)
        self.date_to.setEnabled(enabled)
        self.proxy.set_date_range(
            (self.date_from.date().toPython(), self.date_to.date().toPython()) if enabled else None)
