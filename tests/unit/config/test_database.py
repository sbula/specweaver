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
        """Schema version is 8 after v8 migration."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            assert row[0] == 8

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
        assert "system-default" in names
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
        assert count == 4  # Includes system-default


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
        assert set(names) == {"review", "draft", "search", "system-default"}

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
        assert fetched["model"] == "gemini-3-flash-preview"
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
        assert roles == {"review", "draft", "search", "system-default"}

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
# get_llm_profile_by_name (gap #13-14)
# ---------------------------------------------------------------------------


class TestGetLlmProfileByName:
    """Tests for the get_llm_profile_by_name DB helper."""

    def test_get_profile_by_name_found(self, db):
        """Existing profile is returned as a dict."""
        profile = db.get_llm_profile_by_name("review")
        assert profile is not None
        assert profile["name"] == "review"
        assert profile["model"] == "gemini-3-flash-preview"

    def test_get_profile_by_name_system_default(self, db):
        """system-default profile is retrievable by name."""
        profile = db.get_llm_profile_by_name("system-default")
        assert profile is not None
        assert profile["name"] == "system-default"
        assert profile["is_global"] == 1

    def test_get_profile_by_name_not_found(self, db):
        """Non-existent profile name returns None."""
        profile = db.get_llm_profile_by_name("nonexistent-profile")
        assert profile is None
