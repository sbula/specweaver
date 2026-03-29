import subprocess
# Run tests with -s to show standard output, which will include logging and tracebacks
import sys
with open("pytest_implement.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(["pytest", "tests/integration/cli/test_cli_implement.py", "-s", "--log-cli-level=DEBUG"], stdout=f, stderr=subprocess.STDOUT, text=True)
    sys.exit(result.returncode)
