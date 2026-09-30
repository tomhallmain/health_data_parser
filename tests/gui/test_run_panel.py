import pytest

from health_data_parser.gui.run_panel import RunOptionsPanel
from health_data_parser.model.units import HeightUnit, TemperatureUnit, WeightUnit
from health_data_parser.options import ParseOptions
from health_data_parser.utils.translations import _


@pytest.fixture
def panel(qtbot):
    widget = RunOptionsPanel()
    qtbot.addWidget(widget)
    return widget


def test_missing_export_dir_blocks_the_run(panel):
    assert panel.validate() is None
    assert not panel.error_label.isHidden()
    assert panel.error_label.text() == _("Missing Apple Health data export directory path.")


def test_export_without_clinical_records_is_rejected(panel, tmp_path):
    panel.export_dir.set_path(str(tmp_path))

    assert panel.validate() is None
    assert "clinical-records" in panel.error_label.text()


def test_defaults_match_parse_options(panel, export_dir):
    panel.export_dir.set_path(str(export_dir))

    options = panel.validate()

    assert options == ParseOptions(str(export_dir))
    assert panel.error_label.isHidden()


def test_inputs_become_options(panel, export_dir, tmp_path):
    panel.export_dir.set_path(str(export_dir))
    panel.output_dir.set_path(str(tmp_path / "out"))
    panel.symptom_csv.set_path(str(tmp_path / "symptoms.csv"))
    panel.start_year.setValue(2020)
    panel.skip_dates.set_dates(["2021-01-02"])
    panel.boundary.setValue(-0.1)
    panel.flags["skip_long_values"].setChecked(True)
    panel.flags["report_highlight_abnormal_results"].setChecked(False)
    panel.birth_date.set_iso_date("1980-02-29")
    panel._set_unit("normal_height_unit", "IN")
    panel._set_unit("normal_weight_unit", "KG")
    panel._set_unit("normal_temperature_unit", "F")

    options = panel.options()

    assert options.output_dir == str(tmp_path / "out")
    assert options.symptom_data_csv == str(tmp_path / "symptoms.csv")
    assert options.food_data_csv is None
    assert options.start_year == 2020
    assert options.skip_dates == ("2021-01-02",)
    assert options.in_range_abnormal_boundary == -0.1
    assert options.skip_long_values is True
    assert options.report_highlight_abnormal_results is False
    assert options.birth_date == "1980-02-29"
    assert options.subject["birthDate"] == "1980-02-29"
    assert (options.normal_height_unit, options.normal_weight_unit, options.normal_temperature_unit) == (
        HeightUnit.IN, WeightUnit.KG, TemperatureUnit.F)


def test_changed_fires_on_edits(panel, qtbot):
    with qtbot.waitSignal(panel.changed):
        panel.flags["verbose"].setChecked(True)
    with qtbot.waitSignal(panel.changed):
        panel.start_year.setValue(2001)


def test_settings_round_trip(panel, export_dir, settings, qtbot):
    panel.export_dir.set_path(str(export_dir))
    panel.start_year.setValue(2019)
    panel.skip_dates.set_dates(["2021-01-02"])
    panel.boundary.setValue(0.2)
    panel.flags["json_add_all_vitals"].setChecked(True)
    panel.birth_date.set_iso_date("1975-06-01")
    panel._set_unit("normal_weight_unit", "G")
    panel.save_settings(settings)
    settings.sync()

    restored = RunOptionsPanel()
    qtbot.addWidget(restored)
    restored.restore_settings(settings)

    assert restored.options() == panel.options()


def test_no_start_year_survives_settings(panel, export_dir, settings, qtbot):
    panel.export_dir.set_path(str(export_dir))
    panel.save_settings(settings)

    restored = RunOptionsPanel()
    qtbot.addWidget(restored)
    restored.restore_settings(settings)

    assert restored.options().start_year is None
    assert restored.options().birth_date is None


def test_every_unit_is_offered(panel):
    for name, unit_type in [("normal_height_unit", HeightUnit), ("normal_weight_unit", WeightUnit),
                            ("normal_temperature_unit", TemperatureUnit)]:
        combo = panel.units[name]
        assert [combo.itemData(i) for i in range(combo.count())] == [unit.name for unit in unit_type]


def test_birth_date_edits_fire_changed(panel, qtbot):
    with qtbot.waitSignal(panel.changed):
        panel.birth_date.enabled.setChecked(True)
