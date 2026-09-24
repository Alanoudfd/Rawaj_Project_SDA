"""Run the offline journey checks without emailing restaurants or calling paid providers."""
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "tests/test_requested_lifecycle.py", "-v"],
                                    cwd=Path(__file__).resolve().parents[1]))
