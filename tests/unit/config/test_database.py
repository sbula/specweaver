# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for config/database.py — SQLite setup, schema, project CRUD, LLM profiles."""

from __future__ import annotations

from datetime import datetime
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
# Schema & initialization
# ---------------------------------------------------------------------------


class TestSchemaCreation:
    """Verify DB file, tables, WAL mode, and default seed data."""

    def test_db_file_created(self, db, db_path: Path):
        """Database file is created on disk."""
        assert db_path.exists()

    def test_parent_directory_created(self, db, db_path: Path):
        """Parent directory (.specweaver/) is created automatically."""
        assert db_path.parent.exists()

    def test_wal_mode_enabled(self, db):
        """SQLite WAL mode is enabled for concurrency."""
        with db.connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode == "wal"

    def test_foreign_keys_enabled(self, db):
        """Foreign keys are enforced."""
        with db.connect() as conn:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1

    def test_all_tables_exist(self, db):
        """All 5 required tables are created."""
        expected = {"projects", "llm_profiles", "project_llm_links",
                    "active_state", "schema_version"}
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            tables = {r[0] for r in rows}
        assert expected.issubset(tables)

    def test_schema_version_is_latest(self, db):
        """Schema version is 5 after v5 migration."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            assert row[0] == 5

    def test_default_llm_profiles_seeded(self, db):
        """Three global LLM profiles are seeded: review, draft, search."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT name, is_global FROM llm_profiles ORDER BY name"
            ).fetchall()
        names = [r[0] for r in rows]
        assert "draft" in names
        assert "review" in names
        assert "search" in names
        assert all(r[1] == 1 for r in rows)  # all global

    def test_review_profile_low_temperature(self, db):
        """Review profile has low temperature (0.3)."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT temperature FROM llm_profiles WHERE name='review'"
            ).fetchone()
        assert row[0] == pytest.approx(0.3)

    def test_draft_profile_higher_temperature(self, db):
        """Draft profile has higher temperature (0.7)."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT temperature FROM llm_profiles WHERE name='draft'"
            ).fetchone()
        assert row[0] == pytest.approx(0.7)

    def test_search_profile_lowest_temperature(self, db):
        """Search profile has lowest temperature (0.1)."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT temperature FROM llm_profiles WHERE name='search'"
            ).fetchone()
        assert row[0] == pytest.approx(0.1)

    def test_idempotent_initialization(self, db_path: Path):
        """Creating Database twice on same path does not duplicate data."""
        from specweaver.config.database import Database

        Database(db_path)  # already created by fixture
        db2 = Database(db_path)
        with db2.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM llm_profiles").fetchone()[0]
        assert count == 3  # not 6


# ---------------------------------------------------------------------------
# Project name validation
# ---------------------------------------------------------------------------


class TestProjectNameValidation:
    """Enforce ^[a-z0-9][a-z0-9_-]*$ for project names."""

    @pytest.mark.parametrize("name", [
        "myapp",
        "my-app",
        "my_app",
        "app123",
        "1st-project",
        "a",
    ])
    def test_valid_names(self, db, name: str):
        db.register_project(name, "/tmp/proj")

    @pytest.mark.parametrize("name,reason", [
        ("", "empty"),
        ("My-App", "uppercase"),
        ("my app", "space"),
        ("-leading-hyphen", "starts with hyphen"),
        ("_leading-underscore", "starts with underscore"),
        ("my.app", "dot"),
        ("my/app", "slash"),
        ("my@app", "at sign"),
        ("möbius", "non-ascii"),
    ])
    def test_invalid_names(self, db, name: str, reason: str):
        with pytest.raises(ValueError, match=r"[Ii]nvalid project name"):
            db.register_project(name, "/tmp/proj")


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


class TestProjectCRUD:
    """Register, get, list, update, remove projects."""

    def test_register_and_get(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        proj = db.get_project("myapp")
        assert proj is not None
        assert proj["name"] == "myapp"
        assert proj["root_path"] == str(tmp_path)

    def test_register_sets_timestamps(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        proj = db.get_project("myapp")
        created = datetime.fromisoformat(proj["created_at"])
        assert created.year >= 2026

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_project("nonexistent") is None

    def test_duplicate_name_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path / "a"))
        with pytest.raises(ValueError, match="already exists"):
            db.register_project("myapp", str(tmp_path / "b"))

    def test_duplicate_path_raises(self, db, tmp_path: Path):
        path = str(tmp_path / "shared")
        db.register_project("app1", path)
        with pytest.raises(ValueError, match="already registered"):
            db.register_project("app2", path)

    def test_list_projects_empty(self, db):
        assert db.list_projects() == []

    def test_list_projects_returns_all(self, db, tmp_path: Path):
        db.register_project("alpha", str(tmp_path / "a"))
        db.register_project("beta", str(tmp_path / "b"))
        projects = db.list_projects()
        names = [p["name"] for p in projects]
        assert "alpha" in names
        assert "beta" in names
        assert len(projects) == 2

    def test_remove_project(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.remove_project("myapp")
        assert db.get_project("myapp") is None

    def test_remove_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.remove_project("nonexistent")

    def test_update_path(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path / "old"))
        new_path = str(tmp_path / "new")
        db.update_project_path("myapp", new_path)
        proj = db.get_project("myapp")
        assert proj["root_path"] == new_path

    def test_update_path_nonexistent_raises(self, db, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            db.update_project_path("nonexistent", str(tmp_path))

    def test_update_path_to_existing_path_raises(self, db, tmp_path: Path):
        db.register_project("app1", str(tmp_path / "a"))
        db.register_project("app2", str(tmp_path / "b"))
        with pytest.raises(ValueError, match="already registered"):
            db.update_project_path("app2", str(tmp_path / "a"))


# ---------------------------------------------------------------------------
# Active project
# ---------------------------------------------------------------------------


class TestActiveProject:
    """Track the currently active project."""

    def test_no_active_project_initially(self, db):
        assert db.get_active_project() is None

    def test_set_and_get_active(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_active_project("myapp")
        assert db.get_active_project() == "myapp"

    def test_switch_active_project(self, db, tmp_path: Path):
        db.register_project("app1", str(tmp_path / "a"))
        db.register_project("app2", str(tmp_path / "b"))
        db.set_active_project("app1")
        db.set_active_project("app2")
        assert db.get_active_project() == "app2"

    def test_set_active_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.set_active_project("nonexistent")

    def test_remove_active_project_clears_state(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_active_project("myapp")
        db.remove_project("myapp")
        assert db.get_active_project() is None


# ---------------------------------------------------------------------------
# LLM Profiles
# ---------------------------------------------------------------------------


class TestLLMProfiles:
    """Global and project-specific LLM profile management."""

    def test_list_global_profiles(self, db):
        profiles = db.list_llm_profiles(global_only=True)
        names = [p["name"] for p in profiles]
        assert set(names) == {"review", "draft", "search"}

    def test_create_global_profile(self, db):
        db.create_llm_profile(
            name="code-gen",
            is_global=True,
            model="gemini-2.5-pro",
            temperature=0.5,
        )
        profiles = db.list_llm_profiles(global_only=True)
        names = [p["name"] for p in profiles]
        assert "code-gen" in names

    def test_create_project_specific_profile(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        profile_id = db.create_llm_profile(
            name="review",
            is_global=False,
            model="gemini-2.5-pro",
            temperature=0.1,
        )
        assert profile_id > 0

    def test_get_profile_by_id(self, db):
        profiles = db.list_llm_profiles(global_only=True)
        review = next(p for p in profiles if p["name"] == "review")
        fetched = db.get_llm_profile(review["id"])
        assert fetched["model"] == "gemini-2.5-flash"
        assert fetched["temperature"] == pytest.approx(0.3)

    def test_get_nonexistent_profile_returns_none(self, db):
        assert db.get_llm_profile(9999) is None


# ---------------------------------------------------------------------------
# Project-LLM Links
# ---------------------------------------------------------------------------


class TestProjectLLMLinks:
    """Link projects to LLM profiles by role."""

    def test_register_auto_links_defaults(self, db, tmp_path: Path):
        """Registering a project auto-links all global profiles."""
        db.register_project("myapp", str(tmp_path))
        links = db.get_project_llm_links("myapp")
        roles = {link["role"] for link in links}
        assert roles == {"review", "draft", "search"}

    def test_linked_profile_data_accessible(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        links = db.get_project_llm_links("myapp")
        review_link = next(lnk for lnk in links if lnk["role"] == "review")
        profile = db.get_llm_profile(review_link["profile_id"])
        assert profile["name"] == "review"
        assert profile["temperature"] == pytest.approx(0.3)

    def test_override_profile_for_role(self, db, tmp_path: Path):
        """Project can override a role to point to a different profile."""
        db.register_project("myapp", str(tmp_path))
        custom_id = db.create_llm_profile(
            name="review",
            is_global=False,
            model="gemini-2.5-pro",
            temperature=0.1,
        )
        db.link_project_profile("myapp", "review", custom_id)
        links = db.get_project_llm_links("myapp")
        review_link = next(lnk for lnk in links if lnk["role"] == "review")
        assert review_link["profile_id"] == custom_id

    def test_link_project_to_nonexistent_profile_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Pp]rofile.*not found"):
            db.link_project_profile("myapp", "review", 9999)

    def test_link_nonexistent_project_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.link_project_profile("nonexistent", "review", 1)

    def test_remove_project_cascades_links(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.remove_project("myapp")
        # Direct SQL check — links table should be empty for this project
        with db.connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM project_llm_links WHERE project_name='myapp'"
            ).fetchone()[0]
        assert count == 0

    def test_get_resolved_profile_for_role(self, db, tmp_path: Path):
        """Convenience: get the full profile for a project + role."""
        db.register_project("myapp", str(tmp_path))
        profile = db.get_project_profile("myapp", "review")
        assert profile is not None
        assert profile["name"] == "review"
        assert profile["temperature"] == pytest.approx(0.3)

    def test_get_resolved_profile_unlinked_role_returns_none(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        assert db.get_project_profile("myapp", "nonexistent-role") is None

    def test_add_custom_role(self, db, tmp_path: Path):
        """Projects can add new roles beyond the defaults."""
        db.register_project("myapp", str(tmp_path))
        custom_id = db.create_llm_profile(
            name="analysis",
            is_global=False,
            model="gemini-2.5-pro",
            temperature=0.2,
        )
        db.link_project_profile("myapp", "analysis", custom_id)
        profile = db.get_project_profile("myapp", "analysis")
        assert profile is not None
        assert profile["temperature"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Corner cases and error handling."""

    def test_concurrent_connections(self, db, tmp_path: Path):
        """WAL mode allows concurrent reads."""
        db.register_project("myapp", str(tmp_path))
        # Two separate connections reading simultaneously
        with db.connect() as conn1, db.connect() as conn2:
            r1 = conn1.execute("SELECT name FROM projects").fetchall()
            r2 = conn2.execute("SELECT name FROM projects").fetchall()
        assert len(r1) == len(r2) == 1

    def test_very_long_project_name(self, db, tmp_path: Path):
        """Long but valid names should work."""
        long_name = "a" * 200
        db.register_project(long_name, str(tmp_path))
        proj = db.get_project(long_name)
        assert proj["name"] == long_name

    def test_path_with_spaces(self, db, tmp_path: Path):
        """Paths with spaces are valid."""
        spaced_path = str(tmp_path / "my project folder")
        db.register_project("spaced", spaced_path)
        proj = db.get_project("spaced")
        assert proj["root_path"] == spaced_path

    def test_path_with_unicode(self, db, tmp_path: Path):
        """Paths with unicode characters are valid."""
        uni_path = str(tmp_path / "pröjekt" / "übung")
        db.register_project("unicode-proj", uni_path)
        proj = db.get_project("unicode-proj")
        assert proj["root_path"] == uni_path

    def test_register_many_projects(self, db, tmp_path: Path):
        """Can handle many projects."""
        for i in range(50):
            db.register_project(f"proj-{i}", str(tmp_path / f"p{i}"))
        assert len(db.list_projects()) == 50

    def test_sql_injection_in_name(self, db):
        """SQL injection attempts in project name are rejected by validation."""
        with pytest.raises(ValueError, match=r"[Ii]nvalid project name"):
            db.register_project("'; DROP TABLE projects; --", "/tmp/x")

    def test_sql_injection_in_path(self, db, tmp_path: Path):
        """SQL injection in path is safely handled (parameterized queries)."""
        evil_path = "'; DROP TABLE projects; --"
        db.register_project("safe-app", evil_path)
        proj = db.get_project("safe-app")
        assert proj["root_path"] == evil_path  # stored literally, not executed

    def test_remove_project_then_reregister(self, db, tmp_path: Path):
        """Can reuse name after removal."""
        db.register_project("myapp", str(tmp_path / "v1"))
        db.remove_project("myapp")
        db.register_project("myapp", str(tmp_path / "v2"))
        proj = db.get_project("myapp")
        assert proj["root_path"] == str(tmp_path / "v2")

    def test_register_updates_last_used(self, db, tmp_path: Path):
        """register_project sets last_used_at."""
        db.register_project("myapp", str(tmp_path))
        proj = db.get_project("myapp")
        last_used = datetime.fromisoformat(proj["last_used_at"])
        assert last_used.year >= 2026

    def test_set_active_updates_last_used(self, db, tmp_path: Path):
        """Switching to a project updates its last_used_at."""
        db.register_project("myapp", str(tmp_path))
        proj_before = db.get_project("myapp")
        db.set_active_project("myapp")
        proj_after = db.get_project("myapp")
        # last_used_at should be >= what it was
        before = datetime.fromisoformat(proj_before["last_used_at"])
        after = datetime.fromisoformat(proj_after["last_used_at"])
        assert after >= before


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
            rows = conn.execute(
                "SELECT context_limit FROM llm_profiles"
            ).fetchall()
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
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()

        assert row[0] == 128_000  # default from ALTER TABLE
        assert version[0] == 5  # V2, V3, V4, V5 all applied

    def test_idempotent_v2_migration(self, db_path: Path):
        """Running Database() twice doesn't fail on duplicate ALTER TABLE."""
        from specweaver.config.database import Database

        Database(db_path)
        db2 = Database(db_path)  # should not raise
        with db2.connect() as conn:
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 5  # V2, V3, V4, V5 all applied


