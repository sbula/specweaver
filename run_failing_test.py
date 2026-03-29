import subprocess

import sys

with open("pytest_failing.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(["pytest", "tests/integration/flow/test_planning_integration.py", "tests/integration/cli/test_cli_check.py", "-v", "--tb=short"], stdout=f, stderr=subprocess.STDOUT, text=True)
    sys.exit(result.returncode)
