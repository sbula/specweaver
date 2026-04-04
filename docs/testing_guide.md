# SpecWeaver Testing Guide

This guide covers how to execute the SpecWeaver test suite effectively using `pytest`. Following these commands ensures you only run what you intend to, avoiding side-effects on unrelated components.

> [!WARNING]
> Before running the tests, verify that you are running within your initialized Python virtual environment where your dependencies (`pip install -e .[dev]`) are configured. Do not run random `pip install` commands globally, as it will pollute your environment.

## 1. Running the Whole Test Suite
To run all tests across all layers (Unit, Integration, E2E), use the root command:
```bash
pytest
```
*Tip:* To see shorter output, you can use: `pytest -q` (quiet) or `pytest -v` (verbose). For deep debugging of failures, inspect the `logs/<project_name>/specweaver.log` which outputs full NDJSON tracebacks.

## 2. Running Specific Testing Layers
SpecWeaver organizes tests into distinct layers. You can run them separately or combine them by passing multiple test paths.

**Unit Tests Only:**
```bash
pytest tests/unit
```

**Integration Tests Only:**
```bash
pytest tests/integration
```

**E2E Tests Only:**
```bash
pytest tests/e2e
```

**Multiple Layers Together:**
To run unit and integration tests but skip end-to-end (e2e):
```bash
pytest tests/unit tests/integration
```

## 3. Running Tests for a Specific Feature or Module
If you only want to test a specific module (e.g., the Flow Engine or Standards Analyzer) without running the entire suite, point `pytest` to its directory:

**Example - All Flow Engine tests (Unit + Integration):**
```bash
pytest tests/unit/flow tests/integration/flow
```

**Example - All Standards Analyzer tests:**
```bash
pytest tests/unit/standards
```

## 4. Running a Specific File
If you are iterating on a single file, run only its corresponding test file:
```bash
pytest tests/unit/flow/test_engine.py
```

## 5. Running a Specific Test Class or Single Test Function
To laser-focus on a single test or test class within a file, append the `::` syntax.

**Running a specific class inside a test file:**
```bash
pytest tests/integration/flow/test_flow_engine.py::TestFlowEngineCompletion
```

**Running a specific test method:**
```bash
pytest tests/integration/flow/test_flow_engine.py::test_empty_pipeline_completes_immediately
```

## 6. Advanced Filtering by Keyword
You can run any tests whose names match a specific keyword string (regardless of what file they are in) using the `-k` flag:
```bash
pytest -k "hitl"           # Runs any test function/class containing "hitl"
pytest -k "not validate"   # Runs tests except those containing "validate"
```

## Typical Daily Workflow
1. Write/modify a file: `src/specweaver/flow/engine.py`
2. Run its specific unit tests: `pytest tests/unit/flow/test_engine.py`
3. Run module-level integration tests: `pytest tests/integration/flow`
4. Run linting + complexity checks: `ruff check src/specweaver/`
5. Run type checking on modified files: `mypy src/specweaver/flow/engine.py --ignore-missing-imports`
6. Once satisfied, run the full test suite: `pytest`

## 7. Code Quality Gates

