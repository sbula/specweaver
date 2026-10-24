# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /implement` runs the implement pipeline `sw implement` runs, and reports the task's files.

Proves: TECH-078 FR-4

The model and the language's runner are doubled (the doubles of
`test_implement_in_every_language_e2e.py`); the API, the run setup, the bundled pipeline, the flow,
the task's files and the QA steps are real.

| Bucket | Case |
|---|---|
| Happy | a TypeScript project: the six steps run; the answer names `src/greeter.ts` and `tests/greeter.test.ts` |
| Boundary | the API's pipeline is the bundled `implement_spec`, the one `sw implement` loads |
| Degradation | tests still failing after the loop: 200, `status: "failed"`, the counts |
| Hostile | a spec whose `Package` line is not a package answers 400 naming the line |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.parser import load_bundled_pipeline
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.interfaces.api.app import create_app
from specweaver.sandbox.qa_runner.core.interface import TestRunResult
from tests.api_token import AUTH, TEST_TOKEN
from tests.e2e.capabilities.workflows.test_implement_in_every_language_e2e import (
    _LANGUAGES,
    _Model,
    _Runner,
)
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_TYPESCRIPT = next(lang for lang in _LANGUAGES if lang.key == "typescript")


class _FailingRunner(_Runner):
    def run_tests(self, target: str, *_a: Any, **_k: Any) -> TestRunResult:
        self._log["tests"].append(target)
        return TestRunResult(
            total=1, passed=0, failed=1, errors=0, skipped=0, duration_seconds=0.1, failures=[]
        )


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    (project / _TYPESCRIPT.manifest[0]).write_text(_TYPESCRIPT.manifest[1], encoding="utf-8")
    with TestClient(create_app(token=TEST_TOKEN, db=db), headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "ts", "path": str(project), "scaffold": False}
        )
        yield client, project


def _implement(client: TestClient, runner: type[_Runner] = _Runner) -> tuple[Any, list[Any]]:
    log: dict[str, list[str]] = {"tests": [], "lint": [], "fix": []}
    pipelines: list[Any] = []
    real_init = PipelineRunner.__init__

    def _capture(self: PipelineRunner, pipeline: Any, *args: Any, **kwargs: Any) -> None:
        pipelines.append(pipeline)
        real_init(self, pipeline, *args, **kwargs)

    with (
        doubled_llm(_Model(_TYPESCRIPT)),
        patch(
            "specweaver.sandbox.qa_runner.core.factory.resolve_runner",
            side_effect=lambda cwd, executor=None, language=None: runner(language or "?", log),
        ),
        patch.object(PipelineRunner, "__init__", _capture),
    ):
        answer = client.post(
            "/api/v1/implement", json={"file": "specs/greeter_spec.md", "project": "ts"}
        )
    return answer, pipelines


def test_a_typescript_project_gets_the_six_steps_and_its_files(api) -> None:
    client, project = api

    answer, pipelines = _implement(client)

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["status"] == "completed"
    assert body["code_path"] == str(project / "src/greeter.ts")
    assert body["test_path"] == str(project / "tests/greeter.test.ts")
    assert body["tests"]["passed"] == 1
    assert (project / "src/greeter.ts").is_file()
    assert [s.name for s in pipelines[0].steps] == [
        "generate_code",
        "generate_tests",
        "lint_fix",
        "run_tests",
        "validate_code",
        "acceptance",
    ]


def test_the_api_runs_the_bundled_implement_pipeline(api) -> None:
    client, _project = api

    _answer, pipelines = _implement(client)

    assert pipelines[0] == load_bundled_pipeline("implement_spec")


def test_tests_still_failing_answer_200_failed_with_the_counts(api) -> None:
    client, _project = api

    answer, _pipelines = _implement(client, _FailingRunner)

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["status"] == "failed"
    assert body["tests"] == {"passed": 0, "failed": 1, "coverage_pct": None}


def test_a_bad_package_line_answers_400_naming_it(api) -> None:
    client, project = api
    (project / "pom.xml").write_text("<project><groupId>a</groupId></project>\n")
    (project / _TYPESCRIPT.manifest[0]).unlink()
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n> **Package**: Not-A.Package\n")

    answer, _pipelines = _implement(client)

    assert answer.status_code == 400, answer.text
    assert "greeter_spec.md:2" in answer.json()["detail"]


class _BrokenModel(_Model):
    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> Any:
        raise RuntimeError("model unreachable")


def test_a_generation_error_answers_500_without_a_traceback(api) -> None:
    client, _project = api

    with (
        doubled_llm(_BrokenModel(_TYPESCRIPT)),
        patch(
            "specweaver.sandbox.qa_runner.core.factory.resolve_runner",
            side_effect=lambda cwd, executor=None, language=None: _Runner("?", {}),
        ),
    ):
        answer = client.post(
            "/api/v1/implement", json={"file": "specs/greeter_spec.md", "project": "ts"}
        )

    assert answer.status_code == 500, answer.text
    assert answer.json()["error_code"] == "GENERATION_FAILED"
    assert "model unreachable" in answer.json()["detail"]
    assert "Traceback" not in answer.json()["detail"]


def test_a_broken_implement_section_answers_500_naming_it(api) -> None:
    client, project = api
    (project / "specweaver.toml").write_text('[implement]\nlanguage = "cobol"\n', encoding="utf-8")

    answer, _pipelines = _implement(client)

    assert answer.status_code == 500, answer.text
    assert answer.json()["error_code"] == "IMPLEMENT_POLICY"
