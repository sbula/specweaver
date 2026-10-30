# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A TypeScript timeout reaches the atom as a not-run result that names the tool.

Proves: TECH-087 FR-15

Real atom, runner and `SubprocessExecutor`; a fake `npx` (and `node`) on `PATH` stands in for the
toolchain, and the timeout is cut to 1 s so the real executor kills it.

| Bucket | Case |
|---|---|
| Happy | tsc prints a type error and exits: the error is counted |
| Boundary | ESLint hangs with no output: "ESLint timed out after 1 s" |
| Boundary | the debugged program hangs: "dist/main.js timed out after 1 s", exit 124 |
| Degradation | tsc hangs after a partial line: "tsc timed out after 1 s", the line not counted |
| Hostile | the partial line is a well-formed tsc error; it must not read as the verdict |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

pytestmark = pytest.mark.integration

_TSC_ERROR = "src/a.ts(1,7): error TS2322: Type 'string' is not assignable to type 'number'."


def _atom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, npx_body: str) -> QARunnerAtom:
    from specweaver.sandbox.language.core.typescript import runner
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    npx = bin_dir / "npx"
    npx.write_text(f"#!/bin/sh\n{npx_body}\n", encoding="utf-8")
    npx.chmod(0o755)
    node = bin_dir / "node"
    node.write_text(f"#!/bin/sh\n{npx_body}\n", encoding="utf-8")
    node.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setattr(runner, "_TSC_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(runner, "_ESLINT_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(runner, "_DEBUG_TIMEOUT_SECONDS", 1)
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.ts").write_text("const x: number = 'y';\n", encoding="utf-8")
    return QARunnerAtom(cwd=project, language="typescript")


def test_a_tsc_error_is_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    atom = _atom(tmp_path, monkeypatch, f'echo "{_TSC_ERROR}"; exit 2')

    result = atom.run({"intent": "run_compiler", "target": "src"})

    assert result.exports["error_count"] == 1
    assert result.exports["errors"][0]["code"] == "TS2322"


def test_a_tsc_that_hangs_after_a_partial_line_timed_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    atom = _atom(tmp_path, monkeypatch, f'echo "{_TSC_ERROR}"; exec sleep 30')

    result = atom.run({"intent": "run_compiler", "target": "src"})

    assert result.exports["error_count"] == 1
    error = result.exports["errors"][0]
    assert (error["code"], error["message"]) == ("ToolchainUnavailable", "tsc timed out after 1 s")


def test_an_eslint_that_hangs_timed_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    atom = _atom(tmp_path, monkeypatch, "exec sleep 30")

    result = atom.run({"intent": "run_architecture", "target": "src"})

    assert result.exports["violation_count"] == 1
    violation = result.exports["violations"][0]
    assert (violation["code"], violation["message"]) == (
        "ToolchainUnavailable",
        "ESLint timed out after 1 s",
    )


def test_a_debugged_program_that_hangs_timed_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    atom = _atom(tmp_path, monkeypatch, "echo started; exec sleep 30")

    result = atom.run({"intent": "run_debugger", "target": ".", "entrypoint": "dist/main.js"})

    assert result.exports["exit_code"] == 124
    assert [e["output"] for e in result.exports["events"]] == ["dist/main.js timed out after 1 s"]
