# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A stricter boundary tool the project configured runs in addition, and says when it did not run.

Proves: TECH-082 FR-20

With no `tach.toml` tach is not configured, so nothing runs and nothing fails `[agreed 2026-11-05]`.
A configured tool that cannot run is reported as not run, never as clean `[agreed 2026-11-05]`.

| Bucket | Case |
|---|---|
| Happy | tach, dependency-cruiser and go-arch-lint: clean, and violations carry the tool's name |
| Boundary | no config file → not listed; a Go file → tach is not asked; depcruise `info` is no finding |
| Degradation | not installed, timed out, unreadable output → not run, with the reason |
| Hostile | output that is valid JSON but not a list → not run |
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.language.core import boundary_extras
from specweaver.sandbox.language.core.boundary_extras import run_extras

if TYPE_CHECKING:
    from pathlib import Path

UNDECLARED = (
    '[{"Located": {"file_path": "a/b.py", "details": {"Code": {"UndeclaredDependency": '
    '{"dependency": "c.d", "usage_module": "a", "definition_module": "c"}}}}}]'
)


class _Executor:
    def __init__(self, stdout: str = "[]", *, exit_code: int = 0, timed_out: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._result = SimpleNamespace(
            exit_code=exit_code, stdout=stdout, stderr="", timed_out=timed_out
        )

    def execute(self, cmd: list[str], *, timeout_seconds: int | None = None) -> SimpleNamespace:
        self.calls.append(cmd)
        return self._result


@pytest.fixture
def configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "tach.toml").write_text("exact = true\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")
    return tmp_path


def test_a_clean_tach_run_ran_and_found_nothing(configured: Path) -> None:
    executor = _Executor("[]")

    [run] = run_extras(configured, "python", executor)

    assert (run.tool, run.ran, run.reason, run.violations) == ("tach", True, "", [])
    assert executor.calls == [["python", "-m", "tach", "check", "--output", "json"]]


def test_tachs_violations_carry_the_tools_name(configured: Path) -> None:
    [run] = run_extras(configured, "python", _Executor(UNDECLARED, exit_code=1))

    assert run.ran
    assert [(v.file, v.code) for v in run.violations] == [("a/b.py", "tach:UndeclaredDependency")]
    assert "cannot import 'c.d'" in run.violations[0].message


def test_without_tach_toml_tach_is_not_configured(tmp_path: Path) -> None:
    executor = _Executor()

    assert run_extras(tmp_path, "python", executor) == []
    assert executor.calls == []


def test_a_go_file_does_not_ask_tach(configured: Path) -> None:
    assert run_extras(configured, "go", _Executor()) == []


def test_tach_not_installed_is_not_run(configured: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)

    [run] = run_extras(configured, "python", _Executor())

    assert (run.ran, run.violations) == (False, [])
    assert "not installed" in run.reason


@pytest.mark.parametrize(
    ("executor", "says"),
    [
        (_Executor("", timed_out=True), "tach timed out after 120 s"),
        (_Executor("not json", exit_code=2), "could not read"),
        (_Executor('{"a": 1}', exit_code=1), "could not read"),
        (_Executor("[1]", exit_code=1), "could not read"),
        (_Executor("", exit_code=1), "did not run"),
    ],
)
def test_a_tach_run_with_no_verdict_is_not_run(
    configured: Path, executor: _Executor, says: str
) -> None:
    [run] = run_extras(configured, "python", executor)

    assert run.ran is False
    assert says in run.reason


