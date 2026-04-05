# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for database schema migrations (v2-v7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temporary DB path (file does not exist yet)."""
    return tmp_path / ".specweaver" / "specweaver.db"


@pytest.fixture()
def db(db_path: Path):
    """Create a fresh database and return its Database instance."""
    from specweaver.config.database import Database

    return Database(db_path)


# ---------------------------------------------------------------------------
# Schema v2 migration — context_limit
# ---------------------------------------------------------------------------

# Schema v7 — auto_bootstrap_constitution
# ===========================================================================


class TestSchemaV7AutoBootstrap:
    """Tests for auto_bootstrap_constitution column and accessors."""

    def test_auto_bootstrap_default_is_prompt(self, db, tmp_path: Path):
        """Default auto_bootstrap_constitution is 'prompt'."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_auto_bootstrap("myapp") == "prompt"

    def test_set_auto_bootstrap_off(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "off")
        assert db.get_auto_bootstrap("myapp") == "off"

    def test_set_auto_bootstrap_auto(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "auto")
        assert db.get_auto_bootstrap("myapp") == "auto"

    def test_set_auto_bootstrap_prompt(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "off")
        db.set_auto_bootstrap("myapp", "prompt")
        assert db.get_auto_bootstrap("myapp") == "prompt"

    def test_set_auto_bootstrap_case_insensitive(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "AUTO")
        assert db.get_auto_bootstrap("myapp") == "auto"

    def test_set_auto_bootstrap_invalid_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"Invalid auto-bootstrap mode"):
            db.set_auto_bootstrap("myapp", "always")

    def test_get_auto_bootstrap_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match=r"not found"):
            db.get_auto_bootstrap("nonexistent")

    def test_set_auto_bootstrap_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match=r"not found"):
            db.set_auto_bootstrap("nonexistent", "off")

    def test_auto_bootstrap_persists_across_connections(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "auto")

        from specweaver.config.database import Database

        db2 = Database(db._db_path)
        assert db2.get_auto_bootstrap("myapp") == "auto"


class TestSchemaV6ToV7Upgrade:
    """Simulate opening a v6-only DB and verify v7 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v6_v7.db"

    def test_v6_to_v7_upgrade(self, db_path: Path):
        """Simulate a v6 DB and verify v7 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            Database,
        )

        # Create a v6-only DB manually (no v7 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (6, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size, domain_profile) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120, NULL)"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v7 migration
        db = Database(db_path)
        assert db.get_auto_bootstrap("legacy") == "prompt"  # default
        assert db.get_log_level("legacy") == "INFO"  # preserved
        assert db.get_constitution_max_size("legacy") == 5120  # preserved
        with db.connect() as conn2:
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version[0] >= 10


class TestSchemaV7ToV8Upgrade:
    """Simulate opening a v7-only DB and verify v8 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v7_v8.db"

    def test_v7_to_v8_upgrade(self, db_path: Path):
        """Simulate a v7 DB and verify v8 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (7, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size, domain_profile, auto_bootstrap_constitution) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120, NULL, 'prompt')"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v8 migration
        db = Database(db_path)
        assert db.get_stitch_mode("legacy") == "off"  # default from ALTER
        with db.connect() as conn2:
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version[0] >= 10


class TestSchemaV8ToV9Upgrade:
    """Simulate opening a v8-only DB and verify v9 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v8_v9.db"

    def test_v8_to_v9_upgrade(self, db_path: Path):
        """Simulate a v8 DB and verify v9 migration creates usage tables."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            _SCHEMA_V8,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.executescript(_SCHEMA_V8)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (8, '2026-01-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()

        db = Database(db_path)
        with db.connect() as conn2:
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()
            tables = conn2.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('llm_usage_log', 'llm_cost_overrides')"
            ).fetchall()
        assert version[0] >= 10
        table_names = {r[0] for r in tables}
        assert "llm_usage_log" in table_names
        assert "llm_cost_overrides" in table_names


class TestUsageLogCrud:
    """Tests for log_usage() and query methods."""

    def test_log_usage_insert(self, db):
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:00:00Z",
                "project_name": "proj",
                "task_type": "draft",
                "model": "gemini-3-flash-preview",
                "provider": "gemini",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "estimated_cost_usd": 0.0003,
                "duration_ms": 500,
                "run_id": "test-run-123",
            }
        )
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM llm_usage_log").fetchall()
        assert len(rows) == 1
        assert rows[0]["model"] == "gemini-3-flash-preview"
        assert rows[0]["run_id"] == "test-run-123"

    def test_log_usage_multiple_rows(self, db):
        for i in range(3):
            db.log_usage(
                {
                    "timestamp": f"2026-03-27T00:0{i}:00Z",
                    "project_name": "proj",
                    "task_type": "review",
                    "model": "model-x",
                    "provider": "p",
                }
            )
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM llm_usage_log").fetchone()[0]
        assert count == 3

    def test_get_usage_summary_all(self, db):
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "model-a",
                "provider": "x",
                "total_tokens": 100,
                "estimated_cost_usd": 0.01,
            }
        )
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:01:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "model-a",
                "provider": "x",
                "total_tokens": 200,
                "estimated_cost_usd": 0.02,
            }
        )
        result = db.get_usage_summary()
        assert len(result) == 1
        assert result[0]["call_count"] == 2
        assert result[0]["total_tokens"] == 300

    def test_get_usage_summary_filtered_by_project(self, db):
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
            }
        )
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:01:00Z",
                "project_name": "p2",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
            }
        )
        result = db.get_usage_summary(project="p1")
        assert len(result) == 1
        assert result[0]["call_count"] == 1

    def test_get_usage_by_task_type(self, db):
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
                "total_tokens": 100,
                "estimated_cost_usd": 0.01,
            }
        )
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:01:00Z",
                "project_name": "p1",
                "task_type": "review",
                "model": "m",
                "provider": "x",
                "total_tokens": 200,
                "estimated_cost_usd": 0.03,
            }
        )
        result = db.get_usage_by_task_type("p1")
        assert len(result) == 2
        types = {r["task_type"] for r in result}
        assert types == {"draft", "review"}

    def test_get_usage_summary_empty(self, db):
        assert db.get_usage_summary() == []


class TestCostOverrideCrud:
    """Tests for cost override CRUD methods."""

    def test_get_cost_overrides_empty(self, db):
        assert db.get_cost_overrides() == {}

    def test_set_and_get_override(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        overrides = db.get_cost_overrides()
        assert "gpt-4o" in overrides
        assert overrides["gpt-4o"] == (0.005, 0.015)

    def test_override_upsert(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        db.set_cost_override("gpt-4o", 0.010, 0.030)
        overrides = db.get_cost_overrides()
        assert overrides["gpt-4o"] == (0.010, 0.030)

    def test_delete_override(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        db.delete_cost_override("gpt-4o")
        assert db.get_cost_overrides() == {}

    def test_delete_nonexistent_is_noop(self, db):
        db.delete_cost_override("nonexistent")  # Should not raise

    def test_multiple_overrides(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        db.set_cost_override("claude-3", 0.003, 0.012)
        overrides = db.get_cost_overrides()
        assert len(overrides) == 2


# ---------------------------------------------------------------------------
# Stories 1, 20, 21: Usage log gap tests
# ---------------------------------------------------------------------------


class TestUsageLogGaps:
    """Additional DB mixin tests for uncovered scenarios."""

    @pytest.fixture()
    def db(self, tmp_path: Path):
        from specweaver.config.database import Database

        return Database(tmp_path / ".specweaver" / "specweaver.db")

    def test_get_usage_summary_since_filter(self, db):
        """Story 1: get_usage_summary filters by 'since' timestamp."""
        db.log_usage(
            {
                "timestamp": "2026-03-01T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
                "total_tokens": 100,
                "estimated_cost_usd": 0.01,
            }
        )
        db.log_usage(
            {
                "timestamp": "2026-03-20T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
                "total_tokens": 200,
                "estimated_cost_usd": 0.02,
            }
        )
        result = db.get_usage_summary(since="2026-03-15T00:00:00Z")
        assert len(result) == 1
        assert result[0]["call_count"] == 1
        assert result[0]["total_tokens"] == 200

    def test_get_usage_summary_combined_project_and_since(self, db):
        """Story 20: both project AND since filters applied together."""
        db.log_usage(
            {
                "timestamp": "2026-03-01T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
            }
        )
        db.log_usage(
            {
                "timestamp": "2026-03-20T00:00:00Z",
                "project_name": "p1",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
            }
        )
        db.log_usage(
            {
                "timestamp": "2026-03-20T00:00:00Z",
                "project_name": "p2",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
            }
        )

        result = db.get_usage_summary(project="p1", since="2026-03-15T00:00:00Z")
        assert len(result) == 1
        assert result[0]["call_count"] == 1  # Only p1 after cutoff

    def test_log_usage_missing_optional_keys_uses_defaults(self, db):
        """Story 21: log_usage with only required keys — optionals default to 0."""
        db.log_usage(
            {
                "timestamp": "2026-03-27T00:00:00Z",
                "project_name": "proj",
                "task_type": "draft",
                "model": "m",
                "provider": "x",
                # No prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, duration_ms, run_id
            }
        )
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM llm_usage_log").fetchone()
        assert row["prompt_tokens"] == 0
        assert row["completion_tokens"] == 0
        assert row["total_tokens"] == 0
        assert row["estimated_cost"] == 0.0
        assert row["duration_ms"] == 0
        assert row["run_id"] == ""


# ===========================================================================
# Schema v10 — provider column on llm_profiles
# ===========================================================================


class TestSchemaV10Migration:
    """Test the v9→v10 migration (provider column on llm_profiles)."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v9_v10.db"

    def test_provider_column_exists(self, db):
        """provider column is present on llm_profiles after migration."""
        with db.connect() as conn:
            row = conn.execute("SELECT provider FROM llm_profiles WHERE name='review'").fetchone()
        assert row is not None

    def test_provider_default_is_gemini(self, db):
        """Default provider on seed profiles is 'gemini'."""
        with db.connect() as conn:
            rows = conn.execute("SELECT provider FROM llm_profiles").fetchall()
        for row in rows:
            assert row[0] == "gemini"

    def test_create_profile_with_provider(self, db):
        """create_llm_profile accepts provider parameter."""
        profile_id = db.create_llm_profile(
            "openai-draft",
            model="gpt-4o",
            provider="openai",
        )
        profile = db.get_llm_profile(profile_id)
        assert profile["provider"] == "openai"

    def test_create_profile_provider_defaults_to_gemini(self, db):
        """create_llm_profile defaults provider to 'gemini'."""
        profile_id = db.create_llm_profile(
            "legacy-profile",
            model="gemini-2.0-flash",
        )
        profile = db.get_llm_profile(profile_id)
        assert profile["provider"] == "gemini"

    def test_default_profiles_include_provider(self, db):
        """Seed DEFAULT_PROFILES include provider='gemini' for all entries."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT name, provider FROM llm_profiles WHERE is_global = 1"
            ).fetchall()
        assert len(rows) >= 4
        for row in rows:
            assert row["provider"] == "gemini"

    def test_schema_version_is_latest(self, db):
        """Schema version is 14 after all migrations."""
        with db.connect() as conn:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row[0] == 14

    def test_v9_to_v10_upgrade(self, db_path: Path):
        """Simulate a v9 DB and verify v10 migration adds provider column."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            _SCHEMA_V8,
            _SCHEMA_V9,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.executescript(_SCHEMA_V8)
        conn.executescript(_SCHEMA_V9)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (9, '2026-01-01T00:00:00Z')"
        )
        # Insert a v9 profile (no provider column)
        conn.execute(
            "INSERT INTO llm_profiles "
            "(name, is_global, model, temperature, max_output_tokens, "
            "response_format, context_limit) "
            "VALUES ('review', 1, 'gemini-2.5-flash', 0.3, 4096, 'text', 128000)"
        )
        conn.commit()
        conn.close()

        db = Database(db_path)
        with db.connect() as conn2:
            row = conn2.execute("SELECT provider FROM llm_profiles WHERE name='review'").fetchone()
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()

        assert row[0] == "gemini"  # default from ALTER TABLE
        assert version[0] >= 10


