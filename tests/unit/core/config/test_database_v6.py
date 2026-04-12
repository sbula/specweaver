# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for database schema v6 migration and project_standards CRUD."""

from __future__ import annotations

import json

import pytest

from specweaver.core.config.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    return Database(tmp_path / "test.db")


@pytest.fixture
def db_with_project(db):
    """Database with a registered project."""
    db.register_project("test-project", "/tmp/test-project")
    db.set_active_project("test-project")
    return db


# ---------------------------------------------------------------------------
# Schema v6 migration
# ---------------------------------------------------------------------------


class TestSchemaV6Migration:
    """Verify that the project_standards table exists after migration."""

    def test_project_standards_table_exists(self, db: Database) -> None:
        """Schema v6 should create the project_standards table."""
        with db.connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='project_standards'",
            )
            assert cursor.fetchone() is not None

    def test_schema_version_is_at_least_6(self, db: Database) -> None:
        """Schema version should be >= 6 after migration."""
        with db.connect() as conn:
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version",
            ).fetchone()[0]
            assert version >= 6


# ---------------------------------------------------------------------------
# save_standard()
# ---------------------------------------------------------------------------


class TestSaveStandard:
    """Tests for saving standards to DB."""

    def test_save_new_standard(self, db_with_project: Database) -> None:
        """Saving a new standard should insert a row."""
        db_with_project.save_standard(
            project_name="test-project",
            scope=".",
            language="python",
            category="naming",
            data={"style": "snake_case"},
            confidence=0.94,
        )
        result = db_with_project.get_standard(
            "test-project",
            ".",
            "python",
            "naming",
        )
        assert result is not None
        assert result["confidence"] == pytest.approx(0.94)
        assert json.loads(result["data"])["style"] == "snake_case"

    def test_save_standard_upserts(self, db_with_project: Database) -> None:
        """Saving the same standard again should update (upsert)."""
        db_with_project.save_standard(
            project_name="test-project",
            scope=".",
            language="python",
            category="naming",
            data={"style": "snake_case"},
            confidence=0.8,
        )
        db_with_project.save_standard(
            project_name="test-project",
            scope=".",
            language="python",
            category="naming",
            data={"style": "camelCase"},
            confidence=0.95,
        )
        result = db_with_project.get_standard(
            "test-project",
            ".",
            "python",
            "naming",
        )
        assert json.loads(result["data"])["style"] == "camelCase"
        assert result["confidence"] == pytest.approx(0.95)

    def test_save_standard_with_confirmed_by(
        self,
        db_with_project: Database,
    ) -> None:
        """confirmed_by field should be stored."""
        db_with_project.save_standard(
            project_name="test-project",
            scope=".",
            language="python",
            category="naming",
            data={"style": "snake_case"},
            confidence=0.9,
            confirmed_by="hitl",
        )
        result = db_with_project.get_standard(
            "test-project",
            ".",
            "python",
            "naming",
        )
        assert result["confirmed_by"] == "hitl"

    def test_save_standard_default_confirmed_by_is_none(
        self,
        db_with_project: Database,
    ) -> None:
        """confirmed_by should default to None."""
        db_with_project.save_standard(
            project_name="test-project",
            scope=".",
            language="python",
            category="naming",
            data={"style": "snake_case"},
            confidence=0.9,
        )
        result = db_with_project.get_standard(
            "test-project",
            ".",
            "python",
            "naming",
        )
        assert result["confirmed_by"] is None

    def test_save_multiple_categories(self, db_with_project: Database) -> None:
        """Different categories should coexist."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"style": "snake_case"},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "docstrings",
            {"style": "google"},
            0.87,
        )
        standards = db_with_project.get_standards("test-project")
        assert len(standards) == 2

    def test_save_different_scopes(self, db_with_project: Database) -> None:
        """Same category in different scopes should be independent."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"style": "snake_case"},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            "user-service",
            "python",
            "naming",
            {"style": "camelCase"},
            0.7,
        )
        root = db_with_project.get_standard(
            "test-project",
            ".",
            "python",
            "naming",
        )
        service = db_with_project.get_standard(
            "test-project",
            "user-service",
            "python",
            "naming",
        )
        assert json.loads(root["data"])["style"] == "snake_case"
        assert json.loads(service["data"])["style"] == "camelCase"


