"""The CLI entry points, run as subprocesses: their option handling lives in
`if __name__ == "__main__"` blocks. Subprocesses inherit the environment
conftest.py isolates, so they also write logs under the test home."""
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

OBSERVATIONS_CSV = (
    "Subject,Performer,Collection Date,Report Description,LOINC Code,Code Description,Value,Range,Units\n"
    '"Doe, Jane",Organization/ExampleLab,2022-11-20,Iron Panel,2276-4,Ferritin,20,30-400,ng/mL\n'
)


def run_script(script, *args):
    return subprocess.run([sys.executable, str(REPO_ROOT / script), *map(str, args)],
                          cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)


class TestParseDataCli:
    def test_no_arguments_prints_help(self):
        result = run_script("parse_data.py")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_invalid_export_dir(self, tmp_path):
        result = run_script("parse_data.py", tmp_path / "missing")
        assert result.returncode == 1
        assert "is invalid" in result.stderr
        assert "Usage:" in result.stdout

    def test_export_without_clinical_records(self, tmp_path):
        result = run_script("parse_data.py", tmp_path)
        assert result.returncode == 1
        assert "clinical-records" in result.stderr

    def test_unknown_option(self, export_dir):
        result = run_script("parse_data.py", export_dir, "--no_such_option")
        assert result.returncode == 2
        assert "Usage:" in result.stdout

    @pytest.mark.parametrize("option, message", [
        ("--start_year=abc", "is not a valid year"),
        ("--skip_dates=2023-13-45", "is not a valid list of dates"),
        ("--in_range_abnormal_boundary=0.6", "is not a valid decimal-formatted percentage"),
        ("--birth_date=yesterday", "is not a valid list of date"),
    ])
    def test_invalid_option_values(self, export_dir, option, message):
        result = run_script("parse_data.py", export_dir, option)
        assert result.returncode == 1
        assert message in result.stderr

    def test_run_failure_exits_with_message(self, export_dir, tmp_path):
        result = run_script("parse_data.py", export_dir, f"--food_data={tmp_path / 'missing.csv'}")
        assert result.returncode == 1
        assert "Failed to assemble or analyze food data provided." in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.xfail(reason="Known bug: the help check tests `\"-h\" in opts`, but opts holds "
                              "(option, value) tuples, so -h reaches `assert False`")
    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_flag(self, export_dir, flag):
        result = run_script("parse_data.py", export_dir, flag)
        assert result.returncode == 0
        assert "Usage:" in result.stdout


class TestGenerateDiagnosticReportFilesCli:
    def test_no_arguments_prints_help(self):
        result = run_script("generate_diagnostic_report_files.py")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_writes_reports_next_to_csv(self, tmp_path):
        csv_path = tmp_path / "observations_data.csv"
        csv_path.write_text(OBSERVATIONS_CSV, encoding="utf-8")

        result = run_script("generate_diagnostic_report_files.py", csv_path)

        assert result.returncode == 0, result.stderr
        assert len(list(tmp_path.glob("DiagnosticReport-*-CUSTOM.json"))) == 1

    def test_invalid_csv(self, tmp_path):
        result = run_script("generate_diagnostic_report_files.py", tmp_path / "missing.csv")
        assert result.returncode == 1
        assert "is invalid" in result.stderr
        assert "Usage:" in result.stdout
