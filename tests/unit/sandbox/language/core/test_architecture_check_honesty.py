# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No language runner may answer an architecture question it never asked.

Proves: TECH-064 FR-2, TECH-064 FR-3

Three delivered paths returned `ArchitectureRunResult(violation_count=0, violations=[])` from a body
whose docstring said *"Deferred"*. "Deferred" is honest in a docstring and dishonest as a return
value: the caller receives the same object it would get from a clean check, and
`qa_runner/core/atom.py` turns it into `SUCCESS — "No architectural violations."`

This is a guard against the **class**, not the three instances. The same shape appeared three times
independently, so a fourth language will be added the same way unless something asks the question of
every runner at once.

The rule is deliberately weak on purpose: a runner may perform the check, or it may decline — it
just may not decline **silently**. Whether declining should also fail the pipeline step is a product
decision `TECH-064` records and does not take: "fail the step" and "skip the step loudly" are
different products, and this test would pass under either.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.rust.runner import RustRunner
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

if TYPE_CHECKING:
    from specweaver.sandbox.qa_runner.core.interface import QARunnerInterface

#: Every language runner the QA layer can dispatch to. Listed rather than discovered, so adding a
#: language is a deliberate edit here — the point of the guard is that a new runner cannot arrive
#: unnoticed.
RUNNERS: tuple[type[QARunnerInterface], ...] = (
    PythonQARunner,
    JavaRunner,
    TypeScriptRunner,
    KotlinRunner,
    RustRunner,
)


def _body_without_docstring(runner_cls: type, name: str) -> list[ast.stmt]:
    """The statements of `runner_cls.name`, with a leading docstring dropped.

    The whole MODULE is parsed and the method found inside it, rather than dedenting
    `inspect.getsource` of the method. `JavaRunner` embeds a Java source template in an f-string
    whose lines start at column 0, so the common indent is "" and dedent leaves the `def` indented —
    which raises `IndentationError` and would have turned this guard into a collection error.
    """
    tree = ast.parse(Path(inspect.getfile(runner_cls)).read_text(encoding="utf-8"))
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name
    )
    body = func.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return body


def _sets_a_note(node: ast.Return) -> bool:
    """True when the returned call passes a non-empty `note=`."""
    call = node.value
    if not isinstance(call, ast.Call):
        return False
    return any(
        kw.arg == "note" and not (isinstance(kw.value, ast.Constant) and not kw.value.value)
        for kw in call.keywords
    )


@pytest.mark.parametrize("runner_cls", RUNNERS, ids=lambda c: c.__name__)
def test_a_runner_that_declines_the_check_says_so(runner_cls: type) -> None:
    """A body that returns a clean result without looking must set `note`.

    Detected structurally rather than by running the check, because running it needs a real project
    and a real toolchain per language — and the defect is in the shape of the code, not in its
    behaviour on any one input.

    **An unconditional return is the discriminator, not the returned value.** A first draft matched
    any empty result and flagged `JavaRunner`, whose `if not forbids: return ...` is the true answer
    when a project declares no boundaries — it looked, and there was nothing to violate. Only a body
    that is one bare `return` declined without looking.
    """
    body = _body_without_docstring(runner_cls, "run_architecture_check")
    declines_outright = len(body) == 1 and isinstance(body[0], ast.Return)

    assert not declines_outright or _sets_a_note(body[0]), (
        f"{runner_cls.__name__}.run_architecture_check is a single unconditional return: it "
        "examines nothing and says nothing. A caller cannot tell that apart from a check that ran "
        "and found nothing. Set `note=` on the result to say the check did not run."
    )


@pytest.mark.parametrize("runner_cls", RUNNERS, ids=lambda c: c.__name__)
def test_every_runner_still_offers_the_check(runner_cls: type) -> None:
    """The premise. If the method were renamed, the guard above would vacuously pass."""
    assert callable(getattr(runner_cls, "run_architecture_check", None))


class TestTheAtomSurfacesTheDecline:
    """The note has to reach the caller, or setting it changes nothing anyone sees.

    Proves: TECH-064 FR-3

    `qa_runner/core/atom.py` reported `SUCCESS — "No architectural violations."` for both stubs.
    That message, not the dataclass, is what a reader acts on: adding a field the atom ignores would
    have closed the ticket on paper and left the lie in place.
    """

    def _run(self, note: str) -> object:
        from specweaver.commons.qa import ArchitectureRunResult
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        class _Runner:
            def run_architecture_check(self, target: str, dal_level: object = None) -> object:
                return ArchitectureRunResult(violation_count=0, violations=[], note=note)

        atom = QARunnerAtom.__new__(QARunnerAtom)
        atom._runner = _Runner()  # type: ignore[attr-defined]
        return atom._intent_run_architecture({"target": "src"})  # type: ignore[attr-defined]

    def test_a_declined_check_does_not_claim_a_clean_verdict(self) -> None:
        result = self._run("Kotlin architecture checks are not implemented.")

        assert "No architectural violations" not in result.message
        assert "did not run" in result.message

    def test_a_real_clean_verdict_still_reads_as_one(self) -> None:
        """The honest empty result must survive, or the fix just inverts the defect."""
        result = self._run("")

        assert result.message == "No architectural violations."

    def test_the_note_is_exported_for_a_machine_reader(self) -> None:
        """A pipeline step reads exports, not prose."""
        result = self._run("Rust architecture checks are not implemented.")

        assert result.exports["note"].startswith("Rust")
