from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from specweaver.graph.interfaces.cli import graph_app as app

runner = CliRunner()


def test_graph_build_success() -> None:
    with patch("specweaver.graph.core.builder.orchestrator.GraphOrchestrator") as mock_orchestrator:
        mock_orchestrator.build_target.return_value = 1

        result = runner.invoke(app, ["src/foo.py"])

        assert result.exit_code == 0
        assert "Successfully built graph" in result.stdout
        mock_orchestrator.build_target.assert_called_once_with(Path("src/foo.py"), Path("."))


def test_graph_build_failure() -> None:
    with patch("specweaver.graph.core.builder.orchestrator.GraphOrchestrator") as mock_orchestrator:
        mock_orchestrator.build_target.side_effect = Exception("Parse error")

        result = runner.invoke(app, ["src/bad.py"])

        assert result.exit_code == 1
        assert "Failed to build graph" in result.stdout
        assert "Parse error" in result.stdout
