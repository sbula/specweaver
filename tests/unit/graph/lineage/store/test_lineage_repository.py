import pytest
from pathlib import Path
from typing import Any

from specweaver.graph.lineage.store.lineage_repository import LineageRepository


@pytest.fixture()
def repo(tmp_path: Path) -> LineageRepository:
    from specweaver.core.config.db_bootstrap import bootstrap_database

    db_path = str(tmp_path / "lineage.db")
    bootstrap_database(db_path)
    return LineageRepository(db_path)


class TestLineageRepository:
    """Artifact event logging and history."""

    def test_log_artifact_event_unparented(self, repo: LineageRepository) -> None:
        repo.log_artifact_event("uuid-1", None, "run-1", "CREATED", "gemini-test")
        history = repo.get_artifact_history("uuid-1")
        assert len(history) == 1
        assert history[0]["artifact_id"] == "uuid-1"
        assert history[0]["parent_id"] is None
        assert history[0]["run_id"] == "run-1"
        assert history[0]["event_type"] == "CREATED"
        assert history[0]["model_id"] == "gemini-test"

    def test_log_artifact_event_with_parent(self, repo: LineageRepository) -> None:
        repo.log_artifact_event("uuid-2", "uuid-1", "run-1", "CREATED", "gemini-test")
        history = repo.get_artifact_history("uuid-2")
        assert len(history) == 1
        assert history[0]["parent_id"] == "uuid-1"

    def test_multiple_events_same_artifact(self, repo: LineageRepository) -> None:
        repo.log_artifact_event("uuid-3", None, "run-1", "CREATED", "model-1")
        repo.log_artifact_event("uuid-3", None, "run-2", "MODIFIED", "model-2")
        history = repo.get_artifact_history("uuid-3")
        assert len(history) == 2
        assert history[0]["event_type"] == "CREATED"
        assert history[1]["event_type"] == "MODIFIED"

    def test_get_children(self, repo: LineageRepository) -> None:
        repo.log_artifact_event("parent-a", None, "run-1", "CREATED", "gemini-test")
        repo.log_artifact_event("child-1", "parent-a", "run-2", "CREATED", "gemini-test")
        repo.log_artifact_event("child-2", "parent-a", "run-2", "CREATED", "gemini-test")

        children = repo.get_children("parent-a")
        assert len(children) == 2
        child_ids = {c["artifact_id"] for c in children}
        assert child_ids == {"child-1", "child-2"}

    def test_get_artifact_history_empty(self, repo: LineageRepository) -> None:
        assert repo.get_artifact_history("magic-uuid") == []

    def test_get_children_empty(self, repo: LineageRepository) -> None:
        assert repo.get_children("no-kids") == []

    def test_log_artifact_event_null_constraint(self, repo: LineageRepository) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "run-1", None, "model")  # type: ignore

    def test_log_artifact_event_empty_string_validation(self, repo: LineageRepository) -> None:
        with pytest.raises(ValueError, match="artifact_id cannot be empty"):
            repo.log_artifact_event("   ", None, "run-1", "CREATED", "model")

        with pytest.raises(ValueError, match="run_id cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "", "CREATED", "model")

        with pytest.raises(ValueError, match="event_type cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "run-1", "  ", "model")

        with pytest.raises(ValueError, match="model_id cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "run-1", "CREATED", "  ")

    def test_wal_mode_set(self, repo: LineageRepository) -> None:
        with repo._get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

    def test_busy_timeout_set(self, repo: LineageRepository) -> None:
        with repo._get_connection() as conn:
            cursor = conn.execute("PRAGMA busy_timeout;")
            timeout = cursor.fetchone()[0]
            assert timeout == 5000

    def test_log_artifact_event_sql_injection(self, repo: LineageRepository) -> None:
        dangerous_id = "artifact'; DROP TABLE artifact_events; --"
        repo.log_artifact_event(dangerous_id, None, "run-1", "CREATED", "model-1")
        history = repo.get_artifact_history(dangerous_id)
        assert len(history) == 1
        assert history[0]["artifact_id"] == dangerous_id

    def test_log_artifact_event_unicode_and_special_chars(self, repo: LineageRepository) -> None:
        exotic_id = "🚀_artifact_✨_\n\t_test"
        repo.log_artifact_event(exotic_id, "parent_🔥", "run_💻", "MODIFIED", "gpt-4-turbo")
        history = repo.get_artifact_history(exotic_id)
        assert len(history) == 1
        assert history[0]["artifact_id"] == exotic_id
        assert history[0]["parent_id"] == "parent_🔥"
        assert history[0]["run_id"] == "run_💻"

    def test_log_artifact_event_concurrent_writes(self, repo: LineageRepository) -> None:
        import threading
        num_threads = 20
        threads = []
        errors: list[Exception] = []

        def worker(thread_idx: int) -> None:
            try:
                repo.log_artifact_event(
                    f"art-{thread_idx}",
                    None,
                    f"run-{thread_idx}",
                    "CREATED",
                    "model-xyz"
                )
            except Exception as e:
                errors.append(e)

        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent writes encountered errors: {errors}"
        for i in range(num_threads):
            history = repo.get_artifact_history(f"art-{i}")
            assert len(history) == 1
            assert history[0]["run_id"] == f"run-{i}"

    def test_log_artifact_event_invalid_db_path(self, tmp_path: Path) -> None:
        import sqlite3
        invalid_repo = LineageRepository(str(tmp_path))
        with pytest.raises(sqlite3.OperationalError):
            invalid_repo.log_artifact_event("uuid-1", None, "run-1", "CREATED", "model")


