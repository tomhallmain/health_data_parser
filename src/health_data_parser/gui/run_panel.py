import dataclasses

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget)

from health_data_parser.errors import HealthDataParseError
from health_data_parser.gui.settings import recent_export_dirs, string_list
from health_data_parser.gui.widgets import OptionalDateEdit, PathField, SkipDatesEditor, csv_file_filter
from health_data_parser.model.units import HeightUnit, TemperatureUnit, WeightUnit
from health_data_parser.options import ParseOptions
from health_data_parser.utils.translations import _

_DEFAULTS = {f.name: f.default for f in dataclasses.fields(ParseOptions)
             if f.default is not dataclasses.MISSING}

# The start year box's minimum stands for "no start year"
_NO_START_YEAR = 1899
_MAX_YEAR = 2100

def _flag_labels():
    """(option name, check box label) for the boolean options."""
    return [
        ("skip_long_values", _("Skip long values")),
        ("json_add_all_vitals", _("Add all vital sign readings to the JSON")),
        ("skip_in_range_abnormal_results", _("Skip abnormal results that are in range")),
        ("report_highlight_abnormal_results", _("Highlight abnormal results in the report")),
        ("only_clinical_records", _("Only clinical records (skip export.xml)")),
        ("custom_only", _("Report on the custom data files only")),
        ("verbose", _("Verbose logging")),
    ]


def _unit_labels():
    """(option name, form label, [(unit, label)]) for the unit options."""
    return [
        ("normal_height_unit", _("Height unit:"), [
            (HeightUnit.CM, _("Centimeters (cm)")), (HeightUnit.M, _("Meters (m)")),
            (HeightUnit.FT, _("Feet (ft)")), (HeightUnit.IN, _("Inches (in)"))]),
        ("normal_weight_unit", _("Weight unit:"), [
            (WeightUnit.G, _("Grams (g)")), (WeightUnit.KG, _("Kilograms (kg)")),
            (WeightUnit.LB, _("Pounds (lb)"))]),
        ("normal_temperature_unit", _("Temperature unit:"), [
            (TemperatureUnit.C, _("Celsius (°C)")), (TemperatureUnit.F, _("Fahrenheit (°F)"))]),
    ]