# ---------------------------------------------------------------------------
# Validation Override UPSERT edge cases
# ---------------------------------------------------------------------------


class TestValidationOverrideUpsert:
    """Edge cases for set_validation_override partial-update logic."""

    def test_load_validation_settings_no_overrides(self, db, tmp_path: Path):
        """Project with zero overrides returns empty ValidationSettings."""
        db.register_project("clean", str(tmp_path / "clean"))
        settings = db.load_validation_settings("clean")
        assert settings.overrides == {}

    def test_set_and_load_override(self, db, tmp_path: Path):
        """Set an override, then load it back."""
        db.register_project("proj", str(tmp_path / "proj"))
        db.set_validation_override(
            "proj", "S01",
            enabled=True, warn_threshold=5.0, fail_threshold=3.0,
        )
        settings = db.load_validation_settings("proj")
        assert "S01" in settings.overrides
        assert settings.overrides["S01"].warn_threshold == 5.0
        assert settings.overrides["S01"].fail_threshold == 3.0

    def test_partial_update_preserves_existing(self, db, tmp_path: Path):
        """Updating only warn_threshold should preserve fail_threshold."""
        db.register_project("proj", str(tmp_path / "proj"))
        db.set_validation_override(
            "proj", "S02",
            enabled=True, warn_threshold=8.0, fail_threshold=5.0,
        )
        # Update only warn_threshold
        db.set_validation_override("proj", "S02", warn_threshold=6.0)
        settings = db.load_validation_settings("proj")
        override = settings.overrides["S02"]
        assert override.warn_threshold == 6.0
        assert override.fail_threshold == 5.0  # preserved

    def test_disable_rule(self, db, tmp_path: Path):
        """Can disable a rule via override."""
        db.register_project("proj", str(tmp_path / "proj"))
        db.set_validation_override("proj", "S03", enabled=False)
        settings = db.load_validation_settings("proj")
        assert settings.overrides["S03"].enabled is False

    def test_is_enabled_defaults_true(self, db, tmp_path: Path):
        """Rules without overrides default to enabled."""
        db.register_project("proj", str(tmp_path / "proj"))
        settings = db.load_validation_settings("proj")
        assert settings.is_enabled("S99") is True


