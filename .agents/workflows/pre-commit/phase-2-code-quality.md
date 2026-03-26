---
description: "Phase 2: Code quality checks — ruff, mypy, complexity, and file size limits."
---

# Phase 2: Code Quality Checks

// turbo-all

2.1. Run **ruff lint** on the entire repo:
     ```
     python -m ruff check src/ tests/
     ```
     Every error MUST be fixed — no exceptions, regardless of whether the error
     is pre-existing or newly introduced!

2.2. Run **mypy type check** on the source tree:
     ```
     python -m mypy src/
     ```
     Every error MUST be fixed — no exceptions!

2.3. Run **file complexity** check (C901 max complexity = 10):
     ```
     python -m ruff check src/ --select C901
     ```
     Every violation MUST be fixed by extracting helper functions!

2.4. Run **lines-of-code per file** check (max 500 lines per source file):
     ```
     python -c "from pathlib import Path; files = [f for f in Path('src').rglob('*.py') if f.stat().st_size > 0]; big = [(f, len(f.read_text(encoding='utf-8').splitlines())) for f in files if len(f.read_text(encoding='utf-8').splitlines()) > 500]; [print(f'{loc} lines: {f}') for f, loc in sorted(big, key=lambda x: -x[1])]; print(f'{len(big)} file(s) over 500 lines') if big else print('All files within 500-line limit')"
     ```
     Files over 500 lines MUST be refactored by splitting into smaller modules!

> [!IMPORTANT]
> **CHECKPOINT:** Phase 2 is complete. Update `task.md`.
> The NEXT phase is Phase 3 (Test Gap Analysis) — NOT running pytest!
