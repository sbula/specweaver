# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

import pytest
from ruamel.yaml import YAML

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_context(
    directory: Path,
    *,
    name: str,
    level: str = "module",
    purpose: str = "Test module.",
    archetype: str = "pure-logic",
    consumes: list[str] | None = None,
    exposes: list[str] | None = None,
    forbids: list[str] | None = None,
    constraints: list[str] | None = None,
    operational: dict | None = None,
) -> Path:
    """Write a context.yaml to a directory."""
    directory.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "name": name,
        "level": level,
        "purpose": purpose,
        "archetype": archetype,
    }
    if consumes:
        data["consumes"] = consumes
    if exposes:
        data["exposes"] = exposes
    if forbids:
        data["forbids"] = forbids
    if constraints:
        data["constraints"] = constraints
    if operational:
        data["operational"] = operational
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.dump(data, directory / "context.yaml")
    return directory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def empty_project(tmp_path: Path) -> Path:
    """A project with no context.yaml files."""
    return tmp_path


@pytest.fixture()
def single_node(tmp_path: Path) -> Path:
    """A project with one module."""
    _write_context(tmp_path / "alpha", name="alpha", purpose="The only module.")
    return tmp_path


@pytest.fixture()
def linear_chain(tmp_path: Path) -> Path:
    """A -> B -> C (A consumes B, B consumes C)."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["c"])
    _write_context(tmp_path / "c", name="c", purpose="Leaf module.")
    return tmp_path


@pytest.fixture()
def diamond(tmp_path: Path) -> Path:
    """Diamond: A -> B, A -> C, B -> D, C -> D."""
    _write_context(tmp_path / "a", name="a", consumes=["b", "c"])
    _write_context(tmp_path / "b", name="b", consumes=["d"])
    _write_context(tmp_path / "c", name="c", consumes=["d"])
    _write_context(tmp_path / "d", name="d")
    return tmp_path


@pytest.fixture()
def cycle_ab(tmp_path: Path) -> Path:
    """Simple cycle: A -> B -> A."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["a"])
    return tmp_path


@pytest.fixture()
def cycle_abc(tmp_path: Path) -> Path:
    """3-node cycle: A -> B -> C -> A."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["c"])
    _write_context(tmp_path / "c", name="c", consumes=["a"])
    return tmp_path


@pytest.fixture()
def with_constraints(tmp_path: Path) -> Path:
    """Modules with constraints."""
    _write_context(
        tmp_path / "api",
        name="api",
        consumes=["engine"],
        constraints=["No blocking calls"],
    )
    _write_context(
        tmp_path / "engine",
        name="engine",
        constraints=["All functions must be pure"],
    )
    return tmp_path


@pytest.fixture()
def sla_mismatch(tmp_path: Path) -> Path:
    """Latency-critical module consuming a batch data source."""
    _write_context(
        tmp_path / "fast",
        name="fast",
        consumes=["slow"],
        operational={"latency_critical": True, "max_latency_ms": 50},
    )
    _write_context(
        tmp_path / "slow",
        name="slow",
        operational={"data_freshness": "batch"},
    )
    return tmp_path


@pytest.fixture()
def sla_ok(tmp_path: Path) -> Path:
    """Both modules are realtime — no mismatch."""
    _write_context(
        tmp_path / "fast",
        name="fast",
        consumes=["feed"],
        operational={"latency_critical": True, "max_latency_ms": 50},
    )
    _write_context(
        tmp_path / "feed",
        name="feed",
        operational={"data_freshness": "realtime"},
    )
    return tmp_path


@pytest.fixture()
def dangling_consumes(tmp_path: Path) -> Path:
    """Module consumes a non-existent module."""
    _write_context(tmp_path / "orphan", name="orphan", consumes=["ghost"])
    return tmp_path
