import pytest

from health_data_parser.ingest.symptoms_csv import (
    HEADER, TEMPLATE_HEADER, InvalidSymptomFile, read_symptoms, write_symptoms)

ROWS = (
    'Headache,2021-02,2021-06-15,"Medication A, medication b",Coffee,Mornings,2\n'
    "Fatigue,2020-03-01,Chronic,,,,1\n"
)


def write(tmp_path, header, rows=ROWS, name="symptoms.csv"):
    path = tmp_path / name
    path.write_text(",".join(header) + "\n" + rows, encoding="utf-8")
    return path


class TestReadSymptoms:
    @pytest.mark.parametrize("header", [HEADER, TEMPLATE_HEADER])
    def test_both_headers(self, tmp_path, header):
        symptoms, errors = read_symptoms(write(tmp_path, header), require_known_header=True)
        assert [s.name for s in symptoms] == ["Headache", "Fatigue"]
        assert errors == []

    def test_unknown_header_is_rejected_when_required(self, tmp_path):
        path = write(tmp_path, ["What", "When", "Until", "Meds", "Causes", "Notes", "How bad"])
        with pytest.raises(InvalidSymptomFile, match="Expected columns"):
            read_symptoms(path, require_known_header=True)
        # Without the requirement the header row is just skipped
        assert len(read_symptoms(path)[0]) == 2

    def test_invalid_rows_are_reported_by_row_number(self, tmp_path):
        path = write(tmp_path, HEADER, ROWS + "Bad row,2021-01,,,,,not-a-number\n")
        symptoms, errors = read_symptoms(path)
        assert len(symptoms) == 2
        assert [row for row, _ in errors] == [4]

    def test_values_as_entered(self, tmp_path):
        headache, fatigue = read_symptoms(write(tmp_path, HEADER))[0]
        assert (headache.start_text, headache.end_text) == ("2021-02", "2021-06-15")
        assert headache.medications == ["Medication A", "medication b"]
        assert fatigue.end_text == "Chronic"
        assert fatigue.end_date is None
        assert not fatigue.is_resolved

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        assert read_symptoms(path) == ([], [])


class TestWriteSymptoms:
    def test_round_trip_keeps_entered_values(self, tmp_path):
        symptoms, _ = read_symptoms(write(tmp_path, TEMPLATE_HEADER))
        out = tmp_path / "out.csv"
        write_symptoms(out, symptoms)

        assert out.read_text(encoding="utf-8-sig").splitlines() == [
            ",".join(HEADER),
            'Headache,2021-02,2021-06-15,"Medication A,medication b",Coffee,Mornings,2',
            "Fatigue,2020-03-01,Chronic,,,,1",
        ]

    def test_written_as_utf8_with_byte_order_mark(self, tmp_path):
        symptoms, _ = read_symptoms(write(tmp_path, HEADER, "Céphalée,2021-02,,,,,1\n"))
        out = tmp_path / "out.csv"
        write_symptoms(out, symptoms)
        assert out.read_bytes().startswith(b"\xef\xbb\xbf")
        assert read_symptoms(out)[0][0].name == "Céphalée"
