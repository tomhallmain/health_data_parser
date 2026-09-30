"""The CLI entry points, run as subprocesses: their option handling lives in
main() functions that end the process with sys.exit. Subprocesses inherit the
environment conftest.py isolates, so they also write logs under the test home."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from health_data_parser.cli.diagnostic_reports import help_text as reports_help_text
from health_data_parser.utils.translations import _

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSE = "health_data_parser.cli.parse"
REPORTS = "health_data_parser.cli.diagnostic_reports"

OBSERVATIONS_CSV = (
    "Subject,Performer,Collection Date,Report Description,LOINC Code,Code Description,Value,Range,Units\n"
    '"Doe, Jane",Organization/ExampleLab,2022-11-20,Iron Panel,2276-4,Ferritin,20,30-400,ng/mL\n'
)


def _run(command, *args):
    # src/ on PYTHONPATH so the package imports without an install
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
    return subprocess.run([sys.executable, *command, *map(str, args)], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def invalid_export_message(path):
    return _("Apple Health data export directory path \"{0}\" is invalid.").format(path)


def run_cli(module, *args):
    return _run(["-m", module], *args)


def run_root_script(script, *args):
    return _run([str(REPO_ROOT / script)], *args)


class TestParseDataCli:
    def test_no_arguments_prints_help(self):
        result = run_cli(PARSE)
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "--output_dir" in result.stdout

    def test_invalid_export_dir(self, tmp_path):
        result = run_cli(PARSE, tmp_path / "missing")
        assert result.returncode == 1
        assert invalid_export_message(tmp_path / "missing") in result.stderr
        assert "usage:" in result.stdout.lower()

    def test_export_without_clinical_records(self, tmp_path):
        result = run_cli(PARSE, tmp_path)
        assert result.returncode == 1
        assert _("Folder \"clinical-records\" not found in export folder \"{0}\". Ensure data has "
                 "been connected to Apple Health before export.").format(tmp_path) in result.stderr

    def test_unknown_option(self, export_dir):
        result = run_cli(PARSE, export_dir, "--no_such_option")
        assert result.returncode == 2
        assert "unrecognized arguments: --no_such_option" in result.stderr

    @pytest.mark.parametrize("option, message", [
        ("--start_year=abc", _("\"{0}\" is not a valid year.").format("abc")),
        ("--skip_dates=2023-13-45",
         _("\"{0}\" is not a valid list of dates in format YYYY-MM-DD.").format("2023-13-45")),
        ("--in_range_abnormal_boundary=0.6",
         _("\"{0}\" is not a valid decimal-formatted percentage: its absolute value must be "
           "less than 0.5.").format(0.6)),
        ("--in_range_abnormal_boundary=lots",
         _("\"{0}\" is not a valid decimal-formatted percentage.").format("lots")),
        ("--birth_date=yesterday", _("\"{0}\" is not a valid date in format YYYY-MM-DD.").format("yesterday")),
        ("--report_highlight_abnormal_results=maybe",
         _("{0} value \"{1}\" is not a boolean (true or false).").format(
             "--report_highlight_abnormal_results", "maybe")),
    ])
    def test_invalid_option_values(self, export_dir, option, message):
        result = run_cli(PARSE, export_dir, option)
        assert result.returncode == 1
        assert message in result.stderr

    @pytest.mark.parametrize("option", ["--start_year=abc", "--start-year=abc"])
    def test_hyphenated_aliases(self, export_dir, option):
        result = run_cli(PARSE, export_dir, option)
        assert _("\"{0}\" is not a valid year.").format("abc") in result.stderr

    def test_output_dir_that_is_a_file(self, export_dir, tmp_path):
        path = tmp_path / "reports"
        path.write_text("", encoding="utf-8")
        result = run_cli(PARSE, export_dir, "--output-dir", path)
        assert result.returncode == 1
        assert _("Output directory \"{0}\" is a file.").format(path) in result.stderr

    def test_run_failure_exits_with_message(self, export_dir, tmp_path):
        result = run_cli(PARSE, export_dir, f"--food_data={tmp_path / 'missing.csv'}")
        assert result.returncode == 1
        assert _("Failed to assemble or analyze food data provided.") in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_flag(self, export_dir, flag):
        result = run_cli(PARSE, export_dir, flag)
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()


class TestGenerateDiagnosticReportFilesCli:
    def test_no_arguments_prints_help(self):
        result = run_cli(REPORTS)
        assert result.returncode == 0
        assert reports_help_text().strip() in result.stdout

    def test_writes_reports_next_to_csv(self, tmp_path):
        csv_path = tmp_path / "observations_data.csv"
        csv_path.write_text(OBSERVATIONS_CSV, encoding="utf-8")

        result = run_cli(REPORTS, csv_path)

        assert result.returncode == 0, result.stderr
        assert len(list(tmp_path.glob("DiagnosticReport-*-CUSTOM.json"))) == 1

    def test_invalid_csv(self, tmp_path):
        result = run_cli(REPORTS, tmp_path / "missing.csv")
        assert result.returncode == 1
        assert _("Custom observation results CSV file \"{0}\" is invalid.").format(
            tmp_path / "missing.csv") in result.stderr
        assert reports_help_text().strip() in result.stdout


class TestRootCompatibilityScripts:
    """parse_data.py and generate_diagnostic_report_files.py at the repo root
    forward to the package CLIs, so existing commands keep working."""

    @pytest.mark.parametrize("script", ["parse_data.py", "generate_diagnostic_report_files.py"])
    def test_no_arguments_prints_help(self, script):
        result = run_root_script(script)
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()

    def test_parse_data_reports_errors(self, tmp_path):
        result = run_root_script("parse_data.py", tmp_path / "missing")
        assert result.returncode == 1
        assert invalid_export_message(tmp_path / "missing") in result.stderr
