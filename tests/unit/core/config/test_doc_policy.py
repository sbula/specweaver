# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's `[docs]` section is read strictly; a broken rule stops the command, naming its line.

Proves: C-EXEC-08 FR-1, NFR-1

| Bucket | Case |
|---|---|
| Happy | rules and blocks are read as written |
| Boundary | no `[docs]` section is an empty policy; an error in the second rule names the second rule's line |
| Degradation | not applicable — the text is parsed, nothing is called |
| Hostile | an unknown key or access, a step rule without steps, steps on another access, a pattern leaving the project, a block name that is not a plain word: each refused |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.doc_policy import DocBlock, DocRule, parse_doc_policy
from specweaver.core.config.llm_settings import SettingsFileError

_FULL = """\
[llm]
private_only = false

[[docs.rule]]
paths = ["docs/user_guides/**"]
access = "open"

[[docs.rule]]
paths = ["docs/api/**"]
access = "step"
steps = ["update_api_docs"]

[[docs.block]]
file = "README.md"
name = "counts"
step = "update_counts"
"""


def test_rules_and_blocks_are_read_as_written() -> None:
    policy = parse_doc_policy(_FULL, "specweaver.toml")

    assert policy.rule == [
        DocRule(paths=["docs/user_guides/**"], access="open"),
        DocRule(paths=["docs/api/**"], access="step", steps=["update_api_docs"]),
    ]
    assert policy.block == [DocBlock(file="README.md", name="counts", step="update_counts")]


def test_no_section_is_an_empty_policy() -> None:
    policy = parse_doc_policy("[llm]\nprivate_only = false\n", "specweaver.toml")

    assert (policy.rule, policy.block) == ([], [])


def _refused(text: str) -> SettingsFileError:
    with pytest.raises(SettingsFileError) as caught:
        parse_doc_policy(text, "specweaver.toml")
    return caught.value


def test_an_error_in_the_second_rule_names_its_line() -> None:
    text = _FULL.replace('paths = ["docs/api/**"]', 'paths = ["../outside/**"]')

    error = _refused(text)

    assert error.key == "docs.rule.1.paths"
    assert error.line == 9


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        ('access = "open"', 'acess = "open"', "docs.rule.0.acess"),
        ('access = "open"', 'access = "everyone"', "docs.rule.0.access"),
        ('steps = ["update_api_docs"]', "", "docs.rule.1.steps"),
        ('access = "open"', 'access = "open"\nsteps = ["x"]', "docs.rule.0.steps"),
        ('"docs/user_guides/**"', '"/etc/**"', "docs.rule.0.paths"),
        ('"docs/user_guides/**"', '""', "docs.rule.0.paths"),
        ('name = "counts"', 'name = "counts --> <script>"', "docs.block.0.name"),
        ('file = "README.md"', 'file = "../README.md"', "docs.block.0.file"),
    ],
    ids=[
        "unknown-key",
        "unknown-access",
        "step-without-steps",
        "steps-on-open",
        "absolute",
        "empty",
        "block-name",
        "block-file",
    ],
)
def test_a_broken_entry_is_refused(old: str, new: str, key: str) -> None:
    assert _refused(_FULL.replace(old, new)).key == key