class TestSchemaV11ToV12Upgrade:
    """Simulate opening a V11 DB and verify V12 migration adds model_id column."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v11_v12.db"

    def test_v11_to_v12_upgrade(self, db_path: Path):
        """Simulate a v11 DB and verify v12 migration adds model_id column with default."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            _SCHEMA_V8,
            _SCHEMA_V9,
            SCHEMA_V10,
            SCHEMA_V11,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.executescript(_SCHEMA_V8)
        conn.executescript(_SCHEMA_V9)
        conn.executescript(SCHEMA_V10)
        conn.executescript(SCHEMA_V11)

        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (11, '2026-01-01T00:00:00Z')"
        )

        # Insert a v11 artifact event (no model_id column)
        conn.execute(
            "INSERT INTO artifact_events "
            "(artifact_id, parent_id, run_id, event_type, timestamp) "
            "VALUES ('uuid-test-11', NULL, 'run-1', 'test_event', '2026-01-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()

        # Opening with Database will trigger migration to v12
        db = Database(db_path)
        with db.connect() as conn2:
            row = conn2.execute(
                "SELECT model_id FROM artifact_events WHERE artifact_id='uuid-test-11'"
            ).fetchone()
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()

        assert row[0] == "unknown"  # constraint default from ALTER TABLE
        assert version[0] >= 14
        
# ===========================================================================
# Schema v13 — default_dal column on projects
# ===========================================================================


class TestSchemaV13DefaultDal:
    """Tests for default_dal column and accessors."""

    def test_default_dal_default_is_dal_a(self, db, tmp_path: Path):
        """Default default_dal is 'DAL_A'."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_default_dal("myapp") == "DAL_A"

    def test_set_default_dal(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_default_dal("myapp", "DAL_C")
        assert db.get_default_dal("myapp") == "DAL_C"

    def test_get_default_dal_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match=r"not found"):
            db.get_default_dal("nonexistent")

    def test_set_default_dal_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match=r"not found"):
            db.set_default_dal("nonexistent", "DAL_B")


class TestSchemaV12ToV13Upgrade:
    """Simulate opening a V12 DB and verify V13 migration adds default_dal column."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v12_v13.db"

    def test_v12_to_v13_upgrade(self, db_path: Path):
        """Simulate a v12 DB and verify v13 migration adds default_dal column with DAL_A."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            _SCHEMA_V8,
            _SCHEMA_V9,
            SCHEMA_V10,
            SCHEMA_V11,
            SCHEMA_V12,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.executescript(_SCHEMA_V8)
        conn.executescript(_SCHEMA_V9)
        conn.executescript(SCHEMA_V10)
        conn.executescript(SCHEMA_V11)
        conn.executescript(SCHEMA_V12)

        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (12, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size, domain_profile, auto_bootstrap_constitution, stitch_mode) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120, NULL, 'prompt', 'off')"
        )
        conn.commit()
        conn.close()

        # Opening with Database will trigger migration to v13 (and v14)
        db = Database(db_path)
        with db.connect() as conn2:
            row = conn2.execute("SELECT default_dal FROM projects WHERE name='legacy'").fetchone()
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()

        assert row[0] == "DAL_A"  # constraint default from ALTER TABLE
        assert version[0] >= 14
