import subprocess

result = subprocess.run(["pytest", "tests", "-q", "--tb=line"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

with open("pytest_failures.txt", "w", encoding="utf-8") as f:
    for line in result.stdout.splitlines():
        if line.startswith("FAILED") or line.startswith("ERROR"):
            f.write(line + "\n")

import sys
sys.exit(result.returncode)
