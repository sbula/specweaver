"""Agent Memory Bank — custom exceptions."""
import uuid

from specweaver.workspace.memory.store import TaskStatus


class IllegalStateTransitionError(Exception):
    """Raised when a task state transition violates the allowed matrix (AD-15).

    Attributes:
        task_id: The UUID of the task.
        from_status: The current status of the task.
        to_status: The requested target status.
    """

    def __init__(self, task_id: uuid.UUID, from_status: TaskStatus, to_status: TaskStatus) -> None:
        self.task_id = task_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Illegal state transition for task {task_id}: "
            f"{from_status.value} → {to_status.value}"
        )


class DefectBlocksCompletionError(Exception):
    """Raised when a task cannot transition to DONE due to OPEN defects (AD-8).

    Attributes:
        task_id: The UUID of the task.
        open_defect_count: Number of OPEN defects blocking the transition.
    """

    def __init__(self, task_id: uuid.UUID, open_defect_count: int) -> None:
        self.task_id = task_id
        self.open_defect_count = open_defect_count
        super().__init__(
            f"Cannot complete task {task_id}: "
            f"{open_defect_count} OPEN defect(s) must be resolved first"
        )


class CyclicDependencyError(Exception):
    """Raised when inserting a dependency would create a cycle in the DAG (AD-7).

    Attributes:
        parent_task_id: The UUID of the parent task.
        child_task_id: The UUID of the child task.
    """

    def __init__(self, parent_task_id: uuid.UUID, child_task_id: uuid.UUID) -> None:
        self.parent_task_id = parent_task_id
        self.child_task_id = child_task_id
        super().__init__(
            f"Cyclic dependency detected: inserting edge "
            f"{parent_task_id} → {child_task_id} would create a cycle"
        )


class StaleTaskVersionError(Exception):
    """Raised when OCC version mismatch prevents task acquisition (AD-6).

    Attributes:
        task_id: The UUID of the task.
        expected_version: The version the caller expected.
        actual_version: The current version in the DB.
    """

    def __init__(self, task_id: uuid.UUID, expected_version: int, actual_version: int) -> None:
        self.task_id = task_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Stale version for task {task_id}: "
            f"expected {expected_version}, found {actual_version}"
        )
