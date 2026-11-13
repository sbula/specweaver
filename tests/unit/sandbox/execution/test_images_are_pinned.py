# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every container image is pinned by tag and digest, and CI pulls exactly those.

A moving tag changes under us: `rust:1-slim` moved to 1.100.0 on 2026-11-12, and CI went red on a
commit that changed only docs (`91675641`). A pin changes only in a commit that means to change it.

**What this guard checks, and where.** This file checks the FORMAT, everywhere it runs, CI
included: each reference has a tag and `@sha256:` with 64 hex digits, and the CI pull step lists
exactly the pinned references. It cannot see whether a digest is the multi-arch index or one
platform's manifest; a platform digest would pass here and break the product on ARM (the GB10).
That is checked by `tests/integration/sandbox/execution/test_image_pins_are_multi_arch.py`, which
reads the manifest the engine stored when it pulled: on CI after the pull step, locally after
`podman pull`. Neither check uses the network.

| Bucket | Case |
|---|---|
| Happy | every reference in `src/`, `tests/`, the workflows and the recipes is pinned |
| Boundary | a recipe's stage name and `${ARG}` are not images; our own published image is an output |
| Degradation | a recipe line `FROM` with `--platform` is still read |
| Hostile | a moving tag, a digest with no tag, a short digest and a short name in a recipe all fail |
"""

from __future__ import annotations

import pytest
import yaml

from tests.image_pins import PINNED, ROOT, image_refs, recipe_sources, refs_in

# Built at run time, so the scanner never finds these samples in this file.
_HUB = "docker.io" + "/library"
_UV = "ghcr.io" + "/astral-sh/uv:latest"


def test_every_image_reference_is_pinned_by_tag_and_digest() -> None:
    refs = image_refs()
    loose = {ref: files for ref, files in refs.items() if not PINNED.match(ref)}

    assert refs, "the scanner found no image at all, so it cannot be looking"
    assert loose == {}, "pin each by tag and multi-arch index digest; see subprocess_execution.md"


def test_ci_pulls_exactly_the_pinned_images() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8"))
    (step,) = [s for s in workflow["jobs"]["gate"]["steps"] if s.get("name", "").startswith("Pull")]
    pulled = set(refs_in(step["run"]))

    assert pulled == set(image_refs())


@pytest.mark.parametrize(
    "ref",
    [
        f"{_HUB}/rust:1-slim",
        f"{_HUB}/rust@sha256:{'a' * 64}",
        f"{_HUB}/rust:1-slim@sha256:{'a' * 12}",
    ],
)
def test_a_loose_reference_fails(ref: str) -> None:
    (found,) = refs_in(f'image = "{ref}"')
    assert not PINNED.match(found)


def test_a_pinned_reference_passes() -> None:
    (found,) = refs_in(f"{_HUB}/rust:1.100.0-slim@sha256:{'a' * 64}")
    assert PINNED.match(found)


def test_a_recipe_names_its_sources_but_not_its_stages_or_args() -> None:
    recipe = (
        f"FROM {_HUB}/python:3.13-slim AS base\n"
        "FROM base\n"
        "ARG PY_BASE\n"
        "FROM ${PY_BASE}\n"
        "FROM --platform=linux/arm64 python:3.13-slim\n"
        f"COPY --from={_UV} /uv /bin/\n"
    )

    assert recipe_sources(recipe) == [
        f"{_HUB}/python:3.13-slim",
        "python:3.13-slim",
        _UV,
    ]


def test_a_short_name_in_a_recipe_is_not_pinned() -> None:
    (source,) = recipe_sources("FROM python:3.13-slim\n")
    assert not PINNED.match(source)


def test_our_published_image_is_not_counted() -> None:
    assert refs_in("tags: ghcr.io/sbula/specweaver:latest") == []


def test_a_digest_that_is_not_hex_fails() -> None:
    assert not PINNED.match(f"x/y:1@sha256:{'g' * 64}")
