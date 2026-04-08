# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

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


class TestSchemaV2Migration:
    """Test the v1→v2 schema migration (context_limit column)."""

    def test_context_limit_column_exists(self, db):
        """context_limit column is present after migration."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT context_limit FROM llm_profiles WHERE name='review'"
            ).fetchone()
        assert row is not None

    def test_context_limit_default_value(self, db):
        """Default context_limit is 128000."""
        with db.connect() as conn:
            rows = conn.execute("SELECT context_limit FROM llm_profiles").fetchall()
        for row in rows:
            assert row[0] == 128_000

    def test_v1_to_v2_upgrade(self, db_path: Path):
        """Simulate a v1 DB and verify v2 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import _SCHEMA_V1, Database

        # Create a v1-only DB manually (without v2 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (1, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO llm_profiles "
            "(name, is_global, model, temperature, max_output_tokens, response_format) "
            "VALUES ('review', 1, 'gemini-2.5-flash', 0.3, 4096, 'text')"
        )
        conn.commit()
        conn.close()

        # Now open with Database — should apply v2 migration
        db = Database(db_path)
        with db.connect() as conn2:
            row = conn2.execute(
                "SELECT context_limit FROM llm_profiles WHERE name='review'"
            ).fetchone()
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()

        assert row[0] == 128_000  # default from ALTER TABLE
        assert version[0] >= 10  # V2, V3, V4, V5, V6, V7, V8 all applied

    def test_idempotent_v2_migration(self, db_path: Path):
        """Running Database() twice doesn't fail on duplicate ALTER TABLE."""
        from specweaver.config.database import Database

        Database(db_path)
        db2 = Database(db_path)  # should not raise
        with db2.connect() as conn:
            version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version[0] >= 10  # V2, V3, V4, V5, V6, V7, V8 all applied


# ---------------------------------------------------------------------------
# Validation Override UPSERT edge cases
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Schema v3 migration — log_level column
# ---------------------------------------------------------------------------


