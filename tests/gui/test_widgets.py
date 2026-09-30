import pytest

from health_data_parser.gui.widgets import OptionalDateEdit, PathField, SkipDatesEditor, SymptomDateEdit


@pytest.fixture
def date_edit(qtbot):
    widget = SymptomDateEdit()
    qtbot.addWidget(widget)
    return widget


class TestSymptomDateEdit:
    @pytest.mark.parametrize("text, precision", [
        ("", SymptomDateEdit.NOT_SET),
        ("2021-02", SymptomDateEdit.MONTH),
        ("2021-06-15", SymptomDateEdit.DAY),
        ("Chronic", SymptomDateEdit.TEXT),
        # Not a real date: kept as text rather than lost
        ("2021-13-40", SymptomDateEdit.TEXT),
    ])
    def test_round_trip(self, date_edit, text, precision):
        date_edit.set_text(text)

        assert date_edit.precision.currentIndex() == precision
        assert date_edit.text() == text

    def test_changing_precision_keeps_the_date(self, date_edit):
        date_edit.set_text("2021-06-15")

        date_edit.precision.setCurrentIndex(SymptomDateEdit.MONTH)
        assert date_edit.text() == "2021-06"

        date_edit.precision.setCurrentIndex(SymptomDateEdit.NOT_SET)
        assert date_edit.text() == ""

    def test_only_the_relevant_input_is_shown(self, date_edit):
        date_edit.set_text("Chronic")
        assert date_edit.date_edit.isHidden() and not date_edit.text_edit.isHidden()

        date_edit.set_text("2021-02")
        assert not date_edit.date_edit.isHidden() and date_edit.text_edit.isHidden()


class TestSkipDatesEditor:
    def test_dates_are_sorted_and_distinct(self, qtbot):
        editor = SkipDatesEditor()
        qtbot.addWidget(editor)

        with qtbot.waitSignal(editor.changed):
            editor.add_date("2023-05-01")
        editor.add_date("2021-01-02")
        editor.add_date("2023-05-01")

        assert editor.dates() == ("2021-01-02", "2023-05-01")

    def test_remove_selected(self, qtbot):
        editor = SkipDatesEditor()
        qtbot.addWidget(editor)
        editor.set_dates(["2021-01-02", "2023-05-01"])

        editor.list.item(0).setSelected(True)
        editor.remove_selected()

        assert editor.dates() == ("2023-05-01",)


class TestPathField:
    def test_path_is_trimmed(self, qtbot):
        field = PathField(PathField.FILE, "File")
        qtbot.addWidget(field)

        with qtbot.waitSignal(field.changed):
            field.set_path("  /data/file.csv ")

        assert field.path() == "/data/file.csv"

    def test_history_keeps_the_current_path(self, qtbot):
        field = PathField(PathField.DIRECTORY, "Directory", history=True)
        qtbot.addWidget(field)
        field.set_path("/current")

        field.set_history(["/recent1", "/recent2"])

        assert field.history() == ["/recent1", "/recent2"]
        assert field.path() == "/current"


class TestOptionalDateEdit:
    def test_unset_by_default(self, qtbot):
        edit = OptionalDateEdit("Set")
        qtbot.addWidget(edit)

        assert edit.iso_date() is None
        assert not edit.date_edit.isEnabled()

    def test_round_trip(self, qtbot):
        edit = OptionalDateEdit("Set")
        qtbot.addWidget(edit)

        edit.set_iso_date("1980-02-29")
        assert edit.iso_date() == "1980-02-29"
        assert edit.date_edit.isEnabled()

        edit.set_iso_date(None)
        assert edit.iso_date() is None
