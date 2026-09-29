"""Charts are drawn on standalone matplotlib Figures: pyplot keeps every figure
it creates in process-wide state until closed, which leaks across GUI runs."""
from pathlib import Path
import os
import subprocess
import sys

SRC = Path(__file__).resolve().parents[2] / "src"

# Every module outside the Tk GUI (which needs a display to import tkinter
# widgets in some environments)
CHECK = """
import pkgutil, sys, importlib
import health_data_parser
for module in pkgutil.walk_packages(health_data_parser.__path__, "health_data_parser."):
    if ".tkui" in module.name or module.name.endswith("__main__"):
        continue
    importlib.import_module(module.name)
print("matplotlib.pyplot" in sys.modules)
"""


def test_package_does_not_import_pyplot():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(SRC), env.get("PYTHONPATH")]))
    result = subprocess.run([sys.executable, "-c", CHECK], env=env, capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
