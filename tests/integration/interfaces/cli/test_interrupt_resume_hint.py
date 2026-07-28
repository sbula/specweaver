# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Ctrl-C message must name a run the user can actually resume (INT-US-21 SF-03 CB-2, R-13).

`sw run` printed *"Run state saved. Resume with: sw run --resume"* — with no id. The claim was
true (the runner persists the run in a `finally:` block) but the instruction was unfollowable,
because `except KeyboardInterrupt` sits outside `_execute_run`, which has already raised, and the
run id lived only inside `PipelineRunner.run()`'s frame.

The `resume` command already got this right (`cli.py`, "Resume with: sw resume <id>"), which is how
the divergence with the park message (`display.py`, "sw run --resume <id>") came to light.

CB-2 deliberately does NOT force those two into one wording. Both are real commands; `sw resume`
has its own help text, and telling a user interrupted during `sw resume` to type `sw run --resume`
would be the worse instruction. The enforced contract is the narrower one the defect actually
names: **every resume instruction must carry a run id.**
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

FAKE_RUN_ID = "9f8e7d6c-1111-2222-3333-444455556666"


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    specs.mkdir(parents=True)
    (specs / "greeter_spec.md").write_text("# Greeter\n\n## 1. Purpose\n\nGreets.\n", "utf-8")
    return tmp_path


def _interrupt_mid_run(project: Path):
    """Invoke `sw run` with the pipeline interrupted after the run exists."""

    async def _raise_after_registering(self, parent_run_id=None):
        self._current_run_id = FAKE_RUN_ID
        raise KeyboardInterrupt

    with patch(
        "specweaver.core.flow.engine.runner.PipelineRunner.run", new=_raise_after_registering
    ):
        return runner.invoke(
            app,
            ["run", "validate_only", str(project / "specs" / "greeter_spec.md")],
            catch_exceptions=False,
        )


class TestInterruptHintNamesTheRun:
    def test_the_message_carries_the_run_id(self, project: Path) -> None:
        result = _interrupt_mid_run(project)

        assert FAKE_RUN_ID in result.output.replace("\n", ""), result.output

    def test_the_hint_is_a_command_the_user_can_paste(self, project: Path) -> None:
        """An id printed without the command, or a command without the id, is still unfollowable."""
        flattened = re.sub(r"\s+", " ", result_output := _interrupt_mid_run(project).output)

        assert "--resume" in flattened, result_output
        assert re.search(r"--resume\s+" + re.escape(FAKE_RUN_ID), flattened), result_output

    def test_the_interrupt_still_exits_130(self, project: Path) -> None:
        """SIGINT convention — the message change must not alter the exit contract."""
        assert _interrupt_mid_run(project).exit_code == 130

    def test_the_state_saved_claim_is_still_made(self, project: Path) -> None:
        flattened = re.sub(r"\s+", " ", _interrupt_mid_run(project).output).lower()

        assert "saved" in flattened


class TestEveryResumeHintNamesARun:
    """The contract is that a hint is *followable*, not that one command form wins.

    An earlier version of this test banned the string `sw resume ` outright, on the theory that
    the park message (`sw run --resume <id>`) and the resume command's interrupt hint
    (`sw resume <id>`) had to agree. That over-reached: BOTH are real commands, `sw resume` has its
    own help text and usage example, and telling a user interrupted during `sw resume` to type
    `sw run --resume` is the less natural instruction. The test also tripped on its own explanatory
    docstring. The defect R-13 actually names is narrower and is what is asserted here — a resume
    instruction that cannot be followed because it carries no run id.
    """

    def test_no_resume_instruction_is_printed_without_an_id(self) -> None:
        """Scanned via AST, not raw lines.

        A line-based version tripped twice on prose — once on this class's own docstring and once
        on a code comment quoting the old message. Comments and docstrings are not instructions the
        user ever sees; the AST drops comments entirely, so only real string literals are examined.
        """
        import ast
        import inspect

        from specweaver.core.flow.engine import display
        from specweaver.core.flow.interfaces import cli

        offenders: list[str] = []
        for module in (display, cli):
            tree = ast.parse(inspect.getsource(module))

            # Adjacent literals concatenate, so an f-string's plain fragments appear as Constant
            # nodes of their own. Judging those individually reports the half without the `{id}`
            # as an offender when the joined message is fine — so exclude them and judge the
            # JoinedStr as a whole.
            inside_fstring = {
                id(v)
                for node in ast.walk(tree)
                if isinstance(node, ast.JoinedStr)
                for v in node.values
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    text = "".join(
                        v.value
                        for v in node.values
                        if isinstance(v, ast.Constant) and isinstance(v.value, str)
                    )
                    interpolates = any(isinstance(v, ast.FormattedValue) for v in node.values)
                    if "Resume with" in text and not interpolates:
                        offenders.append(text.strip())
                elif (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in inside_fstring
                    and "Resume with" in node.value
                    and "<run_id>" not in node.value
                ):
                    offenders.append(node.value.strip())

        assert not offenders, f"resume instruction(s) printed with no run id: {offenders}"

    def test_a_hint_that_does_name_a_run_is_still_present(self) -> None:
        """Guards the scan above against passing because every hint was deleted."""
        import inspect

        from specweaver.core.flow.engine import display

        assert "sw run --resume {" in inspect.getsource(display).replace("run.run_id", "run_id")


class TestTheTwoHintBranchesDiffer:
    """A known run is told how to resume; an unknown one is told how to find itself.

    Asserting only that each branch "contains what it should" would pass if both printed the same
    generic text, which would make the id-bearing branch pointless.
    """

    def _render(self, run_id: str | None) -> str:
        import io

        from rich.console import Console

        from specweaver.core.flow.interfaces import cli
        from specweaver.interfaces.cli import _core

        buffer = io.StringIO()
        original, _core.console = _core.console, Console(file=buffer, width=200)
        try:
            cli._print_resume_hint(run_id)
        finally:
            _core.console = original
        return re.sub(r"\s+", " ", buffer.getvalue()).strip()

    def test_the_known_run_branch_names_it(self) -> None:
        assert FAKE_RUN_ID in self._render(FAKE_RUN_ID)

    def test_the_unknown_run_branch_says_how_to_find_one(self) -> None:
        text = self._render(None)

        assert FAKE_RUN_ID not in text
        assert "sw runs" in text, text

    def test_the_two_branches_are_not_the_same_message(self) -> None:
        assert self._render(FAKE_RUN_ID) != self._render(None)
