import json
from pathlib import Path

log_file = Path("C:/Users/steve/AppData/Local/Temp/pytest-of-steve/pytest-1502/test_logging_routing_and_forma0/logs/integration_test/specweaver.log")
lines = log_file.read_text("utf-8").strip().splitlines()

print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines):
    try:
        parsed = json.loads(line)
        print(f"Line {i} parsed successfully: {parsed['levelname']} - {parsed['message']}")
    except json.JSONDecodeError as e:
        print(f"Line {i} failed to parse: {e}")
        print(repr(line))
