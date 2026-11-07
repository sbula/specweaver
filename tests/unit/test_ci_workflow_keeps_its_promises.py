# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The CI workflow keeps the promises TECH-094 made, and never calls a real model.

Proves: TECH-094 FR-1, FR-2, FR-3, FR-6, FR-7

Each promise is one edit away from being lost, and a lost one passes silently: CI stays green while
it calls a paid model, tests less, or reaches a secret. These assertions are the alarm.

| Bucket | Case |
|---|---|
| Happy | the workflow runs on push to `main` and on every pull request, the suite, `cb` and `doc`, on 3.11 and 3.14 |
| Boundary | jobs stop within 30 minutes; a newer push cancels the older run |
| Degradation | the token can only read; the checkout has the full history for `--base` |
| Hostile | a planted secret, key name, `-m live`, `scripts/live.py` or wider permission is caught |
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "tests.yml"
_FORBIDDEN = (
    re.compile(r"secrets\."),
    re.compile(r"[A-Z0-9_]*API_KEY"),
    re.compile(r"SPECWEAVER_LIVE_KEYS"),
    re.compile(r"-m\s+['\"]?[^'\"\n]*\b(live|toolchain)\b"),
    re.compile(r"scripts/(live|toolchain)\.py"),
)


def _load(text: str) -> dict[str, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(text)
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    if True in loaded:
        loaded["on"] = loaded.pop(True)
    return loaded


def _runs(workflow: dict[str, Any]) -> list[str]:
    return [
        step.get("run", "")
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "run" in step
    ]


def _top_level(workflow: dict[str, Any]) -> list[str]:
    broken = []
    triggers = workflow.get("on", {})
    if "main" not in (triggers.get("push") or {}).get("branches", []):
        broken.append("no push trigger for main")
    if "pull_request" not in triggers:
        broken.append("no pull_request trigger")
    if workflow.get("permissions") != {"contents": "read"}:
        broken.append("permissions are not exactly contents: read")
    if (workflow.get("concurrency") or {}).get("cancel-in-progress") is not True:
        broken.append("superseded runs are not cancelled")
    return broken


def _job(name: str, job: dict[str, Any]) -> list[str]:
    broken = []
    if not 0 < int(job.get("timeout-minutes", 0)) <= 30:
        broken.append(f"job {name} has no time limit of 30 minutes or less")
    versions = {str(v) for v in job.get("strategy", {}).get("matrix", {}).get("python", [])}
    if not {"3.11", "3.14"} <= versions:
        broken.append(f"job {name} does not run on 3.11 and 3.14")
    checkout = next(
        s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")
    )
    if checkout.get("with", {}).get("fetch-depth") != 0:
        broken.append(f"job {name} checks out a shallow history")
    return broken


def broken_promises(text: str) -> list[str]:
    """Every promise the workflow text breaks; empty when it keeps them all."""
    broken = [f"names {p.pattern}" for p in _FORBIDDEN if p.search(text)]
    workflow = _load(text)
    broken += _top_level(workflow)
    for name, job in workflow["jobs"].items():
        broken += _job(name, job)
    runs = "\n".join(_runs(workflow))
    broken += [
        f"never runs {needed}"
        for needed in ("pytest -n auto", "quality.py cb", "quality.py doc", "uv sync --locked")
        if needed not in runs
    ]
    return broken


def test_the_workflow_keeps_every_promise() -> None:
    assert broken_promises(_WORKFLOW.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("planted", "promise"),
    [
        ("      - run: echo ${{ secrets.GEMINI_API_KEY }}\n", "secrets"),
        ("      - run: uv run python -m pytest -m live\n", "live"),
        ("      - run: uv run python -m pytest -m 'live or not live'\n", "live"),
        ("      - run: uv run python scripts/toolchain.py\n", "toolchain"),
        ("      - run: export OPENAI_API_KEY=x\n", "API_KEY"),
    ],
)
def test_a_planted_model_call_is_caught(planted: str, promise: str) -> None:
    text = _WORKFLOW.read_text(encoding="utf-8").rstrip("\n") + "\n" + planted

    assert any(promise in b for b in broken_promises(text))


def test_wider_permissions_are_caught() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8").replace("contents: read", "contents: write")

    assert "permissions are not exactly contents: read" in broken_promises(text)


def test_dropping_a_python_version_is_caught() -> None:
    text = re.sub(r"[\"']?3\.11[\"']?,\s*", "", _WORKFLOW.read_text(encoding="utf-8"))

    assert any("3.11 and 3.14" in b for b in broken_promises(text))


def test_ci_pulls_every_image_a_container_test_waits_for() -> None:
    """Proves: TECH-094 FR-5 — a missing image skips the test, and on CI a skip fails the run."""
    module = _WORKFLOW.parents[2] / "tests/integration/sandbox/execution"
    text = (module / "test_container_executor_integration.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^(_[A-Z]+_IMAGE) = "([^"]+)"', text, re.MULTILINE))
    awaited = {constants[name] for name in re.findall(r"_image_available\((_[A-Z]+_IMAGE)\)", text)}
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    runs = "\n".join(run for run in _runs(_load(workflow)) if "podman pull" in run)

    assert len(awaited) == 3, awaited
    assert sorted(image for image in awaited if image not in runs) == []


def test_the_readme_shows_the_workflow_status() -> None:
    """Proves: TECH-094 FR-6"""
    readme = (_WORKFLOW.parents[2] / "README.md").read_text(encoding="utf-8")

    assert "actions/workflows/tests.yml/badge.svg" in readme.split("\n\n", 2)[1]
