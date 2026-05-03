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


@pytest.fixture
def mock_openai_response() -> typing.Generator[Any, None, None]:
    # Mocking at the factory layer isn't true E2E, but mocking HTTP with respx
    # or mocking the AsyncOpenAI client is better.
    # Since respx is already in dev dependencies, we can use it.
    import httpx
    import respx

    with respx.mock(base_url="https://api.openai.com/v1") as respx_mock:
        route = respx_mock.post("/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": 1677652288,
                    "model": "gpt-5.4",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "This is a drafted spec.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
                },
            )
        )
        yield route


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
    assert mock_openai_response.called, (
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
