
import pytest

from specweaver.core.config.database import get_global_write_queue


@pytest.fixture(autouse=True)
async def cleanup_cqrs_queue():
    yield
    queue = get_global_write_queue()
    await queue.stop()

@pytest.fixture(autouse=True)
def mock_global_db_path(tmp_path_factory, monkeypatch):
    """Ensure no test ever touches the real ~/.specweaver/specweaver.db."""
    test_db_dir = tmp_path_factory.mktemp("global_db")
    test_db_path = test_db_dir / "specweaver.db"
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.config_db_path", lambda: test_db_path)

