import pytest
from PySide6.QtWidgets import QMessageBox

from health_data_parser.gui.symptoms import ImportModeDialog, SymptomDialog, SymptomManager
from health_data_parser.gui.widgets import SymptomDateEdit
from health_data_parser.ingest.symptoms_csv import HEADER, read_symptoms, write_symptoms
from health_data_parser.model.symptom import ImportMode, Symptom
from health_data_parser.utils.translations import _


def symptom(name, start="2021-02", end="", medications="", comment="", severity=2):
    return Symptom([name, start, end, medications, "", comment, str(severity)])


def names(path):
    symptoms, errors = read_symptoms(path)
    assert errors == []
    return [s.name for s in symptoms]


class TestSymptomDialog:
    def test_name_is_required(self, qtbot):
        dialog = SymptomDialog()
        qtbot.addWidget(dialog)

        dialog.accept()

        assert not dialog.result()
        assert dialog.error_label.text() == _("Name is required.")

    def test_end_before_start_is_rejected(self, qtbot):
        dialog = SymptomDialog()
        qtbot.addWidget(dialog)
        dialog.name.setText("Headache")
        dialog.start.set_text("2021-06-15")
        dialog.end.set_text("2021-02")

        dialog.accept()

        assert not dialog.result()
        assert dialog.error_label.text() == _("The end date is before the start date.")

    def test_entries_become_a_symptom(self, qtbot):
        dialog = SymptomDialog()
        qtbot.addWidget(dialog)
        dialog.name.setText(" Headache ")
        dialog.start.set_text("2021-02")
        dialog.medications.setText("Medication A, Medication B")
        dialog.severity.setValue(4)

        dialog.accept()

        assert dialog.result()
        assert dialog.symptom().to_row() == [
            "Headache", "2021-02", "", "Medication A,Medication B", "", "", "4"]

    def test_editing_round_trips_every_field(self, qtbot):
        original = Symptom(["Fatigue", "2020-03-01", "Chronic", "Medication A", "Coffee", "Afternoons", "7"])
        dialog = SymptomDialog(original)
        qtbot.addWidget(dialog)

        assert dialog.end.precision.currentIndex() == SymptomDateEdit.TEXT
        assert dialog.symptom().to_row() == original.to_row()


def test_import_mode_dialog_defaults_to_append(qtbot):
    dialog = ImportModeDialog()
    qtbot.addWidget(dialog)

    assert dialog.mode() is ImportMode.APPEND


@pytest.fixture
def symptom_file(tmp_path):
    path = tmp_path / "symptoms.csv"
    write_symptoms(path, [symptom("Headache", medications="Medication A"),
                          symptom("Fatigue", start="2020-03"),
                          symptom("Rash", start="2019-01", end="2019-02")])
    return path


@pytest.fixture
def manager(qtbot, monkeypatch):
    widget = SymptomManager()
    qtbot.addWidget(widget)
    messages = []
    monkeypatch.setattr(widget, "show_message", lambda title, text, error=False: messages.append((text, error)))
    widget.messages = messages
    return widget


