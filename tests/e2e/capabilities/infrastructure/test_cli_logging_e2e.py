# mypy: ignore-errors
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from specweaver.telemetry_logger import get_log_path, setup_logging, teardown_logging

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


async def test_cli_execution_suppresses_debug_and_writes_json(tmp_path: Path) -> None:
    from unittest.mock import patch

    def _mock_op(op: str, *args, **kwargs):
        if op == "get_active_project":
            return "test_project"
        if op == "list_projects":
            return [{"name": "test_project", "root_path": "/fake"}]
        return "test_project"

    with (
        patch("specweaver.telemetry_logger._get_logs_dir", return_value=tmp_path),
        patch("specweaver.interfaces.cli._core.run_repo_op", side_effect=_mock_op),
        patch("specweaver.core.config.db_bootstrap.get_db"),
        patch("specweaver.interfaces.cli._core.get_db"),
    ):
        teardown_logging()
        setup_logging("test_project")
        log_file = get_log_path("test_project")

        try:
            # Invoke a command that we know logs debug. 'projects' is in workspace/project/interfaces/cli.py
            result = runner.invoke(app, ["projects"])

            # 1. Console Cleanliness
            assert "Executing projects command" not in result.stdout

            # Flush logging
            for h in logging.getLogger("specweaver").handlers:
                h.flush()

            # 2. JSON Telemetry Written
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")

            # We look for the JSON log line that contains our debug statement
            found = False
            for line in content.strip().split("\n"):
                try:
                    record = json.loads(line)
                    if record.get(
                        "levelname"
                    ) == "DEBUG" and "Executing projects command" in record.get("message", ""):
                        found = True
                        break
                except json.JSONDecodeError:
                    continue

            assert found, "DEBUG log was not captured in the JSON telemetry file"

        finally:
            teardown_logging()
