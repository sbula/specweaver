import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.errors import DefectBlocksCompletionError
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.memory.store import (
    EpicStatus,
    Task,
    TaskStatus,
    TransitionReason,
)
from specweaver.workspace.store import Base, Project


@pytest_asyncio.fixture
async def engine():
    """Create an in-memory SQLite database with schema and FK constraints."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Provide a transactional scoped session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def base_project(session: AsyncSession) -> Project:
    """Create a foundational Project row for FK references."""
    now = datetime.now(UTC)
    project = Project(
        name="test_proj",
        root_path="/tmp/test",
        created_at=now,
        last_used_at=now,
    )
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


@pytest.mark.asyncio
class TestMemoryBankIntegrationSimulations:
    """Simulates the SF-3/SF-4 Orchestrator logic driving the MemoryRepository."""

    async def test_int_1_orchestrator_happy_path(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 1: Agent Orchestrator acquires, executes, and transitions to DONE."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Write tests")

        # Simulate Orchestrator Selection
        acquired = await repo.transition_state(uuid.UUID(task["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        assert acquired["status"] == TaskStatus.IN_PROGRESS.value

        # Simulate Execution Success
        completed = await repo.transition_state(uuid.UUID(task["id"]), TaskStatus.DONE, TransitionReason.COMPLETED)
        assert completed["status"] == TaskStatus.DONE.value

    async def test_int_2_zombie_reaper(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 2: Zombie Reaper identifies stale task, transitions to BLOCKED, bumps attempt_count."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Zombie Task")
        await repo.transition_state(uuid.UUID(task["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)

        # Artificial Backdate
        task_model = await session.get(Task, uuid.UUID(task["id"]))
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=15)
        await session.flush()

        # Simulate Reaper Script
        stmt = select(Task).where(Task.status == TaskStatus.IN_PROGRESS)
        stale_tasks = (await session.execute(stmt)).scalars().all()
        assert len(stale_tasks) == 1

        reaped = await repo.transition_state(stale_tasks[0].id, TaskStatus.BLOCKED, TransitionReason.ZOMBIE_TIMEOUT)
        assert reaped["status"] == TaskStatus.BLOCKED.value
        assert reaped["attempt_count"] == 1
        assert reaped["locked_at"] is None

    async def test_int_4_dag_resolution(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 4: Resolving parent automatically unblocks child tasks."""
        repo = MemoryRepository(session)
        parent = await repo.create_task(project_name=base_project.name, title="Parent")
        child = await repo.create_task(project_name=base_project.name, title="Child")
        await repo.add_task_dependency(uuid.UUID(parent["id"]), uuid.UUID(child["id"]))

        # Child is upstream blocked
        await repo.transition_state(uuid.UUID(child["id"]), TaskStatus.UPSTREAM_BLOCKED, TransitionReason.UPSTREAM_BLOCKED)

        # Parent finishes
        await repo.transition_state(uuid.UUID(parent["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(uuid.UUID(parent["id"]), TaskStatus.DONE, TransitionReason.COMPLETED)

        # Simulate DAG Manager unblocking children
        child_unblocked = await repo.transition_state(uuid.UUID(child["id"]), TaskStatus.PENDING, TransitionReason.UPSTREAM_CLEARED)
        assert child_unblocked["status"] == TaskStatus.PENDING.value

    async def test_int_5_defect_interception(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 5: DefectBlocksCompletionError intercepts DONE transition."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Buggy Task")
        await repo.transition_state(uuid.UUID(task["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)

        # Agent logs defect
        await repo.create_defect(uuid.UUID(task["id"]), title="Tests fail")

        # Agent tries to complete
        with pytest.raises(DefectBlocksCompletionError):
            await repo.transition_state(uuid.UUID(task["id"]), TaskStatus.DONE, TransitionReason.COMPLETED)

        # Orchestrator catches it and forces BLOCKED for human intervention
        blocked = await repo.transition_state(uuid.UUID(task["id"]), TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)
        assert blocked["status"] == TaskStatus.BLOCKED.value

    async def test_int_6_circuit_breaker(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 6: Circuit Breaker suspends tasks with attempt_count >= 3."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Failing Task")
        task_id = uuid.UUID(task["id"])

        for _ in range(3):
            await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
            await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)
            # Re-queue the task for the next attempt
            await repo.transition_state(task_id, TaskStatus.PENDING, TransitionReason.MANUAL_UNBLOCK)

        task_info = await repo.get_task(task_id)
        assert task_info["attempt_count"] == 3

        # Simulate Circuit Breaker Orchestrator
        if task_info["attempt_count"] >= 3:
            # Prevent re-queue, force it to BLOCKED
            await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)
            task_info = await repo.get_task(task_id)
            assert task_info["status"] == TaskStatus.BLOCKED.value

    async def test_int_7_agent_handoff(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 7: Agent handoff via handover_context."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Handoff Task")
        task_id = uuid.UUID(task["id"])

        # Agent 1
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.update_handover_context(task_id, "Wrote frontend, need backend API")
        await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)

        # Human/Orchestrator unblocks it for Agent 2
        await repo.transition_state(task_id, TaskStatus.PENDING, TransitionReason.MANUAL_UNBLOCK)

        # Agent 2
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        task_info = await repo.get_task(task_id)
        assert task_info["handover_context"] == "Wrote frontend, need backend API"
        await repo.transition_state(task_id, TaskStatus.DONE, TransitionReason.COMPLETED)

    async def test_int_8_upstream_cascading_failure(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 8: Parent failure halts children."""
        repo = MemoryRepository(session)
        parent = await repo.create_task(project_name=base_project.name, title="Parent")
        child = await repo.create_task(project_name=base_project.name, title="Child")
        await repo.add_task_dependency(uuid.UUID(parent["id"]), uuid.UUID(child["id"]))

        # Child waits
        await repo.transition_state(uuid.UUID(child["id"]), TaskStatus.UPSTREAM_BLOCKED, TransitionReason.UPSTREAM_BLOCKED)

        # Parent permanently fails
        await repo.transition_state(uuid.UUID(parent["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(uuid.UUID(parent["id"]), TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)
        await repo.transition_state(uuid.UUID(parent["id"]), TaskStatus.ARCHIVED, TransitionReason.ABANDONED)

        # Simulate Orchestrator deciding child destiny
        parent_status = (await repo.get_task(uuid.UUID(parent["id"])))["status"]
        if parent_status == TaskStatus.ARCHIVED.value:
            child_archived = await repo.transition_state(uuid.UUID(child["id"]), TaskStatus.ARCHIVED, TransitionReason.ABANDONED)
            assert child_archived["status"] == TaskStatus.ARCHIVED.value

    async def test_e2e_1_topological_execution_simulation(self, session: AsyncSession, base_project: Project) -> None:
        """E2E 1: Epic + DAG topological execution simulation."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="New Feature")

        t1 = await repo.create_task(project_name=base_project.name, title="DB Schema", epic_id=uuid.UUID(epic["id"]))
        t2 = await repo.create_task(project_name=base_project.name, title="API Layer", epic_id=uuid.UUID(epic["id"]))
        await repo.add_task_dependency(uuid.UUID(t1["id"]), uuid.UUID(t2["id"]))

        # Initial states
        await repo.transition_state(uuid.UUID(t2["id"]), TaskStatus.UPSTREAM_BLOCKED, TransitionReason.UPSTREAM_BLOCKED)

        # Exec T1
        await repo.transition_state(uuid.UUID(t1["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(uuid.UUID(t1["id"]), TaskStatus.DONE, TransitionReason.COMPLETED)

        # Unblock T2
        await repo.transition_state(uuid.UUID(t2["id"]), TaskStatus.PENDING, TransitionReason.UPSTREAM_CLEARED)

        # Exec T2
        await repo.transition_state(uuid.UUID(t2["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(uuid.UUID(t2["id"]), TaskStatus.DONE, TransitionReason.COMPLETED)

        # Complete Epic
        await repo.close_epic(uuid.UUID(epic["id"]))

        epic_final = await repo.get_epic(uuid.UUID(epic["id"]))
        assert epic_final["status"] == EpicStatus.CLOSED.value

    async def test_e2e_3_sticky_bug_simulation(self, session: AsyncSession, base_project: Project) -> None:
        """E2E 3: Agent logs defect, human fixes, agent resumes."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(task["id"])

        # Agent fails
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        defect = await repo.create_defect(task_id, title="Bug")
        await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)

        # Human fixes bug via CLI
        await repo.resolve_defect(defect["id"])
        await repo.transition_state(task_id, TaskStatus.PENDING, TransitionReason.MANUAL_UNBLOCK)

        # Agent resumes
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(task_id, TaskStatus.DONE, TransitionReason.COMPLETED)

    async def test_e2e_5_automatic_epic_closure_simulation(self, session: AsyncSession, base_project: Project) -> None:
        """E2E 5: Final task triggers Epic CLOSE."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Epic")
        epic_id = uuid.UUID(epic["id"])

        t1 = await repo.create_task(project_name=base_project.name, title="T1", epic_id=epic_id)

        await repo.transition_state(uuid.UUID(t1["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(uuid.UUID(t1["id"]), TaskStatus.DONE, TransitionReason.COMPLETED)

        # Simulate Orchestrator polling
        stmt = select(Task).where(Task.epic_id == epic_id, Task.status != TaskStatus.DONE)
        remaining = (await session.execute(stmt)).scalars().all()

        if not remaining:
            closed_epic = await repo.close_epic(epic_id)
            assert closed_epic["status"] == EpicStatus.CLOSED.value
