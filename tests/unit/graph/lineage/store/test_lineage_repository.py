import pytest

from specweaver.graph.lineage.store.lineage_repository import LineageRepository


@pytest.fixture()
def repo(tmp_path):
    return LineageRepository(str(tmp_path / "lineage.db"))


class TestLineageRepository:
    """Artifact event logging and history."""

    def test_log_artifact_event_unparented(self, repo):
        repo.log_artifact_event("uuid-1", None, "run-1", "CREATED", "gemini-test")
        history = repo.get_artifact_history("uuid-1")
        assert len(history) == 1
        assert history[0]["artifact_id"] == "uuid-1"
        assert history[0]["parent_id"] is None
        assert history[0]["run_id"] == "run-1"
        assert history[0]["event_type"] == "CREATED"
        assert history[0]["model_id"] == "gemini-test"

    def test_log_artifact_event_with_parent(self, repo):
        repo.log_artifact_event("uuid-2", "uuid-1", "run-1", "CREATED", "gemini-test")
        history = repo.get_artifact_history("uuid-2")
        assert len(history) == 1
        assert history[0]["parent_id"] == "uuid-1"

    def test_multiple_events_same_artifact(self, repo):
        repo.log_artifact_event("uuid-3", None, "run-1", "CREATED", "model-1")
        repo.log_artifact_event("uuid-3", None, "run-2", "MODIFIED", "model-2")
        history = repo.get_artifact_history("uuid-3")
        assert len(history) == 2
        assert history[0]["event_type"] == "CREATED"
        assert history[1]["event_type"] == "MODIFIED"

    def test_get_children(self, repo):
        repo.log_artifact_event("parent-a", None, "run-1", "CREATED", "gemini-test")
        repo.log_artifact_event("child-1", "parent-a", "run-2", "CREATED", "gemini-test")
        repo.log_artifact_event("child-2", "parent-a", "run-2", "CREATED", "gemini-test")

        children = repo.get_children("parent-a")
        assert len(children) == 2
        child_ids = {c["artifact_id"] for c in children}
        assert child_ids == {"child-1", "child-2"}

    def test_get_artifact_history_empty(self, repo):
        assert repo.get_artifact_history("magic-uuid") == []

    def test_get_children_empty(self, repo):
        assert repo.get_children("no-kids") == []

    def test_log_artifact_event_null_constraint(self, repo):
        with pytest.raises(ValueError, match="cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "run-1", None, "model")  # type: ignore

    def test_log_artifact_event_empty_string_validation(self, repo):
        with pytest.raises(ValueError, match="artifact_id cannot be empty"):
            repo.log_artifact_event("   ", None, "run-1", "CREATED", "model")

        with pytest.raises(ValueError, match="run_id cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "", "CREATED", "model")

        with pytest.raises(ValueError, match="event_type cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "run-1", "  ", "model")

        with pytest.raises(ValueError, match="model_id cannot be empty"):
            repo.log_artifact_event("uuid-1", None, "run-1", "CREATED", "  ")
