# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What happens to one changed file: kept, kept as a proposal, or stripped.

Proves: C-EXEC-08 FR-8
Proves: C-EXEC-08 NFR-3

One decider for the task grant and the merge. `keep` lets the write stand; `propose` is a doc change
a rule refuses — the merge keeps it in `doc_updates.md`; `strip` is a change nobody may make.

| Bucket | Case |
|---|---|
| Happy | an open path, a step path for its step, a task file — all kept |
| Boundary | the root `doc_updates.md` kept in any case; one in a folder is judged like any path |
| Degradation | no policy: `README.md` and `docs/` proposed, a file outside the task stripped |
| Hostile | a protected file is stripped, never proposed, whatever a rule or the task says; another step, or no step, is refused a step path |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.doc_policy import DocPolicy, DocRule
from specweaver.sandbox.security import write_verdict

_NONE = DocPolicy()
_POLICY = DocPolicy(
    rule=[
        DocRule(paths=["docs/user_guides/**"], access="open"),
        DocRule(paths=["docs/api/**"], access="step", steps=["update_api_docs"]),
    ]
)
_TASK = ["src/greeter.py"]


@pytest.mark.parametrize(
    ("path", "step"),
    [
        ("docs/user_guides/a.md", None),
        ("docs/api/a.md", "update_api_docs"),
        ("src/greeter.py", "implement"),
    ],
)
def test_an_allowed_change_is_kept(path: str, step: str | None) -> None:
    assert write_verdict(_POLICY, path, step, _TASK) == "keep"


@pytest.mark.parametrize("path", ["doc_updates.md", "DOC_UPDATES.MD"])
def test_the_root_doc_updates_is_kept(path: str) -> None:
    assert write_verdict(_NONE, path, None, []) == "keep"


def test_doc_updates_in_docs_is_a_doc_change() -> None:
    assert write_verdict(_NONE, "docs/doc_updates.md", None, []) == "propose"


def test_doc_updates_in_src_is_judged_by_the_task() -> None:
    assert write_verdict(_NONE, "src/my_doc_updates.md", None, []) == "strip"


@pytest.mark.parametrize("path", ["README.md", "ReadMe.md", "docs/roadmap/x.md", "DOCS/guide.md"])
def test_without_a_policy_a_doc_change_is_proposed(path: str) -> None:
    assert write_verdict(_NONE, path, None, ["**"]) == "propose"


def test_a_file_outside_the_task_is_stripped() -> None:
    assert write_verdict(_POLICY, "src/other.py", "implement", _TASK) == "strip"


@pytest.mark.parametrize("step", ["other_step", None])
def test_another_step_proposes_on_a_step_path(step: str | None) -> None:
    assert write_verdict(_POLICY, "docs/api/a.md", step, ["**"]) == "propose"


@pytest.mark.parametrize(
    "path", [".env", "context.yaml", "src/context.yaml", ".git/config", ".SpecWeaver/s"]
)
def test_a_protected_file_is_stripped_whatever_opens_it(path: str) -> None:
    everything = DocPolicy(rule=[DocRule(paths=["**"], access="open")])

    assert write_verdict(everything, path, "any", ["**"]) == "strip"
    assert write_verdict(_NONE, path, None, []) == "strip"
