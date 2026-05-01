from typer.testing import CliRunner

import specweaver.interfaces.cli.lineage  # noqa: F401 - Register commands
from specweaver.graph_store.lineage_repository import LineageRepository
from specweaver.interfaces.cli._core import app, get_db

runner = CliRunner()


def test_lineage_tag_integration_real_db(tmp_path, monkeypatch):
    """sw lineage tag invokes Typer against a temporary real db."""
    # Setup temporary project directory and isolation
    data_dir = tmp_path / ".specweaver"
    data_dir.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    # Initialize DB (creates Schema V12)
    db = get_db()
    db.register_project("test-proj", str(tmp_path))
    db.set_active_project("test-proj")

    local_db_dir = tmp_path / ".specweaver"
    local_db_dir.mkdir(parents=True, exist_ok=True)
    repo = LineageRepository(str(local_db_dir / "graph.db"))

    # Create target file
    test_file = tmp_path / "target.py"
    test_file.write_text("def foo():\n    pass\n", encoding="utf-8")

    # Act
    result = runner.invoke(
        app, ["lineage", "tag", str(test_file), "--author", "integration_test_model"]
    )

    # Assert
    assert result.exit_code == 0
    assert "Added tag" in result.output

    # Verify DB has model_id populated properly
    content = test_file.read_text(encoding="utf-8")
    uuid_str = None
    for line in content.splitlines():
        if line.startswith("# sw-artifact: "):
            uuid_str = line.split(": ")[1].strip()
            break

    assert uuid_str is not None
    history = repo.get_artifact_history(uuid_str)

    # Assert
    assert len(history) == 1
    assert history[0]["model_id"] == "integration_test_model"
    assert history[0]["event_type"] == "manual_tag"


def test_lineage_tree_integration_multigen(tmp_path, monkeypatch):
    """sw lineage tree correctly maps root->child->grandchild events."""
    data_dir = tmp_path / ".specweaver_tree"
    data_dir.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    db = get_db()
    db.register_project("test-proj2", str(tmp_path))
    db.set_active_project("test-proj2")

    local_db_dir = tmp_path / ".specweaver"
    local_db_dir.mkdir(parents=True, exist_ok=True)
    repo = LineageRepository(str(local_db_dir / "graph.db"))

    # Insert events manually using DB interface
    repo.log_artifact_event("root-x", None, "run-1", "generated_code", "human")
    repo.log_artifact_event("child-y", "root-x", "run-2", "edit", "model_1")
    repo.log_artifact_event("grandchild-z", "child-y", "run-3", "lint", "model_2")

    # Act
    result = runner.invoke(app, ["lineage", "tree", "child-y"])

    # Assert
    assert result.exit_code == 0
    # Because it starts from child-y, it should climb to root-x and render all three
    assert "Lineage Graph (Root: root-x)" in result.output
    assert "root-x" in result.output
    assert "child-y" in result.output
    assert "grandchild-z" in result.output


def test_lineage_e2e_full_pipeline(tmp_path, monkeypatch):
    """Full end-to-end lineage tracking on a source file."""
    data_dir = tmp_path / ".specweaver_e2e"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    db = get_db()
    db.register_project("test-proj3", str(tmp_path))
    db.set_active_project("test-proj3")

    # Create a dummy python file
    target_file = tmp_path / "hello.py"
    target_file.write_text("print('hello')\n", encoding="utf-8")

    # Step 1: Tag the file
    result_tag = runner.invoke(app, ["lineage", "tag", str(target_file), "--author", "e2e_human"])
    assert result_tag.exit_code == 0

    # Step 2: Use tree on the file itself!
    result_tree = runner.invoke(app, ["lineage", "tree", str(target_file)])
    assert result_tree.exit_code == 0

    content = target_file.read_text(encoding="utf-8")
    assert "# sw-artifact:" in content

    uuid_str = None
    for line in content.splitlines():
        if line.startswith("# sw-artifact: "):
            uuid_str = line.split(": ")[1].strip()
            break

    assert uuid_str is not None

    # Both tag and tree commands interacted flawlessly
    assert f"Root: {uuid_str}" in result_tree.output
    assert "manual_tag:e2e_human" in result_tree.output
