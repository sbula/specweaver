from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.core.config.database import Database
from specweaver.interfaces.cli.lineage import app

runner = CliRunner()


@pytest.fixture
def isolated_db(tmp_path):
    # Set up a real database for the CLI to interact with during E2E
    db_path = tmp_path / "specweaver.db"
    from specweaver.interfaces.cli._db_utils import bootstrap_database

    bootstrap_database(str(db_path))
    db = Database(str(db_path))
    from tests.fixtures.db_utils import register_test_project, set_test_active_project

    register_test_project(db, "e2e-test-project", str(tmp_path))
    set_test_active_project(db, "e2e-test-project")
    return db


def test_lineage_tag_and_tree_e2e_happy_path(tmp_path, isolated_db):
    """[Happy Path] Running sw lineage tag creates the SQLite row, and sw lineage tree outputs the correct visual graph."""
    target_file = tmp_path / "test_file.py"
    target_file.write_text("def some_function():\n    pass\n", encoding="utf-8")

    # We patch _core.get_db to return our isolated DB so it doesn't pollute the user's ~/.specweaver/
    with patch("specweaver.interfaces.cli._core.get_db") as mock_get_db:
        mock_get_db.return_value = isolated_db

        with patch("specweaver.interfaces.cli.lineage.get_db") as mock_lineage_get_db:
            mock_lineage_get_db.return_value = isolated_db

        # 1. Tag the file
        result_tag = runner.invoke(app, ["tag", str(target_file), "--author", "e2e-robot"])
        print(f"OUTPUT: {result_tag.output}")
        print(f"EXCEPTION: {result_tag.exception}")
        assert result_tag.exit_code == 0

        # Verify the file was actually tagged
        content = target_file.read_text(encoding="utf-8")
        assert "# sw-artifact:" in content

        # Extract the UUID
        uuid_line = next(line for line in content.splitlines() if "# sw-artifact:" in line)
        artifact_uuid = uuid_line.split(": ")[1].strip()

        # 2. Run the tree command using the file path
        result_tree_file = runner.invoke(app, ["tree", str(target_file)])
        assert result_tree_file.exit_code == 0
        assert artifact_uuid in result_tree_file.output
        assert "manual_tag:e2e-robot" in result_tree_file.output

        # 3. Run the tree command using the raw UUID
        result_tree_uuid = runner.invoke(app, ["tree", artifact_uuid])
        assert result_tree_uuid.exit_code == 0
        assert artifact_uuid in result_tree_uuid.output
        assert "manual_tag:e2e-robot" in result_tree_uuid.output
