# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — Database.clear_all_project_routing()."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.database import Database

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Database:
    """Create a temporary database with a registered project."""
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    db.register_project("test-proj", "/path")
    return db


class TestClearAllProjectRouting:
    """Test Database.clear_all_project_routing()."""

    def test_clears_task_entries(self, tmp_db: Database) -> None:
        """Deletes all task: routing entries, returns count."""
        pid1 = tmp_db.create_llm_profile("p1", provider="gemini", model="m1")
        pid2 = tmp_db.create_llm_profile("p2", provider="openai", model="m2")
        tmp_db.link_project_profile("test-proj", "task:implement", pid1)
        tmp_db.link_project_profile("test-proj", "task:review", pid2)

        count = tmp_db.clear_all_project_routing("test-proj")

        assert count == 2
        assert tmp_db.get_project_routing_entries("test-proj") == []

    def test_ignores_non_task_entries(self, tmp_db: Database) -> None:
        """Non-task: role entries (e.g. 'draft') are not deleted."""
        pid = tmp_db.create_llm_profile("p1", provider="gemini", model="m1")
        tmp_db.link_project_profile("test-proj", "draft", pid)
        tmp_db.link_project_profile("test-proj", "task:implement", pid)

        count = tmp_db.clear_all_project_routing("test-proj")

        assert count == 1
        # The 'draft' link must still exist
        links = tmp_db.get_project_llm_links("test-proj")
        assert any(link["role"] == "draft" for link in links)

    def test_clears_orphaned_links(self, tmp_db: Database) -> None:
        """Deletes task: links even when the linked profile has been deleted."""
        pid = tmp_db.create_llm_profile("orphan-prof", provider="gemini", model="m1")
        tmp_db.link_project_profile("test-proj", "task:plan", pid)

        # Delete the profile directly, leaving an orphaned link.
        # Must disable FK enforcement since the link references this profile.
        with tmp_db.connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM llm_profiles WHERE id = ?", (pid,))
            conn.execute("PRAGMA foreign_keys = ON")

        # clear_all should still delete the orphaned task: link
        count = tmp_db.clear_all_project_routing("test-proj")
        assert count == 1

    def test_returns_zero_when_empty(self, tmp_db: Database) -> None:
        """Returns 0 when no routing entries exist."""
        count = tmp_db.clear_all_project_routing("test-proj")
        assert count == 0
