import sys

from PySide6.QtWidgets import QApplication

from health_data_parser.gui.main_window import MainWindow


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    # Name the per-user settings location
    app.setOrganizationName("HealthDataParser")
    app.setApplicationName("Health Data Parser")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
