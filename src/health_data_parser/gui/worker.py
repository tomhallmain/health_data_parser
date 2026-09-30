import traceback

from PySide6.QtCore import QObject, QRunnable, Signal

from health_data_parser.errors import HealthDataParseError, RunCancelled
from health_data_parser.pipeline import DataParser
from health_data_parser.utils.translations import _


class RunSignals(QObject):
    # A pipeline.Stage, as each starts
    stage = Signal(object)
    # The finished DataParser
    succeeded = Signal(object)
    # Message and details (a traceback for unexpected errors, else "")
    failed = Signal(str, str)
    cancelled = Signal()


class RunWorker(QRunnable):
    """Runs the pipeline on a QThreadPool thread; results arrive as signals
    on the thread that created the worker."""

    def __init__(self, options):
        super().__init__()
        # The window keeps a reference, so Qt must not delete it after run()
        self.setAutoDelete(False)
        self.options = options
        self.signals = RunSignals()
        self._cancel_requested = False

    def cancel(self):
        """Stop before the pipeline's next stage."""
        self._cancel_requested = True

    def run(self):
        parser = DataParser(self.options)
        run = parser.create_custom_report if self.options.custom_only else parser.run
        try:
            run(progress=self.signals.stage.emit, is_cancelled=lambda: self._cancel_requested)
        except RunCancelled:
            self.signals.cancelled.emit()
            return
        except HealthDataParseError as e:
            self.signals.failed.emit(str(e), "")
            return
        except Exception as e:
            self.signals.failed.emit(_("Unexpected error: {0}").format(e), traceback.format_exc())
            return
        self.signals.succeeded.emit(parser)
