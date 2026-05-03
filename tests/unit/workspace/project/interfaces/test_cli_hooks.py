import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

# Force import to test decentralized location (Red Phase)
from specweaver.interfaces.cli.main import app


@pytest.fixture(autouse=True)
def _mock_workspace(monkeypatch):
    """Patch _run_workspace_op so we don't hit the real DB and cause aiosqlite warnings."""
    monkeypatch.setattr(
        "specweaver.workspace.project.interfaces.cli._run_workspace_op",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("specweaver.logging.setup_logging", lambda *args, **kwargs: None)


def test_hooks_install_pre_commit_success(tmp_path: Path):
    """Test successful installation of the pre-commit hook."""
    runner = CliRunner()

    # Setup mock git repository structure
    git_dir = tmp_path / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    with patch(
        "specweaver.workspace.project.interfaces.cli.resolve_project_path", return_value=tmp_path
    ):
        result = runner.invoke(app, ["hooks", "install", "--pre-commit"])

    assert result.exit_code == 0
    assert "installed successfully" in result.stdout.lower()

    hook_file = hooks_dir / "pre-commit"
    assert hook_file.exists()

    # Check permissions
    assert os.access(hook_file, os.X_OK)

    # Check content
    content = hook_file.read_text()
    assert "#!/usr/bin/env bash" in content
    assert str(sys.executable) in content
    assert "check-rot --staged" in content
    assert "exit_code=$?" in content
    assert "if [ $exit_code -eq 42 ]; then" in content
    assert "elif [ $exit_code -ne 0 ]; then" in content


def test_hooks_install_no_git_dir(tmp_path: Path):
    """Test hook installation fails nicely if not a git repository."""
    runner = CliRunner()

    # We deliberately do not create .git/ directory here

    with patch(
        "specweaver.workspace.project.interfaces.cli.resolve_project_path", return_value=tmp_path
    ):
        result = runner.invoke(app, ["hooks", "install", "--pre-commit"])

    assert result.exit_code == 1
    assert "not a git repository" in result.stdout.lower()


def test_hooks_install_resolve_error():
    """Test graceful fail if project path cannot be resolved."""
    runner = CliRunner()

    with patch(
        "specweaver.workspace.project.interfaces.cli.resolve_project_path",
        side_effect=FileNotFoundError("Invalid path"),
    ):
        result = runner.invoke(app, ["hooks", "install"])

    assert result.exit_code == 1
    assert "invalid path" in result.stdout.lower()


def test_hooks_install_no_pre_commit(tmp_path: Path):
    """Test passing --no-pre-commit skips templating entirely."""
    runner = CliRunner()

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)

    with patch(
        "specweaver.workspace.project.interfaces.cli.resolve_project_path", return_value=tmp_path
    ):
        result = runner.invoke(app, ["hooks", "install", "--no-pre-commit"])

    assert result.exit_code == 0
    hook_file = git_dir / "hooks" / "pre-commit"
    assert not hook_file.exists()
