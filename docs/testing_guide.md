# SpecWeaver Testing Guide

This guide covers how to execute the SpecWeaver test suite effectively using `pytest`. Following these commands ensures you only run what you intend to, avoiding side-effects on unrelated components.

> [!WARNING]
> Before running the tests, verify that you are running within your initialized Python virtual environment where your dependencies (`pip install -e .[dev]`) are configured. Do not run random `pip install` commands globally, as it will pollute your environment.

## 1. Running the Whole Test Suite
To run all tests across all layers (Unit, Integration, E2E), use the root command:
```bash
pytest
```
*Tip:* To see shorter output, you can use: `pytest -q` (quiet) or `pytest -v` (verbose).

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
3. Run flow integration tests: `pytest tests/integration/flow`
4. Once satisfied, run the entire test suite to ensure no regressions: `pytest`
