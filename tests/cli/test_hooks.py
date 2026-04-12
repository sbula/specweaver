import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app


def test_hooks_install_pre_commit_success(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Test successful installation of the pre-commit hook."""
    runner = CliRunner()

    # Setup mock git repository structure
    git_dir = tmp_path / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    with (
        caplog.at_level("DEBUG", logger="specweaver.interfaces.cli.hooks"),
        patch("specweaver.interfaces.cli.hooks.resolve_project_path", return_value=tmp_path),
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

    # Telemetry
    assert f"Resolved project path: {tmp_path}" in caplog.text
    assert f"Ensuring hooks directory exists: {hooks_dir}" in caplog.text
    assert f"Writing hook to {hook_file}" in caplog.text
    assert f"Successfully installed pre-commit hook at {hook_file}" in caplog.text


def test_hooks_install_no_git_dir(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Test hook installation fails nicely if not a git repository."""
    runner = CliRunner()

    # We deliberately do not create .git/ directory here

    with (
        caplog.at_level("ERROR", logger="specweaver.interfaces.cli.hooks"),
        patch("specweaver.interfaces.cli.hooks.resolve_project_path", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["hooks", "install", "--pre-commit"])

    assert result.exit_code == 1
    assert "not a git repository" in result.stdout.lower()
    assert f"Target is not a git repository: {tmp_path / '.git'}" in caplog.text


def test_hooks_install_resolve_error(caplog: pytest.LogCaptureFixture):
    """Test graceful fail if project path cannot be resolved."""
    runner = CliRunner()

    with (
        caplog.at_level("ERROR", logger="specweaver.interfaces.cli.hooks"),
        patch(
            "specweaver.interfaces.cli.hooks.resolve_project_path",
            side_effect=FileNotFoundError("Invalid path"),
        ),
    ):
        result = runner.invoke(app, ["hooks", "install"])

    assert result.exit_code == 1
    assert "invalid path" in result.stdout.lower()
    assert "Project path resolution failed: Invalid path" in caplog.text


def test_hooks_install_no_pre_commit(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Test passing --no-pre-commit skips templating entirely."""
    runner = CliRunner()

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)

    with (
        caplog.at_level("INFO", logger="specweaver.interfaces.cli.hooks"),
        patch("specweaver.interfaces.cli.hooks.resolve_project_path", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["hooks", "install", "--no-pre-commit"])

    assert result.exit_code == 0
    hook_file = git_dir / "hooks" / "pre-commit"
    assert not hook_file.exists()
    assert "Skip pre-commit hook installation" in caplog.text
