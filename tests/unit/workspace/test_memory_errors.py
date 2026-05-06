import uuid

from specweaver.workspace.memory.errors import CyclicDependencyError, StaleTaskVersionError


def test_cyclic_dependency_error_formatting() -> None:
    """[Happy Path] Exception correctly formats its error message with the provided UUIDs."""
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()
    error = CyclicDependencyError(parent_id, child_id)

    msg = str(error)
    assert str(parent_id) in msg
    assert str(child_id) in msg
    assert "Cyclic dependency detected" in msg


def test_stale_task_version_error_formatting() -> None:
    """[Happy Path] Exception correctly formats its error message with the versions."""
    task_id = uuid.uuid4()
    error = StaleTaskVersionError(task_id, expected_version=1, actual_version=2)

    msg = str(error)
    assert str(task_id) in msg
    assert "expected 1" in msg
    assert "found 2" in msg