class TestSymptomManager:
    def test_open_hides_resolved_until_asked(self, manager, symptom_file):
        assert manager.open_file(str(symptom_file))

        assert manager.model.rowCount() == 3
        assert manager.proxy.rowCount() == 2
        manager.show_resolved.setChecked(True)
        assert manager.proxy.rowCount() == 3
        assert not manager.dirty

    def test_missing_file_opens_empty(self, manager, tmp_path):
        assert manager.open_file(str(tmp_path / "new.csv"))

        assert manager.model.rowCount() == 0
        assert manager.path == str(tmp_path / "new.csv")

    def test_add_then_save(self, manager, symptom_file, monkeypatch):
        manager.open_file(str(symptom_file))
        monkeypatch.setattr(manager, "ask_symptom", lambda existing=None: symptom("Cough"))

        manager.add_symptom()

        assert manager.dirty
        assert manager.model.symptom_at(manager.selected_row()).name == "Cough"
        assert manager.save()
        assert not manager.dirty
        assert names(symptom_file) == ["Headache", "Fatigue", "Rash", "Cough"]
        assert symptom_file.read_text(encoding="utf-8-sig").splitlines()[0] == ",".join(HEADER)

    def test_cancelled_add_changes_nothing(self, manager, symptom_file, monkeypatch):
        manager.open_file(str(symptom_file))
        monkeypatch.setattr(manager, "ask_symptom", lambda existing=None: None)

        manager.add_symptom()

        assert manager.model.rowCount() == 3
        assert not manager.dirty

    def test_edit_selected(self, manager, symptom_file, monkeypatch):
        manager.open_file(str(symptom_file))
        seen = []

        def edit(existing=None):
            seen.append(existing.name)
            return symptom("Headache", comment="Worse", severity=6)

        monkeypatch.setattr(manager, "ask_symptom", edit)
        manager.select_row(0)

        manager.edit_symptom()

        assert seen == ["Headache"]
        edited = manager.model.symptom_at(0)
        assert (edited.comment, edited.severity) == ("Worse", 6)

    def test_edit_and_delete_need_a_selection(self, manager, symptom_file):
        manager.open_file(str(symptom_file))

        assert not manager.buttons["edit"].isEnabled()
        manager.delete_symptom()
        assert manager.model.rowCount() == 3

        manager.select_row(1)
        assert manager.buttons["delete"].isEnabled()

    def test_delete_and_undo(self, manager, symptom_file):
        manager.open_file(str(symptom_file))
        manager.select_row(0)

        manager.delete_symptom()
        assert [s.name for s in manager.model.symptoms] == ["Fatigue", "Rash"]
        assert manager.buttons["undo"].isEnabled()

        manager.undo_delete()
        assert [s.name for s in manager.model.symptoms] == ["Headache", "Fatigue", "Rash"]
        assert not manager.buttons["undo"].isEnabled()

    def test_search(self, manager, symptom_file, qtbot):
        manager.open_file(str(symptom_file))

        qtbot.keyClicks(manager.search, "medication")

        assert manager.proxy.rowCount() == 1

    @pytest.mark.parametrize("mode, expected, message", [
        (ImportMode.APPEND, ["Headache", "Fatigue", "Rash", "Headache", "Cough"], "Added {0} symptoms."),
        (ImportMode.REPLACE, ["Headache", "Cough"], "Replaced the symptoms with {0} imported symptoms."),
        (ImportMode.MERGE, ["Headache", "Fatigue", "Rash", "Cough"], "Updated {0} symptoms and added {1}."),
    ])
    def test_import(self, manager, symptom_file, tmp_path, monkeypatch, mode, expected, message):
        manager.open_file(str(symptom_file))
        imported = tmp_path / "import.csv"
        write_symptoms(imported, [symptom("Headache", comment="Imported"), symptom("Cough")])
        monkeypatch.setattr(manager, "ask_open_path", lambda title: str(imported))
        monkeypatch.setattr(manager, "ask_import_mode", lambda: mode)

        manager.import_csv()

        assert [s.name for s in manager.model.symptoms] == expected
        assert manager.dirty
        if mode is ImportMode.MERGE:
            assert manager.model.symptom_at(0).comment == "Imported"
            assert manager.messages == [(_(message).format(1, 1), False)]
        else:
            assert manager.messages == [(_(message).format(2), False)]

    def test_import_rejects_unknown_header(self, manager, symptom_file, tmp_path, monkeypatch):
        manager.open_file(str(symptom_file))
        imported = tmp_path / "import.csv"
        imported.write_text("A,B,C\n1,2,3\n", encoding="utf-8")
        monkeypatch.setattr(manager, "ask_open_path", lambda title: str(imported))

        manager.import_csv()

        assert manager.model.rowCount() == 3
        [(text, error)] = manager.messages
        assert error

    def test_import_with_invalid_rows_asks_first(self, manager, symptom_file, tmp_path, monkeypatch):
        manager.open_file(str(symptom_file))
        imported = tmp_path / "import.csv"
        imported.write_text(",".join(HEADER) + "\nCough,2022-01,,,,,not a number\n", encoding="utf-8")
        monkeypatch.setattr(manager, "ask_open_path", lambda title: str(imported))
        monkeypatch.setattr(manager, "ask_yes_no", lambda title, text: False)

        manager.import_csv()

        assert manager.model.rowCount() == 3
        assert not manager.dirty

    def test_export(self, manager, symptom_file, tmp_path, monkeypatch):
        manager.open_file(str(symptom_file))
        exported = tmp_path / "export.csv"
        monkeypatch.setattr(manager, "ask_save_path", lambda title: str(exported))

        manager.export_csv()

        assert names(exported) == ["Headache", "Fatigue", "Rash"]
        assert manager.path == str(symptom_file)

    def test_save_without_a_file_asks_for_one(self, manager, tmp_path, monkeypatch, qtbot):
        path = tmp_path / "chosen.csv"
        monkeypatch.setattr(manager, "ask_save_path", lambda title: str(path))
        monkeypatch.setattr(manager, "ask_symptom", lambda existing=None: symptom("Cough"))
        manager.add_symptom()

        with qtbot.waitSignal(manager.file_changed) as signal:
            assert manager.save()

        assert signal.args == [str(path)]
        assert names(path) == ["Cough"]

    @pytest.mark.parametrize("answer, proceeds, saved", [
        (QMessageBox.StandardButton.Save, True, True),
        (QMessageBox.StandardButton.Discard, True, False),
        (QMessageBox.StandardButton.Cancel, False, False),
    ])
    def test_unsaved_changes_prompt(self, manager, symptom_file, monkeypatch, answer, proceeds, saved):
        manager.open_file(str(symptom_file))
        manager.select_row(0)
        manager.delete_symptom()
        monkeypatch.setattr(manager, "ask_unsaved_changes", lambda: answer)

        assert manager.maybe_save() is proceeds
        assert (names(symptom_file) == ["Fatigue", "Rash"]) is saved

    def test_no_prompt_without_changes(self, manager, symptom_file, monkeypatch):
        manager.open_file(str(symptom_file))
        monkeypatch.setattr(manager, "ask_unsaved_changes", lambda: pytest.fail("prompted"))

        assert manager.maybe_save()
