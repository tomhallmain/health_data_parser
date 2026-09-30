import logging

from PySide6.QtCore import QObject, Signal


class LogForwarder(QObject):
    """Forwards the app's log records to a Qt signal while attached.

    Records can come from any thread; the signal is delivered on the thread
    this object lives on (the GUI thread).
    """
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handler = _SignalHandler(self)

    def attach(self):
        # Every app logger propagates to the root logger
        logging.getLogger().addHandler(self._handler)

    def detach(self):
        logging.getLogger().removeHandler(self._handler)


class _SignalHandler(logging.Handler):
    def __init__(self, forwarder):
        super().__init__(logging.INFO)
        self._forwarder = forwarder
        self.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def emit(self, record):
        try:
            self._forwarder.message.emit(self.format(record))
        except Exception:
            self.handleError(record)
