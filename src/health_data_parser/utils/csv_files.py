import csv
import locale


def read_csv_rows(path):
    """All rows of a CSV file, header included.

    Tries UTF-8 (with or without a byte order mark) first, then the platform
    encoding, which is what earlier versions of this app wrote and what
    spreadsheet programs often save.
    """
    for encoding in ("utf-8-sig", locale.getpreferredencoding(False)):
        try:
            with open(path, newline="", encoding=encoding) as f:
                return list(csv.reader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path} is neither UTF-8 nor in the platform encoding")