# ---------------------------------------------------------------------------
# Schema v3 migration — log_level column
# ---------------------------------------------------------------------------


class TestSchemaV3Migration:
    """Test the v2→v3 schema migration (log_level column on projects)."""

    def test_log_level_column_exists(self, db, tmp_path: Path):
        """log_level column is present after migration."""
        db.register_project("myapp", str(tmp_path))
        with db.connect() as conn:
            row = conn.execute(
                "SELECT log_level FROM projects WHERE name='myapp'"
            ).fetchone()
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
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (2, '2026-01-01T00:00:00Z')"
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
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 5  # v3, v4, v5 all applied


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
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
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
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (3, '2026-01-01T00:00:00Z')"
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
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 5  # v4 and v5 both applied


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

    def test_set_domain_profile_clears_existing_overrides(self, db, tmp_path: Path):
        """Setting a profile clears all existing validation overrides."""
        db.register_project("myapp", str(tmp_path))
        # Set some overrides manually
        db.set_validation_override("myapp", "S08", warn_threshold=99, fail_threshold=99)
        db.set_validation_override("myapp", "C04", fail_threshold=99)
        assert len(db.get_validation_overrides("myapp")) == 2

        # Apply profile — should clear old overrides
        db.set_domain_profile("myapp", "web-app")
        overrides = db.get_validation_overrides("myapp")
        # Should have the profile's overrides, not the old ones
        rule_ids = {o["rule_id"] for o in overrides}
        assert "S08" in rule_ids  # web-app has S08
        assert "C04" in rule_ids  # web-app has C04
        # But values should be from profile, not our old 99s
        s08 = next(o for o in overrides if o["rule_id"] == "S08")
        assert s08["warn_threshold"] == 3  # web-app S08 warn
        assert s08["fail_threshold"] == 8  # web-app S08 fail

    def test_set_domain_profile_writes_profile_overrides(self, db, tmp_path: Path):
        """Setting a profile writes all override values from the profile."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")
        overrides = db.get_validation_overrides("myapp")
        rule_ids = {o["rule_id"] for o in overrides}
        # Library profile has: S03, S05, S07, S08, S11, C04
        assert rule_ids == {"S03", "S05", "S07", "S08", "S11", "C04"}

    def test_clear_domain_profile_clears_overrides(self, db, tmp_path: Path):
        """Clearing a profile also clears all validation overrides."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        assert len(db.get_validation_overrides("myapp")) > 0

        db.clear_domain_profile("myapp")
        assert db.get_validation_overrides("myapp") == []

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
        """Profile name lookup is case-insensitive; stored as lowercase."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "WEB-APP")
        # The profile is found case-insensitively
        overrides = db.get_validation_overrides("myapp")
        assert len(overrides) > 0

    def test_schema_version_is_5(self, db):
        """Schema version is 5 after v5 migration."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            assert row[0] == 5


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
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (4, '2026-01-01T00:00:00Z')"
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
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 5