### Linting & Formatting (Ruff)
SpecWeaver uses [Ruff](https://docs.astral.sh/ruff/) for linting and import sorting. Configuration is in `pyproject.toml`.

**Full project check:**
```bash
ruff check src/specweaver/
```

**Check specific files:**
```bash
ruff check src/specweaver/cli/standards.py src/specweaver/project/constitution.py
```

**Auto-fix safe issues:**
```bash
ruff check --fix src/specweaver/
```

**Key rules enforced:**
| Rule | Description |
|------|-------------|
| C901 | Cyclomatic complexity limit ≤ 10 |
| B007 | Unused loop variables must be prefixed with `_` |
| I001 | Import block must be sorted |
| TC001/TC003 | Type-only imports belong in `TYPE_CHECKING` |
| SIM102/SIM108 | Simplifiable control flow |
| N806 | Function-scope variables must be lowercase |

### Type Checking (mypy)
SpecWeaver uses [mypy](https://mypy.readthedocs.io/) in strict mode. Configuration is in `pyproject.toml` under `[tool.mypy]`.

**Check specific files:**
```bash
mypy src/specweaver/project/constitution.py --ignore-missing-imports
```

> [!NOTE]
> The `--ignore-missing-imports` flag suppresses errors for third-party packages that lack type stubs. The project itself must have full type annotations.

### File Size Limits
Keep source files under **500 lines**. If a file grows beyond this, consider refactoring into smaller modules.

## 8. Module-Specific Test Examples

### Standards / Constitution (Feature 3.5a-4)
```bash
# All constitution tests (unit)
pytest tests/unit/project/test_constitution.py

# All standards tests (unit + integration)
pytest tests/unit/standards tests/integration/cli/test_cli_standards_integration.py

# Config database tests (includes schema migrations)
pytest tests/unit/config/test_database.py

# CLI tests for constitution and config commands
pytest tests/unit/cli/test_constitution.py tests/unit/cli/test_config.py
```

### Flow Engine
```bash
pytest tests/unit/flow tests/integration/flow
```

### Validation Rules
```bash
pytest tests/unit/validation tests/integration/validation
```

## 9. Pre-Commit Test Gap Analysis
Before marking a feature as done, run the `/pre-commit-test-gap` workflow (`.agents/workflows/pre-commit-test-gap.md`). This workflow:
1. Reviews every modified source file line-by-line
2. Identifies untested branches, guards, and edge cases
3. Produces a gap table per module
4. Updates the [Test Coverage Matrix](test_coverage_matrix.md)

## 10. Coverage Target
The project aims for **70–90% test coverage**. This balances thorough testing with practical development speed.

## 11. Deselected Tests (`@pytest.mark.live`)

12 tests are marked `@pytest.mark.live` and are **excluded from every normal test run** by `addopts = "-m 'not live'"` in `pyproject.toml`.

**Why:** These tests call real external APIs (e.g., Google Gemini) and require:
- Valid API keys set as environment variables
- Network access
- Quota/billing on the target service

**How to run them:**
```bash
pytest -m live                       # Run ONLY live tests
pytest -m "live" --tb=long -v        # With verbose output
```

**When to run:** Before releases, after changing LLM adapter code, or when troubleshooting API integration issues. Never in automated CI without secrets configured.

**Files containing live tests:**
- `tests/manual/test_llm_live.py` — Gemini API connectivity
- `tests/manual/test_stitch_live.py` — Stitch/MCP integration

## 12. Skipped Tests (Platform Limitations)

Some tests are skipped at runtime via `pytest.skip()` or `skipIf()` due to **platform-specific limitations**. These are not failures — they are expected on certain operating systems.

### Windows Skips (5 tests in `test_executor.py`)

| Test | Reason |
|------|--------|
| `test_read_symlink` | Symlinks require admin privileges on Windows |
| `test_list_directory_with_symlink` | Symlinks require admin privileges on Windows |
| `test_write_to_readonly_file` | `chmod` doesn't enforce read-only on Windows |
| `test_create_in_readonly_dir` | `chmod` doesn't enforce read-only on Windows |
| `test_delete_readonly_file` | `chmod` doesn't enforce read-only on Windows |

These tests pass on Linux/macOS. No action needed.

### Empty Parameterized Set (1 test in `test_interfaces.py`)

`TestImplementerMethodVisibility::test_missing_method` — the implementer role has **all** filesystem methods (`_ALL_METHODS == _IMPLEMENTER_METHODS`), so `_ALL_METHODS - _IMPLEMENTER_METHODS` is empty. Pytest skips parameterized tests with no parameters. This is correct by design — there are no methods the implementer should lack.

---

**Related Documents:**
- [Test Coverage Matrix](test_coverage_matrix.md) — per-module test story inventory
- [Pre-Commit Test Gap Workflow](../.agents/workflows/pre-commit-test-gap.md) — automated gap analysis
- [Architecture Completeness Tests](architecture/completeness_tests.md) — structural verification

