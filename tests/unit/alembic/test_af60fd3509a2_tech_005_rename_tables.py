import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest


@pytest.fixture
def migration() -> Any:
    """Load the migration module dynamically since it's not in a python package."""
    # specweaver/alembic/versions/af60fd3509a2_tech_005_rename_tables.py
    path = (
        Path(__file__).parent.parent.parent.parent
        / "alembic"
        / "versions"
        / "af60fd3509a2_tech_005_rename_tables.py"
    )
    spec = importlib.util.spec_from_file_location("af60fd3509a2", str(path))
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["af60fd3509a2"] = mod
    spec.loader.exec_module(mod)
    return mod


@patch("af60fd3509a2.op")
def test_upgrade_renames_tables_and_indexes(mock_op: MagicMock, migration: Any) -> None:
    # Mock op.f to just return the string format name (it's normally a naming convention formatter)
    mock_op.f.side_effect = lambda name: name

    migration.upgrade()

    # Verify table renames
    mock_op.rename_table.assert_has_calls(
        [
            call("projects", "workspace_projects"),
            call("active_state", "workspace_active_state"),
            call("project_standards", "workspace_project_standards"),
            call("artifact_events", "flow_artifact_events"),
            call("project_llm_links", "llm_project_links"),
        ],
        any_order=True,
    )

    # Verify dropping old indexes on the new table name
    mock_op.drop_index.assert_has_calls(
        [
            call("ix_artifact_events_artifact_id", table_name="flow_artifact_events"),
            call("ix_artifact_events_parent_id", table_name="flow_artifact_events"),
        ],
        any_order=True,
    )

    # Verify creating new indexes
    mock_op.create_index.assert_has_calls(
        [
            call(
                "ix_flow_artifact_events_artifact_id",
                "flow_artifact_events",
                ["artifact_id"],
                unique=False,
            ),
            call(
                "ix_flow_artifact_events_parent_id",
                "flow_artifact_events",
                ["parent_id"],
                unique=False,
            ),
        ],
        any_order=True,
    )


@patch("af60fd3509a2.op")
def test_downgrade_restores_schema(mock_op: MagicMock, migration: Any) -> None:
    mock_op.f.side_effect = lambda name: name

    migration.downgrade()

    # Verify dropping new indexes first (LIFO)
    mock_op.drop_index.assert_has_calls(
        [
            call("ix_flow_artifact_events_artifact_id", table_name="flow_artifact_events"),
            call("ix_flow_artifact_events_parent_id", table_name="flow_artifact_events"),
        ],
        any_order=True,
    )

    # Verify restoring table names
    mock_op.rename_table.assert_has_calls(
        [
            call("workspace_projects", "projects"),
            call("workspace_active_state", "active_state"),
            call("workspace_project_standards", "project_standards"),
            call("flow_artifact_events", "artifact_events"),
            call("llm_project_links", "project_llm_links"),
        ],
        any_order=True,
    )

    # Verify restoring old indexes on the old table name
    mock_op.create_index.assert_has_calls(
        [
            call(
                "ix_artifact_events_artifact_id",
                "artifact_events",
                ["artifact_id"],
                unique=False,
            ),
            call(
                "ix_artifact_events_parent_id",
                "artifact_events",
                ["parent_id"],
                unique=False,
            ),
        ],
        any_order=True,
    )


def test_live_sqlite_migration(migration: Any) -> None:
    """Execute the migration against a live in-memory SQLite database to verify native compatibility."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        # 1. Setup initial state
        conn.execute(text("CREATE TABLE projects (name TEXT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE active_state (key TEXT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE project_standards (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text("CREATE TABLE artifact_events (id INTEGER PRIMARY KEY, artifact_id TEXT, parent_id TEXT)")
        )
        conn.execute(text("CREATE TABLE project_llm_links (id INTEGER PRIMARY KEY)"))

        conn.execute(text("CREATE INDEX ix_artifact_events_artifact_id ON artifact_events (artifact_id)"))
        conn.execute(text("CREATE INDEX ix_artifact_events_parent_id ON artifact_events (parent_id)"))

        # Also test foreign key propagation for memory_epics (verifies RED-1.1 defense)
        conn.execute(text("PRAGMA foreign_keys=OFF;")) # Simulate Alembic default
        conn.execute(text("CREATE TABLE memory_epics (id INTEGER PRIMARY KEY, project_name TEXT REFERENCES projects(name))"))

        # 2. Run Upgrade
        ctx = MigrationContext.configure(conn)
        op_inst = Operations(ctx)

        with patch("af60fd3509a2.op", new=op_inst):
            migration.upgrade()

        # 3. Verify post-upgrade state
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        assert "workspace_projects" in tables
        assert "workspace_active_state" in tables
        assert "workspace_project_standards" in tables
        assert "flow_artifact_events" in tables
        assert "llm_project_links" in tables
        assert "projects" not in tables

        indexes = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'")).fetchall()]
        assert "ix_flow_artifact_events_artifact_id" in indexes
        assert "ix_flow_artifact_events_parent_id" in indexes
        assert "ix_artifact_events_artifact_id" not in indexes

        # Verify foreign key was automatically propagated by SQLite >= 3.26
        child_sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE name='memory_epics'")).scalar()
        assert isinstance(child_sql, str)
        assert "REFERENCES \"workspace_projects\"(name)" in child_sql or "REFERENCES workspace_projects" in child_sql or "REFERENCES `workspace_projects`" in child_sql or "REFERENCES projects" not in child_sql

        # 4. Run Downgrade
        with patch("af60fd3509a2.op", new=op_inst):
            migration.downgrade()

        # 5. Verify post-downgrade state
        tables = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
        assert "projects" in tables
        assert "workspace_projects" not in tables

        indexes = [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'")).fetchall()]
        assert "ix_artifact_events_artifact_id" in indexes
        assert "ix_flow_artifact_events_artifact_id" not in indexes
