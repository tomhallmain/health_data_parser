"""The CLI entry points, run as subprocesses: their option handling lives in
main() functions that end the process with sys.exit. Subprocesses inherit the
environment conftest.py isolates, so they also write logs under the test home."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

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


def run_cli(module, *args):
    return _run(["-m", module], *args)


def run_root_script(script, *args):
    return _run([str(REPO_ROOT / script)], *args)


class TestParseDataCli:
    def test_no_arguments_prints_help(self):
        result = run_cli(PARSE)
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_invalid_export_dir(self, tmp_path):
        result = run_cli(PARSE, tmp_path / "missing")
        assert result.returncode == 1
        assert "is invalid" in result.stderr
        assert "Usage:" in result.stdout

    def test_export_without_clinical_records(self, tmp_path):
        result = run_cli(PARSE, tmp_path)
        assert result.returncode == 1
        assert "clinical-records" in result.stderr

    def test_unknown_option(self, export_dir):
        result = run_cli(PARSE, export_dir, "--no_such_option")
        assert result.returncode == 2
        assert "Usage:" in result.stdout

    @pytest.mark.parametrize("option, message", [
        ("--start_year=abc", "is not a valid year"),
        ("--skip_dates=2023-13-45", "is not a valid list of dates"),
        ("--in_range_abnormal_boundary=0.6", "is not a valid decimal-formatted percentage"),
        ("--birth_date=yesterday", "is not a valid list of date"),
    ])
    def test_invalid_option_values(self, export_dir, option, message):
        result = run_cli(PARSE, export_dir, option)
        assert result.returncode == 1
        assert message in result.stderr

    def test_run_failure_exits_with_message(self, export_dir, tmp_path):
        result = run_cli(PARSE, export_dir, f"--food_data={tmp_path / 'missing.csv'}")
        assert result.returncode == 1
        assert "Failed to assemble or analyze food data provided." in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.xfail(reason="Known bug: the help check tests `\"-h\" in opts`, but opts holds "
                              "(option, value) tuples, so -h reaches `assert False`")
    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_flag(self, export_dir, flag):
        result = run_cli(PARSE, export_dir, flag)
        assert result.returncode == 0
        assert "Usage:" in result.stdout


class TestGenerateDiagnosticReportFilesCli:
    def test_no_arguments_prints_help(self):
        result = run_cli(REPORTS)
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_writes_reports_next_to_csv(self, tmp_path):
        csv_path = tmp_path / "observations_data.csv"
        csv_path.write_text(OBSERVATIONS_CSV, encoding="utf-8")

        result = run_cli(REPORTS, csv_path)

        assert result.returncode == 0, result.stderr
        assert len(list(tmp_path.glob("DiagnosticReport-*-CUSTOM.json"))) == 1

    def test_invalid_csv(self, tmp_path):
        result = run_cli(REPORTS, tmp_path / "missing.csv")
        assert result.returncode == 1
        assert "is invalid" in result.stderr
        assert "Usage:" in result.stdout


class TestRootCompatibilityScripts:
    """parse_data.py and generate_diagnostic_report_files.py at the repo root
    forward to the package CLIs, so existing commands keep working."""

    @pytest.mark.parametrize("script", ["parse_data.py", "generate_diagnostic_report_files.py"])
    def test_no_arguments_prints_help(self, script):
        result = run_root_script(script)
        assert result.returncode == 0, result.stderr
        assert "Usage:" in result.stdout

    def test_parse_data_reports_errors(self, tmp_path):
        result = run_root_script("parse_data.py", tmp_path / "missing")
        assert result.returncode == 1
        assert "is invalid" in result.stderr
