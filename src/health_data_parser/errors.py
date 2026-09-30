class HealthDataParseError(Exception):
    """A failure that ends a parse/report run.

    Library code raises this so each caller decides how to stop: the CLI
    entry points log the message and exit with status 1, and the GUI shows
    it in an error dialog and stays open.
    """


class RunCancelled(Exception):
    """A run stopped between stages because its caller asked it to."""
