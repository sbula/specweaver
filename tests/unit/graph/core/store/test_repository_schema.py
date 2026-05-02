import sqlite3

from specweaver.graph.core.store.repository import SqliteGraphRepository


def test_sqlite_repository_initialization_creates_schema(tmp_path):
    """Test that initializing the repository creates the SQLite database and schema."""
    db_path = tmp_path / "graph.db"

    # Initialize repository
    SqliteGraphRepository(str(db_path), validated_service_name="test_service")

    # Verify the database file was created
    assert db_path.exists()

    # Verify the schema was applied by querying sqlite_master
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        assert "nodes" in tables
        assert "edges" in tables

        # Verify PRAGMA journal_mode=WAL
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.upper() == "WAL"


def test_sqlite_repository_nodes_schema(tmp_path):
    """Test that the nodes table has the correct columns."""
    db_path = tmp_path / "graph.db"
    SqliteGraphRepository(str(db_path), validated_service_name="test_service")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(nodes);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "id": "INTEGER",
            "semantic_hash": "TEXT",
            "clone_hash": "TEXT",
            "file_id": "TEXT",
            "service_name": "TEXT",
            "package_name": "TEXT",
            "is_active": "INTEGER",
            "metadata": "JSON",
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name] == col_type


def test_sqlite_repository_edges_schema(tmp_path):
    """Test that the edges table has the correct columns and no strict FK on target_id."""
    db_path = tmp_path / "graph.db"
    SqliteGraphRepository(str(db_path), validated_service_name="test_service")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(edges);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "source_id": "INTEGER",
            "target_id": "INTEGER",
            "type": "TEXT",
            "metadata": "JSON",
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns
            assert columns[col_name] == col_type

        # Verify Foreign Keys (there should be NO FK on target_id due to LAZY edges)
        cursor.execute("PRAGMA foreign_key_list(edges);")
        fk_list = cursor.fetchall()

        # It's okay if source_id has an FK, but target_id MUST NOT have one.
        for fk in fk_list:
            from_col = fk[3]
            assert from_col != "target_id", "target_id must not have a strict Foreign Key!"
