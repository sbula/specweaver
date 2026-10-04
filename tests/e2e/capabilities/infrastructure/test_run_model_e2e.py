# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`--model` sends one run's calls to that model; the settings file stays as it is (US-16 P8).

Proves: C-FLOW-13 FR-16

| Bucket | Case |
|---|---|
| Happy | `sw implement --model m@gb10` with `default` on another server → every request goes to the GB10 |
| Boundary | `sw run <pipeline> --model m@gb10` → the pipeline's model step goes to the GB10 too; a pipeline without model steps ignores even a broken settings file, `--model` or not |
| Degradation | the same command without `--model` → the file's server, so the flag really was the cause |
| Hostile | `--model gpt-6` (no server) and `--model m@hosted` in a private-only project → refused before any request |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx2
import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[servers.spare]
kind = "openai-compatible"
base_url = "http://spare:8000/v1"
private = true
max_parallel = 2

[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
default = "qwen3-coder-next@spare"
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "qwen3-coder-next",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "def greet():\n    pass\n"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}

_ONE_REVIEW = """\
name: one_review
version: "1.0"
steps:
  - name: review_spec
    action: review
    target: spec
"""


def _project(tmp_path: Path, isolate_env: Path, llm_section: str = "") -> tuple[Path, Path]:
    (isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    if llm_section:
        (project / "specweaver.toml").write_text(llm_section, encoding="utf-8")
    assert runner.invoke(app, ["init", "run-model", "--path", str(project)]).exit_code == 0
    spec = project / "specs" / "greeter_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")
    return project, spec


def _urls(seen) -> set[str]:
    return {str(request.url) for request in seen}


def _reply(_request):
    return httpx2.Response(200, json=_REPLY)


@pytest.mark.usefixtures("_mock_db", "stub_implement_qa")
class TestImplementWithRunModel:
    def test_every_request_goes_to_the_run_models_server(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        project, spec = _project(tmp_path, _isolate_env)

        with fake_httpx2(_reply) as seen:
            runner.invoke(
                app,
                [
                    "implement",
                    str(spec),
                    "--project",
                    str(project),
                    "--model",
                    "qwen3-coder-next@gb10",
                ],
            )

        assert seen, "sw implement sent no request at all"
        assert _urls(seen) == {"http://gb10:8000/v1/chat/completions"}
        assert (_isolate_env / "settings.toml").read_text(encoding="utf-8") == _MACHINE

    def test_without_the_flag_the_file_decides(self, tmp_path: Path, _isolate_env: Path) -> None:
        project, spec = _project(tmp_path, _isolate_env)

        with fake_httpx2(_reply) as seen:
            runner.invoke(app, ["implement", str(spec), "--project", str(project)])

        assert _urls(seen) == {"http://spare:8000/v1/chat/completions"}


@pytest.mark.usefixtures("_mock_db")
class TestRunWithRunModel:
    def test_a_pipeline_step_goes_to_the_run_models_server(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        project, spec = _project(tmp_path, _isolate_env)
        pipeline = tmp_path / "one_review.yaml"
        pipeline.write_text(_ONE_REVIEW, encoding="utf-8")
        assert runner.invoke(app, ["use", "run-model"]).exit_code == 0

        with fake_httpx2(_reply) as seen:
            runner.invoke(
                app,
                [
                    "run",
                    str(pipeline),
                    str(spec),
                    "--project",
                    str(project),
                    "--model",
                    "qwen3-coder-next@gb10",
                ],
            )

        assert seen, "sw run sent no request at all"
        assert _urls(seen) == {"http://gb10:8000/v1/chat/completions"}

    def test_a_pipeline_without_model_steps_ignores_even_a_broken_settings_file(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        project, spec = _project(tmp_path, _isolate_env)
        (_isolate_env / "settings.toml").write_text("[servers.gb10\n", encoding="utf-8")
        assert runner.invoke(app, ["use", "run-model"]).exit_code == 0
        run = ["run", "validate_only", str(spec), "--project", str(project)]

        plain = runner.invoke(app, run)
        with fake_httpx2(_reply) as seen:
            flagged = runner.invoke(app, [*run, "--model", "qwen3-coder-next@gb10"])

        assert seen == []
        assert flagged.exit_code == plain.exit_code, flagged.output
        assert not shows(flagged.output, "settings.toml"), flagged.output


@pytest.mark.usefixtures("_mock_db")
class TestRunModelRefused:
    def test_a_model_without_a_server(self, tmp_path: Path, _isolate_env: Path) -> None:
        project, spec = _project(tmp_path, _isolate_env)

        with fake_httpx2(_reply) as seen:
            result = runner.invoke(
                app, ["implement", str(spec), "--project", str(project), "--model", "gpt-6"]
            )

        assert seen == []
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit), result.exception
        assert shows(result.output, "model@server")

    def test_a_hosted_server_in_a_private_only_project(
        self, tmp_path: Path, _isolate_env: Path
    ) -> None:
        project, spec = _project(tmp_path, _isolate_env, "[llm]\nprivate_only = true\n")

        with (
            fake_httpx2(_reply) as seen,
            patch("rich.prompt.Confirm.ask", return_value=True),
        ):
            result = runner.invoke(
                app,
                [
                    "implement",
                    str(spec),
                    "--project",
                    str(project),
                    "--model",
                    "qwen3-coder-next@hosted",
                ],
            )

        assert seen == []
        assert result.exit_code == 1
        assert shows(result.output, "private servers only")
