# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /api/v1/check` counts skipped rules and never calls a run where no rule judged a pass.

Proves: TECH-082 FR-13, FR-14

The door (P-2): the real app, the real project lookup, the real pipeline and rules. C01 judges
Python only, so on a Kotlin file a pipeline holding only C01 judges nothing (`TECH-093`). The CLI
and the API read one summary; the agreement test checks they say the same.

| Bucket | Case |
|---|---|
| Happy | a Python file is `PASS` with `skipped` 0 |
| Boundary | the Kotlin file is `NOTHING_CHECKED` with `skipped` 1 |
| Degradation | `strict` does not turn `NOTHING_CHECKED` into anything else |
| Hostile | — (the request is a real file in a registered project) |
"""

from __future__ import annotations

import contextlib
import re

import pytest
import typer
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
ONLY_C01 = (
    "name: only_c01\ntype: validation_pipeline\ntarget: code\n"
    "steps:\n  - name: c01_syntax_valid\n    rule: C01\n"
)


@pytest.fixture()
def client(tmp_path):
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    db_path = tmp_path / ".specweaver-test" / "specweaver.db"
    bootstrap_database(str(db_path))
    return TestClient(create_app(token=TEST_TOKEN, db=Database(db_path)), headers=AUTH)


@pytest.fixture()
def project(client, tmp_path):
    proj = tmp_path / "greet"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "Greet.kt").write_text('fun greet(n: String) = "Hi, $n"\n', encoding="utf-8")
    (proj / "src" / "greet.py").write_text("def greet(n):\n    return n\n", encoding="utf-8")
    pipelines = proj / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True)
    (pipelines / "only_c01.yaml").write_text(ONLY_C01, encoding="utf-8")
    client.post("/api/v1/projects", json={"name": "greet", "path": str(proj), "scaffold": False})
    return proj


def _check(client, file: str, *, strict: bool = False) -> dict:
    resp = client.post(
        "/api/v1/check",
        json={
            "file": file,
            "level": "code",
            "project": "greet",
            "pipeline": "only_c01",
            "strict": strict,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.usefixtures("project")
def test_a_file_no_rule_judges_is_nothing_checked(client) -> None:
    data = _check(client, "src/Greet.kt")

    assert (data["overall"], data["skipped"], data["passed"], data["total"]) == (
        "NOTHING_CHECKED",
        1,
        0,
        1,
    )


@pytest.mark.usefixtures("project")
def test_strict_does_not_hide_nothing_checked(client) -> None:
    assert _check(client, "src/Greet.kt", strict=True)["overall"] == "NOTHING_CHECKED"


@pytest.mark.usefixtures("project")
def test_a_judged_file_counts_no_skip(client) -> None:
    data = _check(client, "src/greet.py")

    assert (data["overall"], data["skipped"], data["passed"]) == ("PASS", 0, 1)


def test_the_cli_and_the_api_agree(capsys) -> None:
    """One summary: the CLI's line and the API's `overall` come from the same verdict."""
    from specweaver.assurance.validation.interfaces.cli import _print_summary
    from specweaver.assurance.validation.models import RuleResult, Status
    from specweaver.interfaces.api.v1.validation import _check_response

    cases = {
        (Status.SKIP,): ("NOTHING CHECKED", "NOTHING_CHECKED"),
        (Status.PASS, Status.SKIP): ("ALL PASSED", "PASS"),
        (Status.WARN,): ("PASSED with warnings", "WARN"),
        (Status.FAIL, Status.SKIP): ("FAILED", "FAIL"),
    }
    for statuses, (line, overall) in cases.items():
        results = [RuleResult(rule_id="R", rule_name="r", status=s) for s in statuses]
        with contextlib.suppress(typer.Exit):
            _print_summary(results)
        printed = _ANSI.sub("", capsys.readouterr().out)
        response = _check_response(results, strict=False)

        assert line in printed, (statuses, printed)
        assert response.overall == overall, statuses
        assert response.skipped == statuses.count(Status.SKIP), statuses
