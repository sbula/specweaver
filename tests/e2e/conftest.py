# mypy: ignore-errors
from pathlib import Path

import pytest

from specweaver.core.config.database import Database


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path: Path, monkeypatch):
    """Isolate SpecWeaver data directory using the OS environment variable for true E2E testing."""
    test_data_dir = tmp_path / ".specweaver-test"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(test_data_dir))
    return test_data_dir


@pytest.fixture
def _mock_db(_isolate_env):
    """
    Returns a Database instance for verification without mocking Python code paths.
    Called '_mock_db' purely for compatibility with existing tests.
    """
    db_path = _isolate_env / "specweaver.db"
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(db_path))
    return Database(db_path)


@pytest.fixture
def _mock_state_db(_isolate_env):
    """Returns the StateStore DB path. Compatibility wrapper."""
    from specweaver.core.flow.engine.store import StateStore

    return StateStore(_isolate_env / "pipeline_state.db")


@pytest.fixture
def stub_implement_qa():
    """Stub the QA steps that INT-US-03 SF-01 appended to `sw implement`.

    `sw implement` now runs `run_tests` + `validate_code` in-pipeline. E2E tests
    that invoke `sw implement` to exercise *other* behavior (lineage tags,
    constitution injection, lifecycle routing) — with a mock LLM whose generated
    "test" file has no collectable tests — would otherwise fail QA (0 tests → exit 1).
    This opt-in fixture stubs both QA handlers to PASSED so those tests stay focused;
    real QA execution is proven by the SF-03 verifiable-proof e2e.
    """
    from unittest.mock import AsyncMock, patch

    from specweaver.core.flow.engine.state import StepResult, StepStatus

    def _ok(output):
        return StepResult(
            status=StepStatus.PASSED,
            output=output,
            error_message="",
            started_at="t0",
            completed_at="t1",
        )

    with (
        patch(
            "specweaver.core.flow.handlers.validation.ValidateTestsHandler.execute",
            new=AsyncMock(
                return_value=_ok({"passed": 1, "failed": 0, "total": 1, "coverage_pct": 100})
            ),
        ),
        patch(
            "specweaver.core.flow.handlers.validation.ValidateCodeHandler.execute",
            new=AsyncMock(return_value=_ok({"passed": 8, "failed": 0, "total": 8, "results": []})),
        ),
    ):
        yield
