import subprocess
import sys

with open("pytest_unit_full.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(["pytest", "tests/unit", "-v", "--tb=short"], stdout=f, stderr=subprocess.STDOUT, text=True)
    sys.exit(result.returncode)