def test_container_mode_does_not_ask_the_host_path(
    configured: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a container the host PATH says nothing: tach is looked for inside the image."""
    from unittest.mock import MagicMock

    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)
    executor = MagicMock(spec=ContainerSubprocessExecutor)
    executor.execute.return_value = SimpleNamespace(
        exit_code=0, stdout="[]", stderr="", timed_out=False
    )

    [run] = run_extras(configured, "python", executor)

    assert run.ran
    executor.execute.assert_called_once()


def test_tach_missing_inside_the_container_is_not_run(configured: Path) -> None:
    from unittest.mock import MagicMock

    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

    executor = MagicMock(spec=ContainerSubprocessExecutor)
    executor.execute.return_value = SimpleNamespace(
        exit_code=1, stdout="", stderr="/usr/bin/python3: No module named tach", timed_out=False
    )

    [run] = run_extras(configured, "python", executor)

    assert run.ran is False
    assert "tach" in run.reason


def test_an_unavailable_container_engine_is_not_run(configured: Path) -> None:
    from unittest.mock import MagicMock

    from specweaver.sandbox.execution.container_executor import (
        ContainerEngineUnavailableError,
        ContainerSubprocessExecutor,
    )

    executor = MagicMock(spec=ContainerSubprocessExecutor)
    executor.execute.side_effect = ContainerEngineUnavailableError("no podman")

    [run] = run_extras(configured, "python", executor)

    assert (run.ran, run.reason) == (False, "no podman")


DEPCRUISE = (
    '{"modules": [], "summary": {"violations": ['
    '{"from": "src/domain/a.ts", "to": "src/infra/db.ts", '
    '"rule": {"name": "no-domain-to-infra", "severity": "error"}},'
    '{"from": "src/x.ts", "to": "src/y.ts", "rule": {"name": "just-saying", "severity": "info"}}'
    '], "error": 1, "warn": 0, "info": 1, "totalCruised": 3}}'
)
GO_ARCH = (
    '{"Type": "models.Check", "Payload": {"ArchHasWarnings": true, "ArchWarningsDeps": ['
    '{"ComponentName": "domain", "FileRelativePath": "internal/domain/svc.go", '
    '"FileAbsolutePath": "/p/internal/domain/svc.go", "ResolvedImportName": "app/internal/infra", '
    '"Reference": {}}], "ArchWarningsNotMatched": [], "ArchWarningsDeepScan": []}}'
)


@pytest.mark.parametrize(
    ("config", "language", "command"),
    [
        (
            ".dependency-cruiser.cjs",
            "typescript",
            [
                "npx",
                "--no-install",
                "depcruise",
                "--output-type",
                "json",
                "--config",
                ".dependency-cruiser.cjs",
                ".",
            ],
        ),
        (
            ".dependency-cruiser.json",
            "javascript",
            [
                "npx",
                "--no-install",
                "depcruise",
                "--output-type",
                "json",
                "--config",
                ".dependency-cruiser.json",
                ".",
            ],
        ),
        (
            ".go-arch-lint.yml",
            "go",
            ["go-arch-lint", "check", "--json", "--project-path", "."],
        ),
    ],
)
def test_each_configured_tool_runs_its_own_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: str, language: str, command: list[str]
) -> None:
    (tmp_path / config).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")
    clean = (
        '{"ArchHasWarnings": false, "ArchWarningsDeps": null}'
        if language == "go"
        else '{"summary": {"violations": []}}'
    )
    executor = _Executor(clean)

    [run] = run_extras(tmp_path, language, executor)

    assert (run.ran, run.violations) == (True, []), run.reason
    assert executor.calls == [command]


def test_dependency_cruisers_errors_are_violations_its_info_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".dependency-cruiser.js").write_text("module.exports = {};\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")

    [run] = run_extras(tmp_path, "typescript", _Executor(DEPCRUISE, exit_code=1))

    assert [(v.file, v.code) for v in run.violations] == [
        ("src/domain/a.ts", "dependency-cruiser:no-domain-to-infra")
    ]
    assert "'src/infra/db.ts'" in run.violations[0].message


def test_go_arch_lints_dependency_warnings_are_violations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".go-arch-lint.yml").write_text("version: 3\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")

    [run] = run_extras(tmp_path, "go", _Executor(GO_ARCH, exit_code=1))

    assert [(v.file, v.code) for v in run.violations] == [
        ("internal/domain/svc.go", "go-arch-lint:dependency")
    ]
    assert "'app/internal/infra'" in run.violations[0].message


@pytest.mark.parametrize(
    ("config", "language", "stdout"),
    [
        (".dependency-cruiser.js", "typescript", "[]"),
        (".dependency-cruiser.js", "typescript", '{"summary": {"violations": [1]}}'),
        (".go-arch-lint.yml", "go", "[]"),
        (".go-arch-lint.yml", "go", '{"ArchHasWarnings": true, "ArchWarningsDeps": [1]}'),
        (".go-arch-lint.yml", "go", '{"a": 1}'),
    ],
)
def test_output_of_the_wrong_shape_is_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: str, language: str, stdout: str
) -> None:
    (tmp_path / config).write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")

    [run] = run_extras(tmp_path, language, _Executor(stdout, exit_code=1))

    assert run.ran is False
    assert "could not read" in run.reason


def test_go_arch_lint_not_installed_is_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".go-arch-lint.yml").write_text("version: 3\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)

    [run] = run_extras(tmp_path, "go", _Executor())

    assert (run.tool, run.ran) == ("go-arch-lint", False)
    assert "not installed" in run.reason


def test_a_rule_without_severity_is_a_violation_and_a_folder_is_no_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dependency-cruiser's default severity is `warn`; a folder named like a config is not one."""
    (tmp_path / ".dependency-cruiser.d").mkdir()
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")
    assert run_extras(tmp_path, "typescript", _Executor()) == []

    (tmp_path / ".dependency-cruiser.json").write_text("{}\n", encoding="utf-8")
    unnamed = '{"summary": {"violations": [{"from": "a.ts", "to": "b.ts", "rule": {}}]}}'

    [run] = run_extras(tmp_path, "typescript", _Executor(unnamed, exit_code=1))

    assert [v.code for v in run.violations] == ["dependency-cruiser:unnamed"]
