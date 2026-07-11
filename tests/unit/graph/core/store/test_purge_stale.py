# mypy: ignore-errors
import sqlite3

import networkx as nx
import pytest

from specweaver.graph.core.store.repository import SqliteGraphRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "graph.db"
    return SqliteGraphRepository(str(db_path), validated_service_name="test_service")


def populate_db(repo, file_ids: list[str]) -> None:
    g = nx.DiGraph()
    for i, file_id in enumerate(file_ids):
        g.add_node(
            f"test_service:ast:{i}",
            file_id=file_id,
            package_name="pkg",
            metadata={},
        )
    repo.persist_semantic_digraph(g)


def get_active_files(repo) -> set[str]:
    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT file_id FROM nodes WHERE is_active = 1 AND service_name = 'test_service'"
        )
        return {row[0] for row in cursor.fetchall()}


def test_purge_stale_entries_removes_deleted_files(repo):
    """[Happy Path] Purges files in DB that are not in the known_file_ids set."""
    populate_db(repo, ["src/a.py", "src/b.py", "src/c.py"])

    purged = repo.purge_stale_entries({"src/a.py", "src/c.py"})

    assert purged == ["src/b.py"]
    assert get_active_files(repo) == {"src/a.py", "src/c.py"}


def test_purge_stale_entries_no_stale(repo):
    """[Boundary] If all DB files are in known_file_ids, nothing is purged."""
    populate_db(repo, ["src/a.py", "src/b.py"])

    purged = repo.purge_stale_entries({"src/a.py", "src/b.py", "src/new.py"})

    assert purged == []
    assert get_active_files(repo) == {"src/a.py", "src/b.py"}


def test_purge_stale_entries_empty_db(repo):
    """[Boundary] Empty DB returns empty list."""
    purged = repo.purge_stale_entries({"src/a.py"})
    assert purged == []


def test_purge_stale_entries_all_stale(repo):
    """[Boundary] Empty known set purges everything."""
    populate_db(repo, ["src/a.py", "src/b.py"])

    purged = repo.purge_stale_entries(set())

    assert set(purged) == {"src/a.py", "src/b.py"}
    assert get_active_files(repo) == set()


def test_purge_stale_entries_windows_paths(repo):
    """[Hostile] Windows backslashes in known_file_ids must be normalized to prevent accidental purges."""
    populate_db(repo, ["src/a.py", "src/nested/b.py"])

    # Caller provides Windows paths
    purged = repo.purge_stale_entries({"src\\a.py", "src\\nested\\b.py"})

    # Should normalize and match the DB, so nothing is purged
    assert purged == []
    assert get_active_files(repo) == {"src/a.py", "src/nested/b.py"}
