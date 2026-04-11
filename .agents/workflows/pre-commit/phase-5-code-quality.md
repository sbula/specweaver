---
description: "Phase 5: Code quality checks — ruff, mypy, complexity, and file size limits."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set `SafeToAutoRun: true` for ALL of these commands.
> **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 5: Code Quality Checks

// turbo-all

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
