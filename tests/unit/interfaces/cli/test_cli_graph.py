from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from specweaver.interfaces.cli.graph import app

runner = CliRunner()

def test_graph_build_success() -> None:
    with patch("specweaver.interfaces.cli.graph.InMemoryGraphEngine") as mock_engine_class, \
         patch("specweaver.interfaces.cli.graph.SqliteGraphRepository") as mock_repo_class, \
         patch("specweaver.interfaces.cli.graph.GraphBuilder") as mock_builder_class, \
         patch("specweaver.interfaces.cli.graph.extract_ast_dict") as mock_parser, \
         patch("specweaver.interfaces.cli.graph._load_topology"):

        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        mock_repo = MagicMock()
        mock_repo.load_from_db.return_value = (MagicMock(), {})
        mock_repo.get_all_file_hashes.return_value = {"src/foo.py": "123"}
        mock_repo_class.return_value = mock_repo

        mock_builder = MagicMock()
        mock_builder_class.return_value = mock_builder

        result = runner.invoke(app, ["src/foo.py"])
        print(result.stdout)

        assert result.exit_code == 0
        assert "Successfully built graph" in result.stdout

        # Verify Dependency Injection wiring
        mock_builder_class.assert_called_once_with(engine=mock_engine, parser=mock_parser, id_prefix="default")

        # Verify execution
        mock_builder.ingest_file.assert_called_once_with(str(Path("src/foo.py")))

        # Verify persistence
        mock_repo.flush_to_db.assert_called_once_with(mock_engine)

def test_graph_build_failure() -> None:
    with patch("specweaver.interfaces.cli.graph.InMemoryGraphEngine"), \
         patch("specweaver.interfaces.cli.graph.SqliteGraphRepository") as mock_repo_class, \
         patch("specweaver.interfaces.cli.graph.GraphBuilder") as mock_builder_class, \
         patch("specweaver.interfaces.cli.graph.extract_ast_dict"), \
         patch("specweaver.interfaces.cli.graph._load_topology"):

        mock_repo_class.return_value.load_from_db.return_value = (MagicMock(), {})
        mock_repo_class.return_value.get_all_file_hashes.return_value = {}

        mock_builder = MagicMock()
        mock_builder.ingest_file.side_effect = Exception("Parse error")
        mock_builder_class.return_value = mock_builder

        result = runner.invoke(app, ["src/bad.py"])

        assert result.exit_code == 1
        assert "Failed to build graph" in result.stdout
        assert "Parse error" in result.stdout

def test_graph_build_directory() -> None:
    with patch("specweaver.interfaces.cli.graph.InMemoryGraphEngine"), \
         patch("specweaver.interfaces.cli.graph.SqliteGraphRepository") as mock_repo_class, \
         patch("specweaver.interfaces.cli.graph.GraphBuilder") as mock_builder_class, \
         patch("specweaver.interfaces.cli.graph.extract_ast_dict"), \
         patch("specweaver.interfaces.cli.graph._load_topology"), \
         patch("specweaver.interfaces.cli.graph.Path.is_file") as mock_is_file, \
         patch("specweaver.interfaces.cli.graph.Path.is_dir") as mock_is_dir, \
         patch("specweaver.interfaces.cli.graph.Path.rglob") as mock_rglob:

        mock_repo_class.return_value.load_from_db.return_value = (MagicMock(), {})
        mock_repo_class.return_value.get_all_file_hashes.return_value = {}

        mock_is_file.return_value = False
        mock_is_dir.return_value = True

        mock_file1 = MagicMock()
        mock_file1.is_file.return_value = True
        mock_file1.__str__.return_value = "src/dir/file1.py"

        mock_file2 = MagicMock()
        mock_file2.is_file.return_value = True
        mock_file2.__str__.return_value = "src/dir/file2.py"

        mock_rglob.return_value = [mock_file1, mock_file2]

        mock_builder = MagicMock()
        mock_builder_class.return_value = mock_builder

        result = runner.invoke(app, ["src/dir"])

        assert result.exit_code == 0
        assert mock_builder.ingest_file.call_count == 2
