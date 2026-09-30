import os

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QThreadPool, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QDockWidget, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSplitter,
    QTableView, QTabWidget, QVBoxLayout, QWidget)

from health_data_parser.analysis.summary import (
    OBSERVATIONS_JSON_FILENAME, lab_result_rows, load_observations_json, summary_lines,
    vital_sign_rows)
from health_data_parser.gui.charts import overview_figure, trends_figure
from health_data_parser.gui.log_forwarder import LogForwarder
from health_data_parser.gui.models import SortFilterProxy, lab_results_model, vitals_model
from health_data_parser.gui.run_panel import RunOptionsPanel
from health_data_parser.gui.settings import app_settings, remember_export_dir
from health_data_parser.gui.symptoms import SymptomManager
from health_data_parser.gui.worker import RunWorker
from health_data_parser.ingest.symptoms_csv import write_symptoms
from health_data_parser.pipeline import Stage
from health_data_parser.utils.logger import setup_logger
from health_data_parser.utils.paths import default_user_data_dir
from health_data_parser.utils.translations import _

logger = setup_logger('main_window')

_STAGES = list(Stage)


def stage_label(stage):
    return {
        Stage.CUSTOM_DATA: _("Reading custom data files..."),
        Stage.EXPORT_XML: _("Parsing export.xml..."),
        Stage.CLINICAL_RECORDS: _("Reading clinical records..."),
        Stage.ANALYSIS: _("Analyzing results..."),
        Stage.WEARABLE_CHARTS: _("Charting wearable data..."),
        Stage.OUTPUTS: _("Writing output files and PDF..."),
    }[stage]


def _table(model):
    """A sortable table view over `model`; returns (view, proxy)."""
    proxy = SortFilterProxy(model)
    proxy.setSourceModel(model)
    view = QTableView()
    view.setModel(proxy)
    view.setSortingEnabled(True)
    view.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    view.horizontalHeader().setStretchLastSection(True)
    return view, proxy


