# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Scenario tests run in a container that mounts them read-only at `/scenarios`, and nowhere else.

Proves: B-FLOW-01 FR-14

| Bucket | Case |
|---|---|
| Happy | the scenario executor mounts the store at `/scenarios:ro`; the atom runs a test there |
| Boundary | no `/scenarios` for a coder executor, nor while installing dependencies |
| Degradation | no engine, an engine that does not answer, or an image that will not build: no container |
| Hostile | `/etc/x`, `/scenarios/../etc/x`, `/scenarios/x` without the mount: refused |
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

import pytest

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.models import ContainerMounts
from specweaver.sandbox.execution.sandbox_image import (
    container_available,
    ensure_sandbox_image,
    own_image,
    sandbox_ready,
)
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom


def _mounts(tmp_path: Path, scenarios: Path | None) -> ContainerMounts:
    return ContainerMounts(
        source_root=tmp_path / "project",
        scratch_root=tmp_path / "scratch",
        cache_root=tmp_path / "cache",
        scenarios_root=scenarios,
    )


def _executor(tmp_path: Path, scenarios: Path | None) -> ContainerSubprocessExecutor:
    (tmp_path / "project").mkdir(exist_ok=True)
    return ContainerSubprocessExecutor(
        cwd=tmp_path / "project", mounts=_mounts(tmp_path, scenarios)
    )


def test_the_scenario_executor_mounts_the_store_read_only(tmp_path: Path) -> None:
    argv = _executor(tmp_path, tmp_path / "store")._build_container_cmd("podman", "n", ["x"], None)
    assert f"{tmp_path / 'store'}:/scenarios:ro" in argv


def test_a_coder_executor_has_no_scenarios_mount(tmp_path: Path) -> None:
    argv = _executor(tmp_path, None)._build_container_cmd("podman", "n", ["x"], None)
    assert not [a for a in argv if "/scenarios" in a]


def test_installing_dependencies_never_sees_the_store(tmp_path: Path) -> None:
    argv = _executor(tmp_path, tmp_path / "store")._prepare_container("podman", "n", "uv", "sync")
    assert not [a for a in argv if "/scenarios" in a]


@pytest.mark.parametrize(
    ("found", "answers", "available"),
    [
        ({}, True, False),
        ({"podman": "/usr/bin/podman"}, False, False),
        ({"podman": "/usr/bin/podman"}, True, True),
    ],
    ids=["no-engine", "engine-silent", "engine-live"],
)
def test_a_container_is_available_only_with_a_live_engine(
    found: dict[str, str], answers: bool, available: bool
) -> None:
    assert container_available(which=found.get, probe=lambda engine: answers) is available


def _refused(tmp_path: Path, scenarios: Path | None, target: str) -> bool:
    """Whether the atom refuses `target` before any tool starts."""
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    with (
        patch("specweaver.sandbox.qa_runner.core.atom._build_container_executor"),
        patch("specweaver.sandbox.qa_runner.core.atom._resolve_runner") as resolve,
        suppress(TypeError),  # a mock runner's result is not a real one
    ):
        QARunnerAtom(cwd=project, scenarios_root=scenarios).run(
            {"intent": "run_tests", "target": target}
        )
    return not resolve.return_value.run_tests.called


def test_a_target_in_the_mount_is_accepted(tmp_path: Path) -> None:
    assert not _refused(
        tmp_path, tmp_path / "store", "/scenarios/generated/test_greet_scenarios.py"
    )


@pytest.mark.parametrize("target", ["/etc/x", "/scenarios/../etc/x", "../outside.py"])
def test_a_target_outside_the_project_and_the_mount_is_refused(tmp_path: Path, target: str) -> None:
    assert _refused(tmp_path, tmp_path / "store", target)


def test_without_the_mount_the_scenarios_path_is_refused(tmp_path: Path) -> None:
    assert _refused(tmp_path, None, "/scenarios/generated/x.py")


# --- the sandbox image: built here when missing (no registry) ---------------------------------


class _Engine:
    """Records the engine commands; answers `exists` and `build` as told."""

    def __init__(self, exists: bool, builds: bool) -> None:
        self.calls: list[list[str]] = []
        self._exists, self._builds = exists, builds

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(argv)
        if "exists" in argv or "inspect" in argv:
            return 0 if self._exists else 1
        return 0 if self._builds else 1


_OWN_IMAGE = own_image("3.13")


def test_a_present_image_is_not_built() -> None:
    engine = _Engine(exists=True, builds=True)
    assert ensure_sandbox_image(_OWN_IMAGE, "/usr/bin/podman", engine) is True
    assert not [c for c in engine.calls if "build" in c]


def test_a_missing_image_is_built_from_the_shipped_recipe() -> None:
    engine = _Engine(exists=False, builds=True)

    assert ensure_sandbox_image(_OWN_IMAGE, "/usr/bin/podman", engine) is True
    (build,) = [c for c in engine.calls if "build" in c]
    recipe = Path(build[build.index("-f") + 1])
    assert recipe.name == "Containerfile.sandbox" and recipe.is_file()
    assert build[build.index("-t") + 1] == _OWN_IMAGE
    assert "PY_VERSION=3.13" in build


def test_a_failed_build_means_no_container() -> None:
    assert ensure_sandbox_image(_OWN_IMAGE, "/usr/bin/podman", _Engine(False, False)) is False


def test_an_upstream_image_is_never_built() -> None:
    engine = _Engine(exists=False, builds=True)
    assert ensure_sandbox_image("docker.io/library/rust:1-slim", "/usr/bin/podman", engine) is True
    assert engine.calls == []


def test_ready_needs_a_live_engine_and_the_projects_image(tmp_path: Path) -> None:
    built: list[str] = []

    def ensure(image: str, engine: str, run: object) -> bool:
        built.append(image)
        return True

    assert sandbox_ready(
        tmp_path, which={"podman": "/usr/bin/podman"}.get, probe=lambda e: True, ensure=ensure
    )
    assert built == [own_image("3.13")]
    assert not sandbox_ready(tmp_path, which={}.get, probe=lambda e: True, ensure=ensure)
    assert not sandbox_ready(
        tmp_path,
        which={"podman": "/usr/bin/podman"}.get,
        probe=lambda e: True,
        ensure=lambda *a: False,
    )


def test_the_image_name_carries_the_recipe_so_a_change_rebuilds() -> None:
    image = own_image("3.13")
    assert image.startswith("localhost/specweaver-sandbox-python:3.13-")
    assert own_image("3.13", recipe=b"FROM x\n") != image


def test_the_recipe_installs_pytest_for_the_scenario_tests() -> None:
    import importlib.resources

    recipe = importlib.resources.files("specweaver.sandbox.execution").joinpath(
        "Containerfile.sandbox"
    )
    assert "pytest" in recipe.read_text(encoding="utf-8")


def test_a_coder_container_run_never_mounts_the_scenarios(tmp_path: Path) -> None:
    from specweaver.core.config.settings import SandboxSettings

    project = tmp_path / "project"
    project.mkdir()
    atom = QARunnerAtom(cwd=project, sandbox_settings=SandboxSettings(execution_mode="container"))
    assert atom._runner._executor._mounts.scenarios_root is None
