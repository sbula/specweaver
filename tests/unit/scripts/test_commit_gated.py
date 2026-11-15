# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`scripts/commit_gated.py`: commit only after the full suite, `cb` and `doc` pass.

| Bucket | Case |
|---|---|
| Happy | all three gates pass → the named paths are staged and committed with the message |
| Boundary | a gate fails → nothing is staged; its whole output is shown, not a summary |
| Degradation | nothing ends up staged → no empty commit; a failing `git add` exits 1 and names the paths |
| Boundary | a deletion already staged (`git rm`) can be named: it is committed, not handed to `git add` |
| Hostile | the mutation ledger, or work already staged outside the named paths, is refused |

**Approvals claimed.** Before the commit, every `[agreed <date>]` tag on an added line is printed with
file, line and text, so the user sees which approvals a commit claims before pushing. A tag that
leaves one line and lands on another is printed as **moved**, with both rows: moving a tag can claim
approval for a different decision. Only files under `docs/` are reported: designs, ledgers and
stories hold approvals; a tag in a test or a code comment is data. A moved tag is printed as the tag
and the 60 characters before it, on its old line and its new line.

| Bucket | Case |
|---|---|
| Happy | an added tag is printed as added, with file, line and text |
| Boundary | a tag under `tests/` or `scripts/` is not reported; a moved tag shows its own context, not the row |
| Boundary | a tag moved in a file, across files, or kept on a reworded row is printed as moved, both rows shown |
| Degradation | no tag at all, or a tag only removed, prints "none" |
| Hostile | a `[agreed <date>]` placeholder is no tag; an added line that looks like a file header is content |
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
        diff: str = "",
        deleted: str = "",
    ) -> None:
        self.diff = diff
        self.deleted = deleted
        self.fail = fail
        self.git_fail = git_fail
        self.staged = [staged_before, staged_after]
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(
        self, cmd: list[str], stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, stdin))
        joined = " ".join(cmd)
        if "--diff-filter=D" in joined:
            return subprocess.CompletedProcess(cmd, 0, self.deleted + "\n", "")
        if "diff --cached --name-only" in joined:
            return subprocess.CompletedProcess(cmd, 0, self.staged.pop(0) + "\n", "")
        if "diff --cached -U0" in joined:
            return subprocess.CompletedProcess(cmd, 0, self.diff, "")
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

    def test_a_failing_git_add_names_the_paths(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run = FakeRun(git_fail="git add")
        assert cg.commit("docs: m", ["a.md", "b/c.py"], run) == 1
        assert "a.md b/c.py" in capsys.readouterr().out

    def test_a_staged_deletion_is_not_handed_to_git_add(self, cg: ModuleType) -> None:
        run = FakeRun(staged_before="gone.py", staged_after="a.md\ngone.py", deleted="gone.py")
        assert cg.commit("docs: m", ["a.md", "gone.py"], run) == 0
        assert run.ran("git add -A -- a.md")
        assert not run.ran("gone.py")

    def test_only_staged_deletions_named_skips_git_add(self, cg: ModuleType) -> None:
        run = FakeRun(staged_before="gone.py", staged_after="gone.py", deleted="gone.py")
        assert cg.commit("docs: m", ["gone.py"], run) == 0
        assert not run.ran("git add")

    def test_a_staged_deletion_commits_in_a_real_repo(
        self, cg: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def git(*args: str) -> str:
            return subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout

        (tmp_path / "gone.py").write_text("x\n", encoding="utf-8")
        (tmp_path / "a.md").write_text("a\n", encoding="utf-8")
        git("init", "-q")
        git("add", "-A")
        git("commit", "-q", "-m", "c")
        git("rm", "-q", "gone.py")
        (tmp_path / "a.md").write_text("b\n", encoding="utf-8")
        monkeypatch.setattr(cg, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(cg, "GATES", (("ok", ["true"]),))
        monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
        monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@t")
        monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
        monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@t")

        assert cg.commit("docs: m", ["a.md", "gone.py"], cg.run_in_repo) == 0
        assert git("show", "--name-status", "--format=", "HEAD").split() == [
            "M",
            "a.md",
            "D",
            "gone.py",
        ]
        assert git("status", "--porcelain") == ""

    def test_a_missing_path_variable_does_not_crash(
        self, cg: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PATH", raising=False)
        monkeypatch.setattr(cg.subprocess, "run", lambda *a, **k: k["env"]["PATH"])
        assert str(cg.REPO_ROOT / ".venv" / "bin") in cg.run_in_repo(["true"])


_TAG = "`[agreed 2026-11-13]`"
_OLD = "`[agreed 2026-11-11]`"


def _diff(*files: tuple[str, str]) -> str:
    """A `git diff -U0` text: one `(path, hunks)` per file, each hunk already in diff form."""
    return "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{hunks}"
        for path, hunks in files
    )


class TestApprovalsClaimed:
    def test_an_added_tag_is_reported_with_file_line_and_text(self, cg: ModuleType) -> None:
        diff = _diff(("docs/d.md", f"@@ -4,0 +5 @@\n+| FR-1 | no cap {_TAG} |\n"))
        assert cg.approvals_claimed(diff) == [
            ("added", None, ("docs/d.md", 5, f"| FR-1 | no cap {_TAG} |"))
        ]

    @pytest.mark.parametrize("path", ["tests/t.py", "scripts/s.py", "src/x.py", "README.md"])
    def test_a_tag_outside_docs_is_not_a_claim(self, cg: ModuleType, path: str) -> None:
        assert cg.approvals_claimed(_diff((path, f"@@ -0,0 +1 @@\n+x {_TAG}\n"))) == []

    def test_a_tag_moved_out_of_docs_is_not_a_claim(self, cg: ModuleType) -> None:
        diff = _diff(
            ("docs/a.md", f"@@ -2 +1,0 @@\n-x {_OLD}\n"),
            ("tests/b.py", f"@@ -0,0 +1 @@\n+y {_OLD}\n"),
        )
        assert cg.approvals_claimed(diff) == []

    def test_a_tag_moved_inside_a_file_is_reported_with_both_rows(self, cg: ModuleType) -> None:
        diff = _diff(
            (
                "docs/d.md",
                f"@@ -3 +2,0 @@\n-| FR-1 | old row {_OLD} |\n@@ -9,0 +9 @@\n+| FR-7 | other {_OLD} |\n",
            )
        )
        assert cg.approvals_claimed(diff) == [
            (
                "moved",
                ("docs/d.md", 3, f"| FR-1 | old row {_OLD} |"),
                ("docs/d.md", 9, f"| FR-7 | other {_OLD} |"),
            )
        ]

    def test_a_tag_moved_to_another_file_is_reported_as_moved(self, cg: ModuleType) -> None:
        diff = _diff(
            ("docs/a.md", f"@@ -2 +1,0 @@\n-x {_OLD}\n"),
            ("docs/b.md", f"@@ -0,0 +1 @@\n+y {_OLD}\n"),
        )
        (claim,) = cg.approvals_claimed(diff)
        assert claim == ("moved", ("docs/a.md", 2, f"x {_OLD}"), ("docs/b.md", 1, f"y {_OLD}"))

    def test_a_reworded_row_that_keeps_its_tag_is_reported_as_moved(self, cg: ModuleType) -> None:
        diff = _diff(
            ("docs/d.md", f"@@ -7 +7 @@\n-| FR-3 | cap of 5 {_OLD} |\n+| FR-3 | no cap {_OLD} |\n")
        )
        (claim,) = cg.approvals_claimed(diff)
        assert claim[0] == "moved"
        assert claim[1] == ("docs/d.md", 7, f"| FR-3 | cap of 5 {_OLD} |")
        assert claim[2] == ("docs/d.md", 7, f"| FR-3 | no cap {_OLD} |")

    def test_a_tag_from_a_deleted_file_names_the_old_file(self, cg: ModuleType) -> None:
        diff = (
            f"diff --git a/docs/gone.md b/docs/gone.md\n--- a/docs/gone.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-x {_OLD}\n"
            + _diff(("docs/new.md", f"@@ -0,0 +1 @@\n+y {_OLD}\n"))
        )
        (claim,) = cg.approvals_claimed(diff)
        assert claim == ("moved", ("docs/gone.md", 1, f"x {_OLD}"), ("docs/new.md", 1, f"y {_OLD}"))

    def test_one_removed_tag_pays_for_one_move_only(self, cg: ModuleType) -> None:
        diff = _diff(("docs/d.md", f"@@ -1 +1,2 @@\n-a {_OLD}\n+b {_OLD}\n+c {_OLD}\n"))
        assert [c[0] for c in cg.approvals_claimed(diff)] == ["moved", "added"]

    def test_two_tags_on_one_line_are_two_claims(self, cg: ModuleType) -> None:
        diff = _diff(("docs/d.md", f"@@ -0,0 +1 @@\n+a {_OLD} b {_TAG}\n"))
        assert [c[0] for c in cg.approvals_claimed(diff)] == ["added", "added"]

    @pytest.mark.parametrize(
        "hunks",
        [
            "@@ -1 +1 @@\n-plain\n+still plain\n",
            f"@@ -4 +3,0 @@\n-gone {_TAG}\n",
            "@@ -0,0 +1 @@\n+the marker needs `[agreed <date>]`\n",
        ],
    )
    def test_no_tag_a_removed_tag_or_a_placeholder_claims_nothing(
        self, cg: ModuleType, hunks: str
    ) -> None:
        assert cg.approvals_claimed(_diff(("docs/d.md", hunks))) == []

    def test_an_added_line_that_looks_like_a_header_is_content(self, cg: ModuleType) -> None:
        diff = _diff(("docs/d.md", f"@@ -0,0 +1,2 @@\n+++ b/evil.md\n+z {_TAG}\n"))
        assert cg.approvals_claimed(diff) == [("added", None, ("docs/d.md", 2, f"z {_TAG}"))]

    def test_the_commit_prints_the_claims_before_committing(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        old = f"@@ -3 +2,0 @@\n-| FR-1 | {_OLD} |\n"
        new = f"@@ -0,0 +1,2 @@\n+| FR-2 | {_TAG} |\n+| FR-9 | {_OLD} |\n"
        run = FakeRun(diff=_diff(("docs/a.md", old), ("docs/b.md", new)))
        assert cg.commit("docs: m", ["docs/a.md", "docs/b.md"], run) == 0
        out = capsys.readouterr().out
        assert "approvals claimed in this commit: 2" in out
        assert f"added  docs/b.md:1  | FR-2 | {_TAG} |" in out
        assert f"moved  {_OLD[1:-1]}" in out
        assert "  from docs/a.md:3  …| FR-1 |" in out
        assert "  to   docs/b.md:2  …| FR-9 |" in out
        diff_at = next(i for i, (c, _) in enumerate(run.calls) if "-U0" in c)
        commit_at = next(i for i, (c, _) in enumerate(run.calls) if c[:2] == ["git", "commit"])
        assert diff_at < commit_at

    def test_a_moved_tag_shows_the_60_characters_before_it_not_the_row(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        long = "x" * 100
        old = f"@@ -7 +7 @@\n-| FR-3 | {long} old words {_OLD}; then more {long} |\n"
        new = f"+| FR-3 | {long} new words {_OLD}; then more {long} |\n"
        assert (
            cg.commit("docs: m", ["docs/d.md"], FakeRun(diff=_diff(("docs/d.md", old + new)))) == 0
        )
        out = capsys.readouterr().out
        (before,) = [ln for ln in out.splitlines() if "from docs/d.md:7" in ln]
        (after,) = [ln for ln in out.splitlines() if "to   docs/d.md:7" in ln]
        assert before.endswith("old words") and after.endswith("new words")
        assert len(before.split("  …")[1]) <= 60
        assert "then more" not in out

    def test_a_commit_with_no_tag_says_none(
        self, cg: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cg.commit("docs: m", ["docs/a.md"], FakeRun()) == 0
        assert "approvals claimed in this commit: none" in capsys.readouterr().out
