# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""End-to-End user journey test for multi-provider CLI interaction."""

import os
import typing
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app  # type: ignore[attr-defined]

runner = CliRunner()


_OPENAI_REPLY = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677652288,
    "model": "gpt-5.4",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "This is a drafted spec."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
}


@pytest.fixture
def mock_openai_response() -> typing.Generator[list[Any], None, None]:
    """OpenAI answers every chat call; yields the requests it received.

    openai 3.x sends through httpx2, which respx cannot see — see `tests/fake_http.py`.
    """
    import httpx2

    from tests.fake_http import fake_httpx2

    def reply(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        return httpx2.Response(200, json=_OPENAI_REPLY)

    with fake_httpx2(reply) as seen:
        yield seen


@pytest.fixture
def test_project(tmp_path: Path) -> typing.Generator[Path, None, None]:
    """Sets up a test project and initializes it."""
    # Ensure OPENAI_API_KEY is set so 'available()' passes
    os.environ["OPENAI_API_KEY"] = "sk-test-key-123"

    # We need to initialize the project first
    result = runner.invoke(app, ["init", "e2e-test-project", "--path", str(tmp_path)])
    assert result.exit_code == 0, f"Failed to init project: {result.stdout}"

    yield tmp_path

    # Teardown
    os.environ.pop("OPENAI_API_KEY", None)


def test_openai_draft_telemetry_journey(
    test_project: Path, mock_openai_response: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    E2E User Journey: provider=openai -> sw draft -> telemetry shows openai.
    """
    # 1. Check if openai is installed in the test environment
    pytest.importorskip("openai", reason="openai SDK not installed, skipping E2E test")

    # 2. Configure project to use openai provider
    result = runner.invoke(app, ["config", "set-provider", "openai"])
    assert result.exit_code == 0, f"Failed to set provider config: {result.stdout}"

    # 3. Run the draft command
    # Mocking the interactive input
    with (
        patch("rich.prompt.Confirm.ask", return_value=True),
        patch("rich.prompt.Prompt.ask", return_value="Draft looks good"),
    ):
        # 'sw draft TestComponent' interacts with the flow engine.
        result = runner.invoke(app, ["draft", "TestComponent", "--project", str(test_project)])
        print(f"draft exit code: {result.exit_code}")
        print(f"draft stdout: {result.stdout}")
        if result.exception:
            print(f"draft exception: {result.exception}")

    # 4. Verify HTTP layer was called
    assert mock_openai_response, (
        f"The OpenAI API was never called. Exit: {result.exit_code}, Output: {result.stdout}"
    )

    # 5. Verify Telemetry was recorded with provider="openai"
    import sqlite3

    db_path = test_project / ".specweaver-test" / "specweaver.db"
    assert db_path.exists(), f"Database not found at {db_path}"

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT provider, model, total_tokens FROM llm_usage_log ORDER BY id DESC LIMIT 1"
        )
        record = cursor.fetchone()

    assert record is not None, "No telemetry record found."
    assert record[0] == "openai"
    assert record[2] == 150
