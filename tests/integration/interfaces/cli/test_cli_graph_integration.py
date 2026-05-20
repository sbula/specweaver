import sqlite3

from typer.testing import CliRunner

from specweaver.interfaces.cli._core import get_db
from specweaver.interfaces.cli.main import app
from tests.fixtures.db_utils import register_test_project, set_test_active_project

runner = CliRunner()


def test_graph_build_integration_real_flow(tmp_path, monkeypatch):
    """sw graph build command builds and persists a real graph to SQLite."""
    # Setup temporary project directory and isolation
    data_dir = tmp_path / ".specweaver"
    data_dir.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    # Initialize DB and set active project
    db = get_db()
    register_test_project(db, "test-proj", str(tmp_path))
    set_test_active_project(db, "test-proj")

    # Create a target file to parse
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    test_file = src_dir / "math_utils.py"
    test_file.write_text(
        "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n",
        encoding="utf-8",
    )

    # Act: Run command
    result = runner.invoke(app, ["graph", "build", str(test_file), "-p", str(tmp_path)])

    # Assert CLI succeeded
    assert result.exit_code == 0
    assert "Successfully built graph" in result.output

    # Assert SQLite database is populated with nodes and edges
    db_path = tmp_path / ".specweaver" / "graph.db"
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT semantic_hash, file_id, service_name, is_active FROM nodes")
        nodes = cursor.fetchall()

        # Verify default service name and normalized file path
        assert len(nodes) > 0
        for _semantic_hash, file_id, service_name, is_active in nodes:
            assert service_name == "default"
            assert is_active == 1
            assert "math_utils.py" in file_id


def test_graph_build_integration_topology_service(tmp_path, monkeypatch):
    """sw graph build command resolves service name from topology yaml when present."""
    data_dir = tmp_path / ".specweaver"
    data_dir.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    db = get_db()
    register_test_project(db, "test-proj-topo", str(tmp_path))
    set_test_active_project(db, "test-proj-topo")

    # Create topology context.yaml file
    context_file = tmp_path / "context.yaml"
    context_file.write_text(
        "name: payment_service\nkind: service\n",
        encoding="utf-8",
    )

    # Create a target file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    test_file = src_dir / "payment.py"
    test_file.write_text("class Processor:\n    pass\n", encoding="utf-8")

    # Act: Run command
    result = runner.invoke(app, ["graph", "build", str(test_file), "-p", str(tmp_path)])

    assert result.exit_code == 0

    db_path = tmp_path / ".specweaver" / "graph.db"
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT service_name FROM nodes LIMIT 1")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "payment_service"
