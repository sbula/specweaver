# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""May this step change this path? The project's doc policy answers, after the built-in rules.

Proves: C-EXEC-08 FR-2, FR-4, FR-5, FR-6, NFR-3, NFR-4

`keep` lets the change stand, `refuse` keeps it out, `task` leaves it to the task's own list.

| Bucket | Case |
|---|---|
| Happy | an open path is kept; a step path is kept for its step |
| Boundary | the last matching rule wins, both ways; `*` stays in one folder, `**` spans folders |
| Degradation | no policy: `README.md` and `docs/**` refused, any other path left to the task |
| Hostile | another step is refused a step path; a rule naming only one folder leaves README and the rest of `docs/` refused; no rule opens `.specweaver/`, `context.yaml`, `.env` or `.git` |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.doc_policy import DocPolicy, DocRule
from specweaver.sandbox.security import doc_access


def _policy(*rules: DocRule) -> DocPolicy:
    return DocPolicy(rule=list(rules))


_GUIDES = DocRule(paths=["docs/user_guides/**"], access="open")
_API = DocRule(paths=["docs/api/**"], access="step", steps=["update_api_docs"])


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("README.md", "refuse"),
        ("readme.MD", "refuse"),
        ("docs/roadmap/x.md", "refuse"),
        ("src/app.py", "task"),
    ],
)
def test_without_a_policy_today_s_rule_holds(path: str, expected: str) -> None:
    assert doc_access(DocPolicy(), path, step="generate_code") == expected


def test_an_open_path_is_kept() -> None:
    assert doc_access(_policy(_GUIDES), "docs/user_guides/setup.md", step="any") == "keep"


def test_a_step_path_is_kept_for_its_step_only() -> None:
    policy = _policy(_API)

    assert doc_access(policy, "docs/api/v1.md", step="update_api_docs") == "keep"
    assert doc_access(policy, "docs/api/v1.md", step="generate_code") == "refuse"
    assert doc_access(policy, "docs/api/v1.md", step=None) == "refuse"


def test_a_rule_for_one_folder_leaves_the_rest_protected() -> None:
    policy = _policy(_GUIDES)

    assert doc_access(policy, "README.md", step="any") == "refuse"
    assert doc_access(policy, "docs/roadmap/plan.md", step="any") == "refuse"


def test_the_last_matching_rule_wins_both_ways() -> None:
    opened_then_closed = _policy(
        DocRule(paths=["docs/**"], access="open"),
        DocRule(paths=["docs/roadmap/**"], access="human"),
    )
    closed_then_opened = _policy(
        DocRule(paths=["docs/roadmap/**"], access="human"),
        DocRule(paths=["docs/**"], access="open"),
    )

    assert doc_access(opened_then_closed, "docs/roadmap/plan.md", step="s") == "refuse"
    assert doc_access(opened_then_closed, "docs/guide.md", step="s") == "keep"
    assert doc_access(closed_then_opened, "docs/roadmap/plan.md", step="s") == "keep"


def test_a_project_rule_may_open_the_readme() -> None:
    assert (
        doc_access(_policy(DocRule(paths=["README.md"], access="open")), "README.md", step="s")
        == "keep"
    )


def test_one_star_stays_in_one_folder() -> None:
    policy = _policy(DocRule(paths=["docs/*.md"], access="open"))

    assert doc_access(policy, "docs/guide.md", step="s") == "keep"
    assert doc_access(policy, "docs/deep/guide.md", step="s") == "refuse"


@pytest.mark.parametrize(
    "path", [".specweaver/x.toml", "pkg/context.yaml", ".env", ".git/config", "pkg/.ENV"]
)
def test_no_rule_opens_a_protected_file(path: str) -> None:
    everything = _policy(DocRule(paths=["**"], access="open"))

    assert doc_access(everything, path, step="s") == "refuse"