class MainWindow(QMainWindow):
    """Run options on the left, results tabs on the right, the log below."""

    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle(_("Apple Health Data Parser"))
        self.resize(1400, 900)
        self.settings = settings if settings is not None else app_settings()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._worker = None
        self.output_dir = None
        self.pdf_path = None

        # Run options and controls
        self.panel = RunOptionsPanel()
        self.panel.restore_settings(self.settings)
        panel_scroll = QScrollArea()
        panel_scroll.setWidget(self.panel)
        panel_scroll.setWidgetResizable(True)

        self.run_button = QPushButton(_("Generate Report"))
        self.cancel_button = QPushButton(_("Cancel"))
        self.load_button = QPushButton(_("Load Results..."))
        self.run_button.clicked.connect(self.start_run)
        self.cancel_button.clicked.connect(self.cancel_run)
        self.load_button.clicked.connect(self.load_results_dialog)
        self.progress = QProgressBar()
        self.progress.setRange(0, len(_STAGES))
        self.progress.setValue(0)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.load_button)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(panel_scroll, 1)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.progress)
        left_layout.addWidget(self.status_label)

        # Results
        self.tabs = QTabWidget()
        self.tabs.addTab(self._summary_tab(), _("Summary"))
        self.lab_model = lab_results_model(self)
        self.lab_view, self.lab_proxy = _table(self.lab_model)
        self.tabs.addTab(self._lab_tab(), _("Lab Results"))
        self.vitals_model = vitals_model(self)
        self.vitals_view, self.vitals_proxy = _table(self.vitals_model)
        self.tabs.addTab(self.vitals_view, _("Vitals"))
        self.trends_tab = QWidget()
        QVBoxLayout(self.trends_tab)
        self.tabs.addTab(self.trends_tab, _("Trends"))
        self.symptoms = SymptomManager()
        self.symptoms_tab_index = self.tabs.addTab(self.symptoms, _("Symptoms"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        # Log
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        log_dock = QDockWidget(_("Log"), self)
        log_dock.setObjectName("log_dock")
        log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        self.log_forwarder = LogForwarder(self)
        self.log_forwarder.message.connect(self.log_view.appendPlainText)
        self.log_forwarder.attach()

        self.panel.changed.connect(self._update_controls)
        self.panel.manage_symptoms_requested.connect(self.manage_symptoms)
        self.symptoms.file_changed.connect(self._symptom_file_changed)
        self._update_controls()
        self._set_results_dir(None)

    def _summary_tab(self):
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(160)
        self.open_pdf_button = QPushButton(_("Open PDF"))
        self.open_folder_button = QPushButton(_("Open Output Folder"))
        self.open_pdf_button.clicked.connect(self.open_pdf)
        self.open_folder_button.clicked.connect(self.open_output_folder)
        self.overview_area = QWidget()
        QVBoxLayout(self.overview_area)

        buttons = QHBoxLayout()
        buttons.addWidget(self.open_pdf_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addStretch(1)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self.summary_text)
        layout.addLayout(buttons)
        layout.addWidget(self.overview_area, 1)
        return tab

    def _lab_tab(self):
        self.lab_search = QLineEdit()
        self.lab_search.setPlaceholderText(_("Filter lab results"))
        self.lab_search.setClearButtonEnabled(True)
        self.lab_search.textChanged.connect(self.lab_proxy.setFilterFixedString)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self.lab_search)
        layout.addWidget(self.lab_view, 1)
        return tab

    # --- Questions and messages; tests replace these --------------------------

    def show_error(self, title, message, details=""):
        box = QMessageBox(QMessageBox.Icon.Critical, title, message, parent=self)
        if details:
            box.setDetailedText(details)
        box.exec()

    def ask_results_dir(self):
        return QFileDialog.getExistingDirectory(self, _("Load Results"), self.output_dir or "")

    # --- Running --------------------------------------------------------------

    @property
    def is_running(self):
        return self._worker is not None

    def _update_controls(self):
        valid = self.panel.validate() is not None
        self.run_button.setEnabled(valid and not self.is_running)
        self.cancel_button.setEnabled(self.is_running)
        self.load_button.setEnabled(not self.is_running)
        self.panel.setEnabled(not self.is_running)

    def start_run(self):
        if self.is_running:
            return
        options = self.panel.validate()
        if options is None:
            return
        remember_export_dir(self.settings, options.data_export_dir)
        self.panel.export_dir.set_history(
            [options.data_export_dir] + [d for d in self.panel.export_dir.history()
                                         if d != options.data_export_dir])
        self.panel.save_settings(self.settings)

        worker = RunWorker(options)
        worker.signals.stage.connect(self._on_stage)
        worker.signals.succeeded.connect(self._on_succeeded)
        worker.signals.failed.connect(self._on_failed)
        worker.signals.cancelled.connect(self._on_cancelled)
        self._worker = worker
        self.progress.setValue(0)
        self.status_label.setStyleSheet("")
        self.status_label.setText(_("Starting..."))
        self._update_controls()
        self.pool.start(worker)

    def cancel_run(self):
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText(_("Cancelling after the current step..."))

    def _finish_run(self):
        self._worker = None
        self._update_controls()

    def _on_stage(self, stage):
        self.progress.setValue(_STAGES.index(stage))
        self.status_label.setText(stage_label(stage))

    def _on_succeeded(self, parser):
        self._finish_run()
        self.progress.setValue(len(_STAGES))
        self.status_label.setText(_("Report generated."))
        self.pdf_path = parser.pdf_path
        self.show_results(parser.output_dir)

    def _on_failed(self, message, details):
        self._finish_run()
        self.progress.setValue(0)
        self.status_label.setStyleSheet("color: red")
        self.status_label.setText(message)
        if details:
            logger.error(details)
        self.show_error(_("Report Failed"), message, details)

    def _on_cancelled(self):
        self._finish_run()
        self.progress.setValue(0)
        self.status_label.setText(_("Cancelled."))

    # --- Results --------------------------------------------------------------

    def load_results_dialog(self):
        directory = self.ask_results_dir()
        if directory:
            self.pdf_path = None
            self.show_results(directory)

    def show_results(self, directory):
        """Fill the results tabs from the observations.json in `directory`."""
        try:
            json_data = load_observations_json(directory)
        except Exception as e:
            self.show_error(_("Error"), _("Failed to load results: {0}").format(e))
            return
        self._set_results_dir(directory)
        if not json_data:
            self.summary_text.setPlainText(
                _("No {0} found in {1}.").format(OBSERVATIONS_JSON_FILENAME, directory))
        else:
            self.summary_text.setPlainText("\n".join(summary_lines(json_data)))
        self.lab_model.set_rows(lab_result_rows(json_data))
        self.vitals_model.set_rows(vital_sign_rows(json_data))
        self._set_figure(self.overview_area, overview_figure(json_data))
        self._set_figure(self.trends_tab, trends_figure(json_data))
        self.tabs.setCurrentIndex(0)

    def _set_results_dir(self, directory):
        self.output_dir = directory
        self.open_folder_button.setEnabled(directory is not None)
        self.open_pdf_button.setEnabled(self.pdf_path is not None and os.path.exists(self.pdf_path))

    @staticmethod
    def _set_figure(container, figure):
        layout = container.layout()
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        layout.addWidget(FigureCanvasQTAgg(figure))

    def open_pdf(self):
        if self.pdf_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.pdf_path))

    def open_output_folder(self):
        if self.output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir))

    # --- Symptoms -------------------------------------------------------------

    def manage_symptoms(self):
        """Show the run's symptom file in the Symptoms tab, starting a new one
        in the user data folder if none is set."""
        path = self.panel.symptom_csv.path()
        if not path:
            directory = default_user_data_dir()
            path = str(directory / "symptom_set.csv")
            if not os.path.exists(path):
                try:
                    os.makedirs(directory, exist_ok=True)
                    write_symptoms(path, [])
                except OSError as e:
                    self.show_error(_("Error"), _("Failed to create symptom file: {0}").format(e))
                    return
            self.panel.symptom_csv.set_path(path)
        if path != self.symptoms.path:
            if not self.symptoms.maybe_save() or not self.symptoms.open_file(path):
                return
        self.tabs.setCurrentIndex(self.symptoms_tab_index)

    def _symptom_file_changed(self, path):
        if path:
            self.panel.symptom_csv.set_path(path)

    # --- Closing --------------------------------------------------------------

    def closeEvent(self, event):
        if not self.symptoms.maybe_save():
            event.ignore()
            return
        if self._worker is not None:
            self._worker.cancel()
        # A run stops at its next stage; it can't be interrupted mid-stage
        self.pool.waitForDone()
        self.panel.save_settings(self.settings)
        self.settings.sync()
        self.log_forwarder.detach()
        super().closeEvent(event)
