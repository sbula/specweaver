import subprocess

import sys

with open("pytest_integ_full.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(["pytest", "tests/integration", "-v", "--tb=short"], stdout=f, stderr=subprocess.STDOUT, text=True)
    sys.exit(result.returncode)
