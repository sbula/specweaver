# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A contract declared on disk is compared against the code that should implement it.

Proves: TECH-066 FR-1, TECH-066 FR-2

`C13` reads `protocol_schema` from its rule context and nothing in `src/` produced that key, so it
took the skip branch on every code check. Measured before the fix: a project with an `api.proto`
declaring a service and a source file implementing none of it reported
`C13 SKIP — Missing 'protocol_schema'`. `A-VAL-01` FR-5 promises ERRORs on mismatched signatures, and
its unit test handed the rule a `protocol_schema` literal — proving the comparison against a context
no run constructed.

The parsers were never the gap. `ProtocolParserFactory` already reads `.proto`, OpenAPI and AsyncAPI,
each behind its own unit test; what was missing was anything that found the files and called them.

**The matching run is the load-bearing half.** A discovery that returned nothing would leave C13
skipping and satisfy a drift-only assertion perfectly, and so would a rule that flagged every project
whatever its code said.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

#: OpenAPI, because `C13` compares an endpoint's PATH against the code's structure literally. That
#: suits a path-based contract, where the route appears in a decorator. It cannot confirm a gRPC
#: method is implemented — `Users/GetUser` is a name the code never has to spell — so the proto below
#: is used for the half that check can actually answer: an endpoint the code does not carry.
OPENAPI = """openapi: 3.0.0
info:
  title: Users
  version: '1'
paths:
  /api/v1/users:
    get:
      responses:
        '200':
          description: ok
"""

PROTO = """syntax = "proto3";
package demo;

service Users {
  rpc GetUser (Req) returns (Res);
}
"""

#: Carries no route at all.
DRIFTED = '''"""A service."""


def unrelated() -> int:
    """Do something else entirely."""
    return 1
'''

#: Binds the declared path, the way a route is actually written.
ALIGNED = '''"""A service."""

from fastapi import FastAPI

app = FastAPI()


@app.get("/api/v1/users")
def list_users() -> list[str]:
    """List users."""
    return []
'''


def _project(tmp_path: Path, source: str, *, contract: str | None) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    runner.invoke(app, ["init", project.name, "--path", str(project)])
    src = project / "src"
    src.mkdir(exist_ok=True)
    (src / "service.py").write_text(source, encoding="utf-8")
    if contract == "openapi":
        (project / "openapi.yaml").write_text(OPENAPI, encoding="utf-8")
    elif contract == "proto":
        (project / "api.proto").write_text(PROTO, encoding="utf-8")
    return project


def _c13_row(project: Path) -> str:
    result = runner.invoke(
        app,
        [
            "check",
            str(project / "src" / "service.py"),
            "--level",
            "code",
            "--project",
            str(project),
        ],
    )
    rows = [_ANSI.sub("", line) for line in result.output.splitlines() if "C13" in line]
    return rows[0] if rows else "(C13 absent from the report)"


def test_a_declared_contract_the_code_ignores_is_a_failure(tmp_path: Path) -> None:
    row = _c13_row(_project(tmp_path, DRIFTED, contract="openapi"))

    assert "FAIL" in row, row


def test_a_proto_contract_is_discovered_too(tmp_path: Path) -> None:
    """Both parsers are reached, not only the YAML one the pass case uses."""
    project = _project(tmp_path, DRIFTED, contract="proto")
    result = runner.invoke(
        app,
        [
            "check",
            str(project / "src" / "service.py"),
            "--level",
            "code",
            "--project",
            str(project),
        ],
    )

    assert "Users/GetUser" in _ANSI.sub("", result.output)


def test_the_finding_names_the_endpoint_that_drifted(tmp_path: Path) -> None:
    """A verdict a reader cannot act on is a verdict that will be ignored."""
    project = _project(tmp_path, DRIFTED, contract="openapi")
    result = runner.invoke(
        app,
        [
            "check",
            str(project / "src" / "service.py"),
            "--level",
            "code",
            "--project",
            str(project),
        ],
    )

    assert "/api/v1/users" in _ANSI.sub("", result.output)


def test_code_that_matches_its_contract_passes(tmp_path: Path) -> None:
    """The control. Without it, a rule that flagged every project would look correct."""
    row = _c13_row(_project(tmp_path, ALIGNED, contract="openapi"))

    assert "PASS" in row, row


def test_a_project_declaring_no_contract_still_skips(tmp_path: Path) -> None:
    """SKIP stays the honest answer where there is nothing to compare against.

    The defect was never that C13 skipped — it was that it skipped when a contract WAS there.
    """
    row = _c13_row(_project(tmp_path, DRIFTED, contract=None))

    assert "SKIP" in row, row
