# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The deployment image declares what an operator depends on.

Proves: D-EXEC-01 FR-1, D-EXEC-01 FR-2, D-EXEC-01 FR-3, D-EXEC-01 FR-4, D-EXEC-01 FR-5

`D-EXEC-01` shipped with no design document, so nothing could be uncited and the capability scored
perfectly by having nothing to score. The design was written from what ships; these are its claims.

**No image is built here.** A real build pulls a base image, installs apt packages and resolves the
whole dependency set — a CI job, not something to run on every commit. What is pinned is the
*contract the image declares*: the directives an operator relies on, so dropping the non-root user or
the healthcheck fails here instead of in production.

That distinction is the point. Asserting the file merely "mentions podman" would pass any file; each
assertion below names a directive and what breaks without it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTAINERFILE = REPO_ROOT / "Containerfile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "container.yml"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def containerfile() -> str:
    assert CONTAINERFILE.is_file(), f"the deployment image has no {CONTAINERFILE.name}"
    return CONTAINERFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow() -> str:
    assert WORKFLOW.is_file(), "nothing publishes the image"
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_container_serves_by_default(containerfile: str) -> None:
    """FR-1. `podman run <image>` with no arguments must serve, or it is not one command."""
    command = re.search(r"^CMD \[(.+)\]", containerfile, re.M)

    assert command is not None, "the image declares no default command"
    assert "serve" in command.group(1), command.group(1)


def test_the_served_port_is_exposed(containerfile: str) -> None:
    """FR-1. A port nothing declares is a port an operator has to discover by reading the file."""
    assert re.search(r"^EXPOSE 8000$", containerfile, re.M), containerfile


def test_state_resolves_through_the_data_dir(containerfile: str) -> None:
    """FR-2. Without this the state lands under a home directory that a replaced container loses."""
    assert re.search(r"^ENV SPECWEAVER_DATA_DIR=/data/", containerfile, re.M), containerfile


def test_the_image_does_not_run_as_root(containerfile: str) -> None:
    """FR-3. A root container writing into a mounted host project is the failure this prevents."""
    users = re.findall(r"^USER (\S+)", containerfile, re.M)

    assert users, "the image never leaves root"
    assert users[-1] not in ("root", "0", "0:0"), users


def test_the_unprivileged_user_is_set_before_the_entrypoint(containerfile: str) -> None:
    """A `USER` after `ENTRYPOINT` is decoration — the entrypoint still starts as root."""
    lines = containerfile.splitlines()
    user_at = max(i for i, line in enumerate(lines) if line.startswith("USER "))
    entry_at = max(i for i, line in enumerate(lines) if line.startswith("ENTRYPOINT"))

    assert user_at < entry_at, f"USER at line {user_at}, ENTRYPOINT at {entry_at}"


def test_the_healthcheck_asks_the_api_not_the_process(containerfile: str) -> None:
    """FR-4. A process check reports healthy while the API returns 500 to every caller."""
    # Anchored to line start: the file also says "required by HEALTHCHECK" in a comment, and an
    # unanchored match reads that instead and then asserts about the apt-get line below it.
    check = re.search(r"^HEALTHCHECK(.+?)(?=\n[A-Z]+ |\Z)", containerfile, re.S | re.M)

    assert check is not None, "the image declares no healthcheck"
    assert "/healthz" in check.group(1), check.group(1)


def test_the_image_is_published_from_a_tag(workflow: str) -> None:
    """FR-5. Publishing on every push means the tag says nothing about what is inside."""
    assert "tags: ['v*']" in workflow or 'tags: ["v*"]' in workflow, workflow[:400]


def test_the_image_is_published_to_the_registry_the_docs_name(workflow: str) -> None:
    assert "ghcr.io" in workflow
