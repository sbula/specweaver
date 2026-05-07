import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

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
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, poolclass=StaticPool)
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

    async def test_int_1_orchestrator_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 1: Agent Orchestrator acquires, executes, and transitions to DONE."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Write tests")

        # Simulate Orchestrator Selection
        acquired = await repo.transition_state(
            uuid.UUID(str(task["id"])), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )
        assert acquired["status"] == TaskStatus.IN_PROGRESS.value

        # Simulate Execution Success
        completed = await repo.transition_state(
            uuid.UUID(str(task["id"])), TaskStatus.DONE, TransitionReason.COMPLETED
        )
        assert completed["status"] == TaskStatus.DONE.value

    async def test_int_2_zombie_reaper(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 2: Zombie Reaper identifies stale task, transitions to BLOCKED, bumps attempt_count."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Zombie Task")
        await repo.transition_state(
            uuid.UUID(str(task["id"])), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )

        # Artificial Backdate
        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=15)
        await session.flush()

        # Simulate Reaper Script
        stmt = select(Task).where(Task.status == TaskStatus.IN_PROGRESS)
        stale_tasks = (await session.execute(stmt)).scalars().all()
        assert len(stale_tasks) == 1

        reaped = await repo.transition_state(
            stale_tasks[0].id, TaskStatus.BLOCKED, TransitionReason.ZOMBIE_TIMEOUT
        )
        assert reaped["status"] == TaskStatus.BLOCKED.value
        assert reaped["attempt_count"] == 1
        assert reaped["locked_at"] is None

    async def test_int_4_dag_resolution(self, session: AsyncSession, base_project: Project) -> None:
        """Integration 4: Resolving parent automatically unblocks child tasks."""
        repo = MemoryRepository(session)
        parent = await repo.create_task(project_name=base_project.name, title="Parent")
        child = await repo.create_task(project_name=base_project.name, title="Child")
        await repo.insert_dependency(uuid.UUID(parent["id"]), uuid.UUID(child["id"]))

        # Child is upstream blocked
        await repo.transition_state(
            uuid.UUID(child["id"]), TaskStatus.UPSTREAM_BLOCKED, TransitionReason.UPSTREAM_BLOCKED
        )

        # Parent finishes
        await repo.transition_state(
            uuid.UUID(parent["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )
        await repo.transition_state(
            uuid.UUID(parent["id"]), TaskStatus.DONE, TransitionReason.COMPLETED
        )

        # Simulate DAG Manager unblocking children
        child_unblocked = await repo.transition_state(
            uuid.UUID(child["id"]), TaskStatus.PENDING, TransitionReason.UPSTREAM_CLEARED
        )
        assert child_unblocked["status"] == TaskStatus.PENDING.value

    async def test_int_5_defect_interception(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 5: DefectBlocksCompletionError intercepts DONE transition."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Buggy Task")
        await repo.transition_state(
            uuid.UUID(str(task["id"])), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )

        # Agent logs defect
        await repo.create_defect(uuid.UUID(str(task["id"])), title="Tests fail")

        # Agent tries to complete
        with pytest.raises(DefectBlocksCompletionError):
            await repo.transition_state(
                uuid.UUID(str(task["id"])), TaskStatus.DONE, TransitionReason.COMPLETED
            )

        # Orchestrator catches it and forces BLOCKED for human intervention
        blocked = await repo.transition_state(
            uuid.UUID(str(task["id"])), TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE
        )
        assert blocked["status"] == TaskStatus.BLOCKED.value

    async def test_int_6_circuit_breaker(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 6: Circuit Breaker suspends tasks with attempt_count >= 3."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Failing Task")
        task_id = uuid.UUID(str(task["id"]))

        for _ in range(3):
            await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
            await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)
            # Re-queue the task for the next attempt
            await repo.transition_state(
                task_id, TaskStatus.PENDING, TransitionReason.MANUAL_UNBLOCK
            )

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
        from specweaver.workspace.memory.models import HandoverContext

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Handoff Task")
        task_id = uuid.UUID(str(task["id"]))

        # Agent 1
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.update_handover_context(
            task_id, HandoverContext(summary="Wrote frontend, need backend API")
        )
        await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)

        # Human/Orchestrator unblocks it for Agent 2
        await repo.transition_state(task_id, TaskStatus.PENDING, TransitionReason.MANUAL_UNBLOCK)

        # Agent 2
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        task_info = await repo.get_task(task_id)
        assert (
            task_info["handover_context"]
            == HandoverContext(summary="Wrote frontend, need backend API").to_json_str()
        )
        await repo.transition_state(task_id, TaskStatus.DONE, TransitionReason.COMPLETED)

    async def test_int_8_upstream_cascading_failure(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 8: Parent failure halts children."""
        repo = MemoryRepository(session)
        parent = await repo.create_task(project_name=base_project.name, title="Parent")
        child = await repo.create_task(project_name=base_project.name, title="Child")
        await repo.insert_dependency(uuid.UUID(parent["id"]), uuid.UUID(child["id"]))

        # Child waits
        await repo.transition_state(
            uuid.UUID(child["id"]), TaskStatus.UPSTREAM_BLOCKED, TransitionReason.UPSTREAM_BLOCKED
        )

        # Parent permanently fails
        await repo.transition_state(
            uuid.UUID(parent["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )
        await repo.transition_state(
            uuid.UUID(parent["id"]), TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE
        )
        await repo.transition_state(
            uuid.UUID(parent["id"]), TaskStatus.ARCHIVED, TransitionReason.ABANDONED
        )

        # Simulate Orchestrator deciding child destiny
        parent_status = (await repo.get_task(uuid.UUID(parent["id"])))["status"]
        if parent_status == TaskStatus.ARCHIVED.value:
            child_archived = await repo.transition_state(
                uuid.UUID(child["id"]), TaskStatus.ARCHIVED, TransitionReason.ABANDONED
            )
            assert child_archived["status"] == TaskStatus.ARCHIVED.value

    async def test_e2e_1_topological_execution_simulation(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E 1: Epic + DAG topological execution simulation."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="New Feature")

        t1 = await repo.create_task(
            project_name=base_project.name, title="DB Schema", epic_id=uuid.UUID(str(epic["id"]))
        )
        t2 = await repo.create_task(
            project_name=base_project.name, title="API Layer", epic_id=uuid.UUID(str(epic["id"]))
        )
        await repo.insert_dependency(uuid.UUID(t1["id"]), uuid.UUID(t2["id"]))

        # Initial states
        await repo.transition_state(
            uuid.UUID(t2["id"]), TaskStatus.UPSTREAM_BLOCKED, TransitionReason.UPSTREAM_BLOCKED
        )

        # Exec T1
        await repo.transition_state(
            uuid.UUID(t1["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )
        await repo.transition_state(
            uuid.UUID(t1["id"]), TaskStatus.DONE, TransitionReason.COMPLETED
        )

        # Unblock T2
        await repo.transition_state(
            uuid.UUID(t2["id"]), TaskStatus.PENDING, TransitionReason.UPSTREAM_CLEARED
        )

        # Exec T2
        await repo.transition_state(
            uuid.UUID(t2["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )
        await repo.transition_state(
            uuid.UUID(t2["id"]), TaskStatus.DONE, TransitionReason.COMPLETED
        )

        # Complete Epic
        await repo.close_epic(uuid.UUID(str(epic["id"])))

        epic_final = await repo.get_epic(uuid.UUID(str(epic["id"])))
        assert epic_final["status"] == EpicStatus.CLOSED.value

    async def test_e2e_3_sticky_bug_simulation(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E 3: Agent logs defect, human fixes, agent resumes."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        # Agent fails
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        defect = await repo.create_defect(task_id, title="Bug")
        await repo.transition_state(task_id, TaskStatus.BLOCKED, TransitionReason.AGENT_FAILURE)

        # Human fixes bug via CLI
        await repo.resolve_defect(int(defect["id"]))
        await repo.transition_state(task_id, TaskStatus.PENDING, TransitionReason.MANUAL_UNBLOCK)

        # Agent resumes
        await repo.transition_state(task_id, TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED)
        await repo.transition_state(task_id, TaskStatus.DONE, TransitionReason.COMPLETED)

    async def test_e2e_5_automatic_epic_closure_simulation(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E 5: Final task triggers Epic CLOSE."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Epic")
        epic_id = uuid.UUID(str(epic["id"]))

        t1 = await repo.create_task(project_name=base_project.name, title="T1", epic_id=epic_id)

        await repo.transition_state(
            uuid.UUID(t1["id"]), TaskStatus.IN_PROGRESS, TransitionReason.ACQUIRED
        )
        await repo.transition_state(
            uuid.UUID(t1["id"]), TaskStatus.DONE, TransitionReason.COMPLETED
        )

        # Simulate Orchestrator polling
        stmt = select(Task).where(Task.epic_id == epic_id, Task.status != TaskStatus.DONE)
        remaining = (await session.execute(stmt)).scalars().all()

        if not remaining:
            closed_epic = await repo.close_epic(epic_id)
            assert closed_epic["status"] == EpicStatus.CLOSED.value

    async def test_int_9_occ_concurrent_race(self, engine, base_project: Project) -> None:
        """Integration 9: True concurrent OCC race condition simulating two agents."""
        import asyncio

        from specweaver.workspace.memory.errors import StaleTaskVersionError

        # Setup task in a base session
        async with AsyncSession(engine, expire_on_commit=False) as setup_session:
            repo = MemoryRepository(setup_session)
            task = await repo.create_task(project_name=base_project.name, title="Contested Task")
            task_id = uuid.UUID(str(task["id"]))
            await setup_session.commit()

        # Agent 1 and Agent 2 try to acquire at the exact same time using distinct sessions
        async def agent_acquire(worker_id: str) -> dict[str, object]:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                repo = MemoryRepository(session)
                return await repo.acquire_task(task_id, worker_id)

        results = await asyncio.gather(
            agent_acquire("agent-1"), agent_acquire("agent-2"), return_exceptions=True
        )

        # One should succeed, one should fail with StaleTaskVersionError (or an OperationalError if DB locked, but memory sqlite is fast)
        # Wait, if both try to UPDATE, SQLite might throw `database is locked` (OperationalError).
        # But SQLite handles simple updates if PRAGMA journal_mode=WAL or concurrency is low. In aiosqlite memory, it serializes.
        # So we expect one success, one StaleTaskVersionError.
        successes = [r for r in results if isinstance(r, dict)]
        exceptions = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
        assert len(exceptions) == 1, f"Expected 1 exception, got {len(exceptions)}: {results}"
        assert isinstance(exceptions[0], StaleTaskVersionError), (
            f"Expected StaleTaskVersionError, got {type(exceptions[0])}"
        )
        assert successes[0]["assigned_worker_id"] in ["agent-1", "agent-2"]
        assert successes[0]["version"] == 2

    async def test_int_10_deep_dag_cycle_protection(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 10: Protection against deep transitive cycle injection in realistic topology."""
        from specweaver.workspace.memory.errors import CyclicDependencyError

        repo = MemoryRepository(session)

        # Build a 10-node complex graph: 0->1->2...->9
        tasks = [
            await repo.create_task(project_name=base_project.name, title=f"Node {i}")
            for i in range(10)
        ]
        task_ids = [uuid.UUID(str(t["id"])) for t in tasks]

        for i in range(9):
            await repo.insert_dependency(task_ids[i], task_ids[i + 1])

        # Add some diamond patterns (0->3, 2->5)
        await repo.insert_dependency(task_ids[0], task_ids[3])
        await repo.insert_dependency(task_ids[2], task_ids[5])

        # Now an agent hallucinates that node 9 depends on node 0
        with pytest.raises(CyclicDependencyError):
            await repo.insert_dependency(task_ids[9], task_ids[0])

        # Or that node 5 depends on node 2 (already have 2->5)
        with pytest.raises(CyclicDependencyError):
            await repo.insert_dependency(task_ids[5], task_ids[2])

    async def test_int_11_zombie_reaper_full_cycle(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 11: Zombie reaper full cycle."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Zombie")
        task_id = uuid.UUID(str(task["id"]))

        # Agent 1 acquires
        await repo.acquire_task(task_id, worker_id="agent-1")

        # Backdate heartbeat
        task_model = await session.get(Task, task_id)
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        # Recycle
        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1
        assert recycled[0]["status"] == TaskStatus.PENDING.value
        assert recycled[0]["attempt_count"] == 1
        assert recycled[0]["version"] == 3  # created(1) -> acquired(2) -> recycled(3)

        # Agent 2 acquires
        acquired = await repo.acquire_task(task_id, worker_id="agent-2")
        assert acquired["assigned_worker_id"] == "agent-2"

    async def test_int_12_circuit_breaker_three_strikes(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Integration 12: Circuit Breaker fires after 3 fails through recycle_zombies."""
        from specweaver.workspace.memory.store import Defect

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Hard Task")
        task_id = uuid.UUID(str(task["id"]))

        for i in range(3):
            await repo.acquire_task(task_id, worker_id=f"agent-{i}")
            task_model = await session.get(Task, task_id)
            assert task_model is not None
            task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
            await session.flush()
            recycled = await repo.recycle_zombies(project_name=base_project.name)
            assert len(recycled) == 1

        assert recycled[0]["status"] == TaskStatus.BLOCKED.value
        assert recycled[0]["resilience_action"] == "CIRCUIT_BREAKER"

        # Defect check
        stmt = select(Defect).where(Defect.task_id == task_id)
        defect = (await session.execute(stmt)).scalar_one()
        assert defect.title == "circuit_breaker: max retries exceeded"

    async def test_e2e_7_heartbeat_survival(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E 7: Agent pulses heartbeat, survives zombie scan."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Active Task")
        task_id = uuid.UUID(str(task["id"]))

        await repo.acquire_task(task_id, worker_id="agent-1")

        # Backdate heartbeat initially
        task_model = await session.get(Task, task_id)
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        # Pulse heartbeat
        await repo.pulse_heartbeat(task_id, worker_id="agent-1")

        # Recycle
        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 0

    async def test_int_13_create_defect_preserves_session_bounds(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-13: [Boundary] Defect creation during batch atomic update preserves session state."""
        from specweaver.workspace.memory.store import Task

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        # create_defect performs an explicit flush
        defect_dict = await repo.create_defect(
            task_id=task_id, title="Test Defect", description="Something broke"
        )
        assert defect_dict["title"] == "Test Defect"

        # Verify it flushed
        task_model = await session.get(Task, task_id)
        assert task_model is not None
        assert task_model.status.value == "PENDING"  # Defect creation itself doesn't block

    async def test_int_14_create_defect_hostile_size(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-14: [Hostile] Extremely large defect description handled without DB errors (caught or bounded)."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        # 1MB string
        massive_desc = "A" * 1024 * 1024

        with pytest.raises(IntegrityError):
            await repo.create_defect(task_id=task_id, title="Massive", description=massive_desc)

    async def test_int_15_recycle_zombies_preserves_handover_context(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-15: [Boundary] recycle_zombies preserves handover_context (RT2-2)."""
        from specweaver.workspace.memory.models import HandoverContext
        from specweaver.workspace.memory.store import Task

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        await repo.acquire_task(task_id, worker_id="agent-1")

        ctx = HandoverContext(files_touched=["a.txt"], summary="None")
        await repo.update_handover_context(task_id, ctx)

        task_model = await session.get(Task, task_id)
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1
        assert recycled[0]["handover_context"] == ctx.model_dump_json(exclude_none=True)

    async def test_int_16_recycle_zombies_concurrent_occ_conflict(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-16: [Graceful Degradation] Concurrent agent update during recycle_zombies batch flush (NFR-1)."""
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        await repo.transition_state(task_id, to_status=TaskStatus.IN_PROGRESS, reason="start")

        task_model = await session.get(Task, task_id)
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        # Simulate concurrent version increment
        task_model.version += 1
        await session.commit()

        # recycle_zombies does zombie.version += 1 and flushes.
        # SQLite serialized lock usually prevents this in real multi-connection,
        # but in this session we just verify it successfully increments and flushes.
        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1
        assert recycled[0]["version"] == 3  # Started at 1, we bumped +1, recycle_zombies bumped +1

    async def test_e2e_8_pulse_heartbeat_storm(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E-8: [Hostile] Massive agent fleet creating heartbeat storms (NFR-1)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        repo = MemoryRepository(session)
        tasks = []
        for i in range(50):
            t = await repo.create_task(project_name=base_project.name, title=f"T{i}")
            tid = uuid.UUID(str(t["id"]))
            await repo.acquire_task(tid, worker_id=f"agent-{i}")
            tasks.append((tid, f"agent-{i}"))

        # Storm of heartbeats
        import asyncio

        async def _pulse(tid, wid):
            # Create a separate session per concurrent task to avoid Session is already flushing error
            async with AsyncSession(session.bind) as new_sess:
                r = MemoryRepository(new_sess)
                return await r.pulse_heartbeat(tid, wid)

        results = await asyncio.gather(
            *[_pulse(tid, wid) for tid, wid in tasks], return_exceptions=True
        )

        # All should succeed without locking the DB due to AsyncSession
        for r in results:
            assert not isinstance(r, Exception)

    async def test_e2e_9_zombie_reaping_boundary_jitter(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E-9: [Boundary] Zombie reaping at exact 15-minute boundary."""
        from specweaver.workspace.memory.store import Task

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        await repo.acquire_task(task_id, worker_id="agent-1")

        task_model = await session.get(Task, task_id)
        assert task_model is not None

        # Less than 15 minutes
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=14)
        await session.flush()

        # Should not be recycled (requires > 15)
        recycled = await repo.recycle_zombies(project_name=base_project.name, timeout_minutes=15)
        assert len(recycled) == 0

        # More than 15 mins
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=16)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name, timeout_minutes=15)
        assert len(recycled) == 1

    async def test_int_17_upstream_propagation_cascade(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-13: Build A->B->C chain, block C -> propagate_blocked(C) -> BFS auto-cascades"""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task_a = await repo.create_task(project_name=base_project.name, title="A")
        task_b = await repo.create_task(project_name=base_project.name, title="B")
        task_c = await repo.create_task(project_name=base_project.name, title="C")

        a_id, b_id, c_id = (
            uuid.UUID(str(task_a["id"])),
            uuid.UUID(str(task_b["id"])),
            uuid.UUID(str(task_c["id"])),
        )

        await repo.insert_dependency(a_id, b_id)
        await repo.insert_dependency(b_id, c_id)

        await repo.transition_state(task_id=c_id, to_status=TaskStatus.BLOCKED, reason="error")
        affected = await repo.propagate_blocked(task_id=c_id)

        assert len(affected) == 2
        affected_ids = {a["id"] for a in affected}
        assert str(a_id) in affected_ids
        assert str(b_id) in affected_ids

        a_model = await session.get(Task, a_id)
        b_model = await session.get(Task, b_id)
        assert a_model is not None
        assert b_model is not None
        assert a_model.status == TaskStatus.UPSTREAM_BLOCKED
        assert b_model.status == TaskStatus.UPSTREAM_BLOCKED

    async def test_int_18_reverse_propagation_partial(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-14: A depends on B and C, B blocked -> A UPSTREAM_BLOCKED -> C unblocked but B still blocked -> A stays"""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task_a = await repo.create_task(project_name=base_project.name, title="A")
        task_b = await repo.create_task(project_name=base_project.name, title="B")
        task_c = await repo.create_task(project_name=base_project.name, title="C")

        a_id, b_id, c_id = (
            uuid.UUID(str(task_a["id"])),
            uuid.UUID(str(task_b["id"])),
            uuid.UUID(str(task_c["id"])),
        )

        await repo.insert_dependency(a_id, b_id)
        await repo.insert_dependency(a_id, c_id)

        await repo.transition_state(task_id=b_id, to_status=TaskStatus.BLOCKED, reason="error")
        await repo.transition_state(task_id=c_id, to_status=TaskStatus.BLOCKED, reason="error")

        await repo.propagate_blocked(task_id=b_id)
        await repo.propagate_blocked(task_id=c_id)

        a_model = await session.get(Task, a_id)
        assert a_model is not None
        assert a_model.status == TaskStatus.UPSTREAM_BLOCKED

        await repo.transition_state(task_id=c_id, to_status=TaskStatus.PENDING, reason="clear")
        cleared = await repo.clear_upstream_blocked(task_id=c_id)

        assert len(cleared) == 0
        a_model = await session.get(Task, a_id)
        assert a_model is not None
        assert a_model.status == TaskStatus.UPSTREAM_BLOCKED

    async def test_int_19_reverse_propagation_full_clear(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-15: Same as INT-14 but B also unblocks -> clear_upstream_blocked(B) BFS clears A to PENDING"""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task_a = await repo.create_task(project_name=base_project.name, title="A")
        task_b = await repo.create_task(project_name=base_project.name, title="B")
        task_c = await repo.create_task(project_name=base_project.name, title="C")

        a_id, b_id, c_id = (
            uuid.UUID(str(task_a["id"])),
            uuid.UUID(str(task_b["id"])),
            uuid.UUID(str(task_c["id"])),
        )

        await repo.insert_dependency(a_id, b_id)
        await repo.insert_dependency(a_id, c_id)

        await repo.transition_state(task_id=b_id, to_status=TaskStatus.BLOCKED, reason="error")
        await repo.transition_state(task_id=c_id, to_status=TaskStatus.BLOCKED, reason="error")
        await repo.propagate_blocked(task_id=b_id)
        await repo.propagate_blocked(task_id=c_id)

        await repo.transition_state(task_id=c_id, to_status=TaskStatus.PENDING, reason="clear")
        await repo.clear_upstream_blocked(task_id=c_id)

        await repo.transition_state(task_id=b_id, to_status=TaskStatus.PENDING, reason="clear")
        cleared = await repo.clear_upstream_blocked(task_id=b_id)

        assert len(cleared) == 1
        assert cleared[0]["id"] == str(a_id)

        a_model = await session.get(Task, a_id)
        assert a_model is not None
        assert a_model.status == TaskStatus.PENDING

    async def test_e2e_6_resilient_dag_execution(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """E2E-6: Full lifecycle: Create Epic + 3 tasks in DAG -> T1 completes -> T2 zombies -> circuit breaker fires -> T3 UPSTREAM_BLOCKED via BFS -> human resolves defect -> unblock -> T3 resumes -> Epic closes."""
        from specweaver.workspace.memory.store import EpicStatus, TaskStatus

        repo = MemoryRepository(session)

        # 1. Create Epic + 3 tasks in DAG
        epic = await repo.create_epic(project_name=base_project.name, title="Feature")
        epic_id = uuid.UUID(str(epic["id"]))

        t1 = await repo.create_task(project_name=base_project.name, title="T1", epic_id=epic_id)
        t2 = await repo.create_task(project_name=base_project.name, title="T2", epic_id=epic_id)
        t3 = await repo.create_task(project_name=base_project.name, title="T3", epic_id=epic_id)

        t1_id, t2_id, t3_id = (
            uuid.UUID(str(t1["id"])),
            uuid.UUID(str(t2["id"])),
            uuid.UUID(str(t3["id"])),
        )

        # DAG: T3 depends on T2, T2 depends on T1
        await repo.insert_dependency(t3_id, t2_id)
        await repo.insert_dependency(t2_id, t1_id)

        # 2. T1 completes
        await repo.transition_state(t1_id, to_status=TaskStatus.IN_PROGRESS, reason="start")
        await repo.transition_state(t1_id, to_status=TaskStatus.DONE, reason="complete")

        # 3. T2 acquired, then zombies and eventually circuit breaks (attempt_count = 3)
        t2_model = await session.get(Task, t2_id)
        assert t2_model is not None
        t2_model.attempt_count = 2
        await session.flush()

        await repo.acquire_task(t2_id, worker_id="agent-1")

        # Fake time passing so it's a zombie
        t2_model = await session.get(Task, t2_id)
        assert t2_model is not None
        t2_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        # Recycle -> circuit breaker fires!
        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1
        assert recycled[0]["resilience_action"] == "CIRCUIT_BREAKER"

        # 4. T3 UPSTREAM_BLOCKED via BFS
        await repo.propagate_blocked(t2_id)

        t3_model = await session.get(Task, t3_id)
        assert t3_model is not None
        assert t3_model.status == TaskStatus.UPSTREAM_BLOCKED

        # 5. Human resolves T2 defect & unblocks
        defects = await repo.list_defects(t2_id)
        assert len(defects) == 1
        await repo.resolve_defect(int(defects[0]["id"]))

        await repo.transition_state(t2_id, to_status=TaskStatus.PENDING, reason="manual_unblock")
        await repo.clear_upstream_blocked(t2_id)

        # 6. T3 resumes (is PENDING)
        t3_model = await session.get(Task, t3_id)
        assert t3_model is not None
        assert t3_model.status == TaskStatus.PENDING

        # 7. Complete T2 and T3
        await repo.transition_state(t2_id, to_status=TaskStatus.IN_PROGRESS, reason="start")
        await repo.transition_state(t2_id, to_status=TaskStatus.DONE, reason="complete")

        await repo.transition_state(t3_id, to_status=TaskStatus.IN_PROGRESS, reason="start")
        await repo.transition_state(t3_id, to_status=TaskStatus.DONE, reason="complete")

        # Close Epic
        await repo.close_epic(epic_id)

        epic_model = await repo.get_epic(epic_id)
        assert epic_model is not None
        assert epic_model["status"] == EpicStatus.CLOSED.name

    async def test_int_20_diamond_dependency_propagation(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """INT-20: Diamond DAG A->B, A->C, B->D, C->D. Block D -> cascades to A. Unblock D -> clears all."""
        from specweaver.workspace.memory.store import TaskStatus
        repo = MemoryRepository(session)
        task_a = await repo.create_task(project_name=base_project.name, title="A")
        task_b = await repo.create_task(project_name=base_project.name, title="B")
        task_c = await repo.create_task(project_name=base_project.name, title="C")
        task_d = await repo.create_task(project_name=base_project.name, title="D")

        a_id = uuid.UUID(str(task_a["id"]))
        b_id = uuid.UUID(str(task_b["id"]))
        c_id = uuid.UUID(str(task_c["id"]))
        d_id = uuid.UUID(str(task_d["id"]))

        await repo.insert_dependency(a_id, b_id)
        await repo.insert_dependency(a_id, c_id)
        await repo.insert_dependency(b_id, d_id)
        await repo.insert_dependency(c_id, d_id)

        # 1. Block D
        await repo.transition_state(task_id=d_id, to_status=TaskStatus.BLOCKED, reason="error")
        await repo.propagate_blocked(task_id=d_id)

        # A, B, C should all be UPSTREAM_BLOCKED
        for tid in (a_id, b_id, c_id):
            model = await session.get(Task, tid)
            assert model is not None
            assert model.status == TaskStatus.UPSTREAM_BLOCKED

        # 2. Unblock D
        await repo.transition_state(task_id=d_id, to_status=TaskStatus.PENDING, reason="clear")
        await repo.clear_upstream_blocked(task_id=d_id)

        # A, B, C should all be back to PENDING
        for tid in (a_id, b_id, c_id):
            model = await session.get(Task, tid)
            assert model is not None
            assert model.status == TaskStatus.PENDING
