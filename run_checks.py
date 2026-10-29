"""Run the repository's automated tests and report a nonzero exit on failure."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

print("Running HOAS specification and prototype tests...")
result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
if result.returncode:
    raise SystemExit(result.returncode)
print("All discovered tests passed.")
print("To regenerate specification exports, run: python scripts/generate_specifications.py")
