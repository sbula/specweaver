import subprocess

import sys

with open("pytest_e2e_full.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(["pytest", "tests/e2e", "-v", "--tb=short"], stdout=f, stderr=subprocess.STDOUT, text=True)
    sys.exit(result.returncode)
