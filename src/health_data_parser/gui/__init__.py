"""The PySide6 desktop app."""
import os

# matplotlib's Qt backend uses an already-imported Qt binding, or QT_API; pin
# it to PySide6 so another installed binding (PyQt6, ...) is never mixed in
os.environ.setdefault("QT_API", "pyside6")
