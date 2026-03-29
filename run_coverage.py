import subprocess

import sys

with open("coverage_report.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(
        ["pytest", "tests/", "--cov=src", "--cov-report=term-missing"],
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True
    )
    sys.exit(result.returncode)
