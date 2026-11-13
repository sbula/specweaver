# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every GitHub Action a workflow uses is pinned by commit, and CI's uv is the pinned uv.

`actions/checkout@v5` is a moving tag: whoever controls the action's repository decides what runs
in our CI next time, with our token. A commit SHA changes only in a commit that means to change it.
The exact release it came from stays beside it as a comment, so a reader sees the version.

The SHA is the commit the tag points at — for an annotated tag the peeled `^{}` line of
`git ls-remote --tags`, never the tag object. This test checks the format; it cannot ask GitHub
what a SHA is, because the suite uses no network. The procedure is in
`docs/dev_guides/subprocess_execution.md`.

| Bucket | Case |
|---|---|
| Happy | every `uses:` in `.github/workflows/` is `owner/repo@<40 hex>  # vX.Y.Z` |
| Boundary | setup-uv installs the exact uv version the recipes copy from the pinned uv image |
| Degradation | — a format check has no dependency to fail |
| Hostile | a major tag, a short SHA, a branch, and a SHA with a moving-tag comment all fail |
"""

from __future__ import annotations

import re

import pytest
import yaml

from tests.image_pins import ROOT

_WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
_USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$", re.MULTILINE)
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_RELEASE = re.compile(r"^\s*#\s*v\d+\.\d+\.\d+\s*$")


def loose_uses(text: str) -> list[str]:
    """Every `uses:` line not pinned to a commit with its exact release in a comment."""
    return [
        f"{ref}{rest}"
        for ref, rest in _USES.findall(text)
        if not (_PINNED.match(ref) and _RELEASE.match(rest))
    ]


def test_every_action_is_pinned_by_commit_with_its_release() -> None:
    found = {wf.name: _USES.findall(wf.read_text(encoding="utf-8")) for wf in _WORKFLOWS}
    loose = {name: loose_uses((ROOT / ".github/workflows" / name).read_text()) for name in found}

    assert sum(len(v) for v in found.values()) >= 5, "the scanner found too few actions to trust"
    assert {k: v for k, v in loose.items() if v} == {}


@pytest.mark.parametrize(
    "line",
    [
        "      - uses: actions/checkout@v5",
        "      - uses: actions/checkout@v5.1.0",
        "      - uses: actions/checkout@fbc6f39  # v5.1.0",
        "      - uses: actions/checkout@main  # v5.1.0",
        f"      - uses: actions/checkout@{'f' * 40}  # v5",
        f"      - uses: actions/checkout@{'f' * 40}",
    ],
)
def test_a_loose_action_fails(line: str) -> None:
    assert loose_uses(line) != []


def test_a_pinned_action_passes() -> None:
    assert loose_uses(f"      - uses: actions/checkout@{'f' * 40}  # v5.1.0") == []


def _uv_in_recipes() -> set[str]:
    recipes = [
        ROOT / "Containerfile",
        ROOT / "src/specweaver/sandbox/execution/Containerfile.sandbox",
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in recipes)
    return set(re.findall(r"COPY --from=ghcr\.io/astral-sh/uv:(\d+\.\d+\.\d+)@", text))


def test_ci_installs_the_uv_the_recipes_pin() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8"))
    (step,) = [s for s in workflow["jobs"]["gate"]["steps"] if "setup-uv" in s.get("uses", "")]

    assert len(_uv_in_recipes()) == 1, "the two recipes pin different uv versions"
    assert str(step["with"].get("version")) in _uv_in_recipes()
