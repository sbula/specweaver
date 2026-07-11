---
description: "Phase 5: Code quality checks — ruff, mypy, complexity, and file size limits."
---

# Phase 5: Code Quality Checks

5.1. Run **ruff lint** on the entire repo:
     ```
     python -m ruff check src/ tests/
     ```
     Every error MUST be fixed — no exceptions, regardless of whether the error
     is pre-existing or newly introduced!

5.2. Run **mypy type check** on the source tree:
     ```
     python -m mypy src/
     ```
     Every error MUST be fixed — no exceptions!

5.3. Run **file complexity** check (C901 max complexity = 10):
     ```
     python -m ruff check src/ --select C901
     ```
     Every violation MUST be fixed by extracting helper functions!

5.4. Run **lines-of-code per file** check (max 500 lines per source file):
     ```
     uv run python scripts/check_file_sizes.py
     ```
     Files over 500 lines MUST be refactored by splitting into smaller modules!

5.5. Run **tach architecture check** to verify domain isolation boundary rules:
     ```
     tach check
     ```
     Every violation MUST be fixed by explicitly removing or circumventing the illegal dependencies!

> [!IMPORTANT]
> **NO HITL GATE HERE:** If all checks in Phase 5 pass successfully, update `task.md` and PROCEED IMMEDIATELY to Phase 6. Do NOT stop to ask the user for permission to continue.
