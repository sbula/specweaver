import subprocess
import sys
with open("pytest_implement.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(["pytest", "tests/integration/cli/test_cli_implement.py", "-v", "--tb=line"], stdout=f, stderr=subprocess.STDOUT, text=True)
    sys.exit(result.returncode)
