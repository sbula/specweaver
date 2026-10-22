# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`scripts/commit_gated.py`: commit only after the full suite, `cb` and `doc` pass.

| Bucket | Case |
|---|---|
| Happy | all three gates pass → the named paths are staged and committed with the message |
| Boundary | a gate fails → nothing is staged; its whole output is shown, not a summary |
| Degradation | nothing ends up staged → no empty commit |
| Hostile | the mutation ledger, or work already staged outside the named paths, is refused |
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def cg() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "commit_gated", REPO_ROOT / "scripts" / "commit_gated.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["commit_gated"] = module
    spec.loader.exec_module(module)
    return module


class FakeRun:
    """Records every command; answers from a table keyed by the command's first distinct words."""

    def __init__(
        self,
        fail: str = "",
        staged_before: str = "",
        staged_after: str = "a.md",
        git_fail: str = "",
    ) -> None:
        self.fail = fail
        self.git_fail = git_fail
        self.staged = [staged_before, staged_after]
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(
        self, cmd: list[str], stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, stdin))
        joined = " ".join(cmd)
        if "diff --cached --name-only" in joined:
            return subprocess.CompletedProcess(cmd, 0, self.staged.pop(0) + "\n", "")
        for gate in ("pytest", "quality.py cb", "quality.py doc"):
            if gate in joined:
                code = 1 if self.fail == gate else 0
                out = f"{gate} line 1\n{gate} line 2\n{gate} last line\n"
                return subprocess.CompletedProcess(cmd, code, out, "")
        if self.git_fail and joined.startswith(self.git_fail):
            return subprocess.CompletedProcess(cmd, 1, "", f"{self.git_fail}: refused by a hook\n")
        if joined.startswith("git log"):
            return subprocess.CompletedProcess(cmd, 0, "abc1234 the message\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def ran(self, fragment: str) -> bool:
        return any(fragment in " ".join(cmd) for cmd, _ in self.calls)


class TestCommitGated:
    def test_green_gates_stage_the_paths_and_commit_the_message(self, cg: ModuleType) -> None:
        run = FakeRun()
        assert cg.commit("docs: a message", ["a.md"], run) == 0
        assert run.ran("git add -A -- a.md")
        commit = [(c, s) for c, s in run.calls if c[:2] == ["git", "commit"]]
        assert commit and commit[0][1] == "docs: a message"

    @pytest.mark.parametrize("gate", ["pytest", "quality.py cb", "quality.py doc"])
    def test_a_failing_gate_stages_nothing_and_shows_its_whole_output(
        self, cg: ModuleType, gate: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = FakeRun(fail=gate)
        assert cg.commit("docs: m", ["a.md"], run) == 1
        assert not run.ran("git add")
        assert not run.ran("git commit")
        out = capsys.readouterr().out
        assert f"{gate} line 1" in out
        assert f"{gate} last line" in out

    def test_the_gates_run_in_order_and_stop_at_the_first_red(self, cg: ModuleType) -> None:
        run = FakeRun(fail="pytest")
        cg.commit("docs: m", ["a.md"], run)
        assert not run.ran("quality.py")

    def test_nothing_staged_makes_no_commit(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = FakeRun(staged_after="")
        assert cg.commit("docs: m", ["a.md"], run) == 1
        assert not run.ran("git commit")
        assert "nothing staged" in capsys.readouterr().out

    def test_the_mutation_ledger_is_never_committed(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = FakeRun(staged_after="a.md\nscripts/baselines/mutation_findings.json")
        assert cg.commit("docs: m", ["."], run) == 1
        assert not run.ran("git commit")
        assert run.ran("git restore --staged -- scripts/baselines/mutation_findings.json")
        assert "mutation_findings.json" in capsys.readouterr().out

    def test_work_already_staged_elsewhere_is_refused_before_the_gates(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = FakeRun(staged_before="other.py")
        assert cg.commit("docs: m", ["a.md"], run) == 1
        assert not run.ran("pytest")
        assert "already staged" in capsys.readouterr().out

    def test_work_already_staged_inside_the_named_paths_is_fine(self, cg: ModuleType) -> None:
        run = FakeRun(staged_before="docs/a.md")
        assert cg.commit("docs: m", ["docs"], run) == 0

    @pytest.mark.parametrize(("message", "paths"), [("", ["a.md"]), ("  ", ["a.md"]), ("m", [])])
    def test_an_empty_message_or_no_paths_is_refused(
        self, cg: ModuleType, message: str, paths: list[str]
    ) -> None:
        run = FakeRun()
        assert cg.commit(message, paths, run) == 2
        assert run.calls == []

    def test_main_reads_the_message_and_paths_from_argv(
        self, cg: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[tuple[str, list[str]]] = []
        monkeypatch.setattr(cg, "commit", lambda m, p, run: seen.append((m, p)) or 0)
        assert cg.main(["docs: m", "a.md", "b.md"]) == 0
        assert seen == [("docs: m", ["a.md", "b.md"])]

    def test_main_with_no_arguments_is_a_usage_error(self, cg: ModuleType) -> None:
        assert cg.main([]) == 2

    @pytest.mark.parametrize("step", ["git add", "git commit"])
    def test_a_failing_git_step_is_a_failure_not_a_success(
        self, cg: ModuleType, step: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = FakeRun(git_fail=step)
        assert cg.commit("docs: m", ["a.md"], run) == 1
        out = capsys.readouterr().out
        assert "refused by a hook" in out
        assert "abc1234" not in out

    def test_a_missing_path_variable_does_not_crash(
        self, cg: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PATH", raising=False)
        monkeypatch.setattr(cg.subprocess, "run", lambda *a, **k: k["env"]["PATH"])
        assert str(cg.REPO_ROOT / ".venv" / "bin") in cg.run_in_repo(["true"])