# ---------------------------------------------------------------------------
# get_standards()
# ---------------------------------------------------------------------------


class TestGetStandards:
    """Tests for querying standards from DB."""

    def test_get_all_standards(self, db_with_project: Database) -> None:
        """Get all standards for a project."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "docstrings",
            {"x": 2},
            0.8,
        )
        db_with_project.save_standard(
            "test-project",
            "svc",
            "typescript",
            "naming",
            {"x": 3},
            0.7,
        )
        standards = db_with_project.get_standards("test-project")
        assert len(standards) == 3

    def test_get_standards_filtered_by_scope(
        self,
        db_with_project: Database,
    ) -> None:
        """Filter standards by scope."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            "svc",
            "python",
            "naming",
            {"x": 2},
            0.8,
        )
        scoped = db_with_project.get_standards("test-project", scope="svc")
        assert len(scoped) == 1
        assert scoped[0]["scope"] == "svc"

    def test_get_standards_filtered_by_language(
        self,
        db_with_project: Database,
    ) -> None:
        """Filter standards by language."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            ".",
            "typescript",
            "naming",
            {"x": 2},
            0.8,
        )
        py_only = db_with_project.get_standards(
            "test-project",
            language="python",
        )
        assert len(py_only) == 1
        assert py_only[0]["language"] == "python"

    def test_get_standards_empty_returns_empty_list(
        self,
        db_with_project: Database,
    ) -> None:
        """No standards → empty list (not None)."""
        standards = db_with_project.get_standards("test-project")
        assert standards == []


# ---------------------------------------------------------------------------
# clear_standards()
# ---------------------------------------------------------------------------


class TestClearStandards:
    """Tests for deleting standards from DB."""

    def test_clear_all_standards(self, db_with_project: Database) -> None:
        """Clear all standards for a project."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            "svc",
            "python",
            "naming",
            {"x": 2},
            0.8,
        )
        db_with_project.clear_standards("test-project")
        assert db_with_project.get_standards("test-project") == []

    def test_clear_scoped_standards(self, db_with_project: Database) -> None:
        """Clear only standards for a specific scope."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            "svc",
            "python",
            "naming",
            {"x": 2},
            0.8,
        )
        db_with_project.clear_standards("test-project", scope="svc")
        remaining = db_with_project.get_standards("test-project")
        assert len(remaining) == 1
        assert remaining[0]["scope"] == "."


# ---------------------------------------------------------------------------
# list_scopes()
# ---------------------------------------------------------------------------


class TestListScopes:
    """Tests for listing known scopes."""

    def test_list_scopes(self, db_with_project: Database) -> None:
        """List distinct scopes for a project."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            "svc-a",
            "python",
            "naming",
            {"x": 2},
            0.8,
        )
        db_with_project.save_standard(
            "test-project",
            "svc-b",
            "typescript",
            "naming",
            {"x": 3},
            0.7,
        )
        scopes = db_with_project.list_scopes("test-project")
        assert sorted(scopes) == [".", "svc-a", "svc-b"]

    def test_list_scopes_empty(self, db_with_project: Database) -> None:
        """No standards → empty scope list."""
        scopes = db_with_project.list_scopes("test-project")
        assert scopes == []

    def test_list_scopes_no_duplicates(
        self,
        db_with_project: Database,
    ) -> None:
        """Multiple categories in same scope → scope listed once."""
        db_with_project.save_standard(
            "test-project",
            "svc",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        db_with_project.save_standard(
            "test-project",
            "svc",
            "python",
            "docstrings",
            {"x": 2},
            0.8,
        )
        scopes = db_with_project.list_scopes("test-project")
        assert scopes == ["svc"]


# ---------------------------------------------------------------------------
# CASCADE delete
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Standards should be deleted when the project is removed."""

    def test_standards_deleted_with_project(
        self,
        db_with_project: Database,
    ) -> None:
        """Deleting a project should cascade-delete its standards."""
        db_with_project.save_standard(
            "test-project",
            ".",
            "python",
            "naming",
            {"x": 1},
            0.9,
        )
        assert len(db_with_project.get_standards("test-project")) == 1

        # Delete the project
        db_with_project.remove_project("test-project")
        assert db_with_project.get_standards("test-project") == []
