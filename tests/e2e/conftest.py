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
    return Database(db_path)


@pytest.fixture
def _mock_state_db(_isolate_env):
    """Returns the StateStore DB path. Compatibility wrapper."""
    from specweaver.core.flow.engine.store import StateStore

    return StateStore(_isolate_env / "pipeline_state.db")