class TestSchemaV3Migration:
    """Test the v2→v3 schema migration (log_level column on projects)."""

    def test_log_level_column_exists(self, db, tmp_path: Path):
        """log_level column is present after migration."""
        db.register_project("myapp", str(tmp_path))
        with db.connect() as conn:
            row = conn.execute("SELECT log_level FROM projects WHERE name='myapp'").fetchone()
        assert row is not None

    def test_log_level_default_is_debug(self, db, tmp_path: Path):
        """Default log_level is DEBUG."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_log_level("myapp") == "DEBUG"

    def test_get_log_level_nonexistent_project_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.get_log_level("nonexistent")

    def test_set_log_level(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_log_level("myapp", "WARNING")
        assert db.get_log_level("myapp") == "WARNING"

    def test_set_log_level_case_insensitive(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_log_level("myapp", "info")
        assert db.get_log_level("myapp") == "INFO"

    def test_set_log_level_invalid_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match="Invalid log level"):
            db.set_log_level("myapp", "VERBOSE")

    def test_set_log_level_nonexistent_project_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.set_log_level("nonexistent", "DEBUG")

    def test_all_valid_levels(self, db, tmp_path: Path):
        """All 5 standard levels can be set and retrieved."""
        db.register_project("myapp", str(tmp_path))
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            db.set_log_level("myapp", level)
            assert db.get_log_level("myapp") == level

    def test_v2_to_v3_upgrade(self, db_path: Path):
        """Simulate a v2 DB and verify v3 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import _SCHEMA_V1, _SCHEMA_V2, Database

        # Create a v2-only DB manually
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (2, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v3 migration
        db = Database(db_path)
        assert db.get_log_level("legacy") == "DEBUG"  # default from ALTER
        with db.connect() as conn2:
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version[0] >= 10  # v3, v4, v5, v6, v7, v8 all applied


# ---------------------------------------------------------------------------
# Schema v4 migration — constitution_max_size column
# ---------------------------------------------------------------------------


class TestSchemaV4Migration:
    """Test the v3→v4 schema migration (constitution_max_size on projects)."""

    def test_constitution_max_size_column_exists(self, db, tmp_path: Path):
        """constitution_max_size column is present after migration."""
        db.register_project("myapp", str(tmp_path))
        with db.connect() as conn:
            row = conn.execute(
                "SELECT constitution_max_size FROM projects WHERE name='myapp'"
            ).fetchone()
        assert row is not None

    def test_constitution_max_size_default_is_5120(self, db, tmp_path: Path):
        """Default constitution_max_size is 5120 (5 KB)."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_constitution_max_size("myapp") == 5120

    def test_get_constitution_max_size_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.get_constitution_max_size("nonexistent")

    def test_set_constitution_max_size(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_constitution_max_size("myapp", 8192)
        assert db.get_constitution_max_size("myapp") == 8192

    def test_set_constitution_max_size_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.set_constitution_max_size("nonexistent", 8192)

    def test_set_constitution_max_size_zero_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Ii]nvalid.*size|must be positive"):
            db.set_constitution_max_size("myapp", 0)

    def test_schema_version_is_4(self, db):
        """Schema version is at least 4 after v4 migration (v5 also applied)."""
        with db.connect() as conn:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            assert row[0] >= 4

    def test_set_constitution_max_size_negative_raises(self, db, tmp_path: Path):
        """Negative constitution_max_size is rejected."""
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Ii]nvalid.*size|must be positive"):
            db.set_constitution_max_size("myapp", -100)

    def test_set_constitution_max_size_to_one(self, db, tmp_path: Path):
        """Setting constitution_max_size to 1 succeeds (minimum valid)."""
        db.register_project("myapp", str(tmp_path))
        db.set_constitution_max_size("myapp", 1)
        assert db.get_constitution_max_size("myapp") == 1

    def test_constitution_max_size_persists_across_connections(self, db, tmp_path: Path):
        """constitution_max_size value survives reconnection."""
        db.register_project("myapp", str(tmp_path))
        db.set_constitution_max_size("myapp", 10240)

        # Re-open database (simulates restart)
        from specweaver.config.database import Database

        db2 = Database(db._db_path)
        assert db2.get_constitution_max_size("myapp") == 10240


class TestSchemaV3ToV4Upgrade:
    """Simulate opening a v3-only DB and verify v4 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v3_v4.db"

    def test_v3_to_v4_upgrade(self, db_path: Path):
        """Simulate a v3 DB and verify v4 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            Database,
        )

        # Create a v3-only DB manually (no v4 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (3, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, log_level) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', 'INFO')"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v4 migration
        db = Database(db_path)
        assert db.get_constitution_max_size("legacy") == 5120  # default from ALTER
        assert db.get_log_level("legacy") == "INFO"  # preserved from v3
        with db.connect() as conn2:
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version[0] >= 10  # v4, v5, v6, v7, v8 all applied


# ===========================================================================
# Domain Profile Methods (Feature 3.3)
# ===========================================================================


class TestDomainProfile:
    """Tests for domain profile storage and application."""

    def test_get_domain_profile_default_is_none(self, db, tmp_path: Path):
        """New project has no domain profile set."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_domain_profile("myapp") is None

    def test_set_and_get_domain_profile(self, db, tmp_path: Path):
        """Setting a profile stores the name."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        assert db.get_domain_profile("myapp") == "web-app"

    def test_set_domain_profile_overwrites_previous(self, db, tmp_path: Path):
        """Setting a new profile replaces the previous one."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.set_domain_profile("myapp", "library")
        assert db.get_domain_profile("myapp") == "library"

    def test_clear_domain_profile(self, db, tmp_path: Path):
        """Clearing the profile resets to None."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.clear_domain_profile("myapp")
        assert db.get_domain_profile("myapp") is None

    def test_set_domain_profile_unknown_raises(self, db, tmp_path: Path):
        """Setting an unknown profile name raises ValueError."""
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Uu]nknown.*profile"):
            db.set_domain_profile("myapp", "quantum-computing")

    def test_set_domain_profile_unregistered_project_raises(self, db):
        """Setting a profile on an unregistered project raises ValueError."""
        with pytest.raises(ValueError, match=r"not found"):
            db.set_domain_profile("nonexistent", "web-app")

    def test_domain_profile_persists_across_connections(self, db, tmp_path: Path):
        """domain_profile value survives reconnection."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")

        from specweaver.config.database import Database

        db2 = Database(db._db_path)
        assert db2.get_domain_profile("myapp") == "data-pipeline"

    def test_get_domain_profile_unregistered_raises(self, db):
        """Getting profile on unregistered project raises ValueError."""
        with pytest.raises(ValueError, match=r"not found"):
            db.get_domain_profile("nonexistent")

    def test_clear_domain_profile_unregistered_raises(self, db):
        """Clearing profile on unregistered project raises ValueError."""
        with pytest.raises(ValueError, match=r"not found"):
            db.clear_domain_profile("nonexistent")

    def test_clear_domain_profile_idempotent(self, db, tmp_path: Path):
        """Clearing when no profile is set is idempotent (no error)."""
        db.register_project("myapp", str(tmp_path))
        db.clear_domain_profile("myapp")  # should not raise
        assert db.get_domain_profile("myapp") is None

    def test_set_domain_profile_case_insensitive(self, db, tmp_path: Path):
        """Profile name is accepted case-insensitively (stored normalised)."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "WEB-APP")
        # The profile is stored (case-insensitive lookup succeeded)
        assert db.get_domain_profile("myapp") == "WEB-APP"

    def test_schema_version_is_latest(self, db):
        """Schema version is 9 after all migrations."""
        with db.connect() as conn:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            assert row[0] >= 10


class TestSchemaV4ToV5Upgrade:
    """Simulate opening a v4-only DB and verify v5 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v4_v5.db"

    def test_v4_to_v5_upgrade(self, db_path: Path):
        """Simulate a v4 DB and verify v5 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            Database,
        )

        # Create a v4-only DB manually (no v5 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (4, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120)"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v5 migration
        db = Database(db_path)
        assert db.get_domain_profile("legacy") is None  # default
        assert db.get_constitution_max_size("legacy") == 5120  # preserved
        with db.connect() as conn2:
            version = conn2.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version[0] >= 10  # v5, v6, v7, v8 all applied


class TestSchemaV14Migration:
    """Test the v13→v14 schema migration (dropping validation_overrides)."""

    def test_validation_overrides_is_dropped(self, db):
        """After dropping, validation_overrides does not exist in sqlite_schema."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name='validation_overrides'"
            ).fetchone()
        assert row is None

    def test_schema_version_is_latest(self, db):
        """Schema version reaches 14."""
        with db.connect() as conn:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            assert row[0] >= 14