class RunOptionsPanel(QWidget):
    """Inputs for a run. `changed` fires on every edit; validate() builds the
    ParseOptions and shows why it can't, if it can't."""
    changed = Signal()
    manage_symptoms_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.export_dir = PathField(PathField.DIRECTORY, _("Apple Health Export Directory"), history=True)
        self.output_dir = PathField(PathField.DIRECTORY, _("Output Directory"))
        self.output_dir.set_placeholder(_("The export directory"))
        self.symptom_csv = PathField(PathField.FILE, _("Symptom Data"), csv_file_filter())
        self.food_csv = PathField(PathField.FILE, _("Food Data"), csv_file_filter())
        self.extra_observations_csv = PathField(PathField.FILE, _("Extra Observations"), csv_file_filter())
        self.manage_symptoms_button = QPushButton(_("Manage..."))
        self.manage_symptoms_button.clicked.connect(self.manage_symptoms_requested)

        self.start_year = QSpinBox()
        self.start_year.setRange(_NO_START_YEAR, _MAX_YEAR)
        self.start_year.setSpecialValueText(_("Any"))
        self.skip_dates = SkipDatesEditor()
        self.boundary = QDoubleSpinBox()
        self.boundary.setRange(-0.49, 0.49)
        self.boundary.setDecimals(2)
        self.boundary.setSingleStep(0.01)
        self.flags = {name: QCheckBox(label) for name, label in _flag_labels()}
        self.birth_date = OptionalDateEdit(_("Set"))
        self.birth_date.setToolTip(_("Subject birth date for the report, if not found in export.xml"))
        # Option name -> combo box whose items hold the unit enum's member name
        self.units = {}
        unit_rows = []
        for name, label, choices in _unit_labels():
            combo = QComboBox()
            for unit, unit_label in choices:
                combo.addItem(unit_label, unit.name)
            self.units[name] = combo
            unit_rows.append((label, combo))

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: red")
        self.error_label.hide()

        files = QGroupBox(_("Input Files"))
        files_form = QFormLayout(files)
        files_form.addRow(_("Apple Health export:"), self.export_dir)
        files_form.addRow(_("Output directory:"), self.output_dir)
        symptom_row = QHBoxLayout()
        symptom_row.addWidget(self.symptom_csv, 1)
        symptom_row.addWidget(self.manage_symptoms_button)
        files_form.addRow(_("Symptom data:"), symptom_row)
        files_form.addRow(_("Food data:"), self.food_csv)
        files_form.addRow(_("Extra observations:"), self.extra_observations_csv)

        options = QGroupBox(_("Options"))
        options_form = QFormLayout(options)
        options_form.addRow(_("Start year:"), self.start_year)
        options_form.addRow(_("Skip dates:"), self.skip_dates)
        options_form.addRow(_("In-range abnormal boundary:"), self.boundary)
        options_form.addRow(_("Birth date:"), self.birth_date)
        for label, combo in unit_rows:
            options_form.addRow(label, combo)
        for check_box in self.flags.values():
            options_form.addRow(check_box)

        layout = QVBoxLayout(self)
        layout.addWidget(files)
        layout.addWidget(options)
        layout.addWidget(self.error_label)
        layout.addStretch(1)

        self.reset_to_defaults()

        for field in (self.export_dir, self.output_dir, self.symptom_csv, self.food_csv,
                      self.extra_observations_csv, self.skip_dates, self.birth_date):
            field.changed.connect(self.changed)
        self.start_year.valueChanged.connect(self.changed)
        self.boundary.valueChanged.connect(self.changed)
        for check_box in self.flags.values():
            check_box.toggled.connect(self.changed)
        for combo in self.units.values():
            combo.currentIndexChanged.connect(self.changed)

    def reset_to_defaults(self):
        self._set_start_year(_DEFAULTS["start_year"])
        self.skip_dates.set_dates(_DEFAULTS["skip_dates"])
        self.boundary.setValue(_DEFAULTS["in_range_abnormal_boundary"])
        for name, check_box in self.flags.items():
            check_box.setChecked(_DEFAULTS[name])
        self.birth_date.set_iso_date(_DEFAULTS["birth_date"])
        for name in self.units:
            self._set_unit(name, _DEFAULTS[name].name)

    def _set_unit(self, name, unit_name):
        """Select the unit named `unit_name`; an unknown name leaves the
        selection as it is."""
        combo = self.units[name]
        index = combo.findData(unit_name)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _unit(self, name):
        unit_type = type(_DEFAULTS[name])
        return unit_type[self.units[name].currentData()]

    def _set_start_year(self, year):
        self.start_year.setValue(_NO_START_YEAR if year is None else year)

    def _start_year(self):
        value = self.start_year.value()
        return None if value == _NO_START_YEAR else value

    def options(self):
        """The ParseOptions for the current inputs; raises HealthDataParseError."""
        return ParseOptions(
            data_export_dir=self.export_dir.path(),
            output_dir=self.output_dir.path() or None,
            start_year=self._start_year(),
            skip_dates=self.skip_dates.dates(),
            in_range_abnormal_boundary=round(self.boundary.value(), 2),
            symptom_data_csv=self.symptom_csv.path() or None,
            food_data_csv=self.food_csv.path() or None,
            extra_observations_csv=self.extra_observations_csv.path() or None,
            birth_date=self.birth_date.iso_date(),
            **{name: self._unit(name) for name in self.units},
            **{name: check_box.isChecked() for name, check_box in self.flags.items()},
        )

    def validate(self):
        """The ParseOptions, or None with the reason shown under the inputs."""
        try:
            options = self.options()
        except HealthDataParseError as e:
            self.error_label.setText(str(e))
            self.error_label.show()
            return None
        self.error_label.clear()
        self.error_label.hide()
        return options

    def save_settings(self, settings):
        settings.beginGroup("options")
        settings.setValue("export_dir", self.export_dir.path())
        settings.setValue("output_dir", self.output_dir.path())
        settings.setValue("symptom_data_csv", self.symptom_csv.path())
        settings.setValue("food_data_csv", self.food_csv.path())
        settings.setValue("extra_observations_csv", self.extra_observations_csv.path())
        settings.setValue("start_year", self.start_year.value())
        settings.setValue("skip_dates", list(self.skip_dates.dates()))
        settings.setValue("in_range_abnormal_boundary", self.boundary.value())
        for name, check_box in self.flags.items():
            settings.setValue(name, check_box.isChecked())
        settings.setValue("birth_date", self.birth_date.iso_date() or "")
        for name, combo in self.units.items():
            settings.setValue(name, combo.currentData())
        settings.endGroup()

    def restore_settings(self, settings):
        self.export_dir.set_history(recent_export_dirs(settings))
        settings.beginGroup("options")
        try:
            self.export_dir.set_path(settings.value("export_dir", "", type=str))
            self.output_dir.set_path(settings.value("output_dir", "", type=str))
            self.symptom_csv.set_path(settings.value("symptom_data_csv", "", type=str))
            self.food_csv.set_path(settings.value("food_data_csv", "", type=str))
            self.extra_observations_csv.set_path(settings.value("extra_observations_csv", "", type=str))
            if settings.contains("start_year"):
                self.start_year.setValue(settings.value("start_year", _NO_START_YEAR, type=int))
            if settings.contains("skip_dates"):
                self.skip_dates.set_dates(string_list(settings, "skip_dates"))
            if settings.contains("in_range_abnormal_boundary"):
                self.boundary.setValue(settings.value("in_range_abnormal_boundary", 0.0, type=float))
            for name, check_box in self.flags.items():
                if settings.contains(name):
                    check_box.setChecked(settings.value(name, False, type=bool))
            if settings.contains("birth_date"):
                self.birth_date.set_iso_date(settings.value("birth_date", "", type=str))
            for name in self.units:
                if settings.contains(name):
                    self._set_unit(name, settings.value(name, "", type=str))
        finally:
            settings.endGroup()
