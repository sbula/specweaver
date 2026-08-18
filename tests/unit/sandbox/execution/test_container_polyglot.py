# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The container executor acting on a plan for a toolchain that is not Python.

The plan is decided in `commons.prepare_plan` and has its own tests. What is asserted here is that
the executor *acts* on it: runs the fetch, carries the environment into both phases, and picks an
image that contains the toolchain at all. A plan nothing consumes is half a deliverable.

Three things are easy to get wrong and each is pinned below. The image must change with the
toolchain, or `cargo` is simply absent. The environment must reach **both** phases, or the fetch
lands somewhere the run cannot see. And `PATH` must not be overridden with the Python venv path,
because `cargo` lives outside it in the Rust image.

Proves: TECH-031 FR-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.executor import SubprocessExecutor
from tests.fixtures.container_sandbox import mounts as _mounts
from tests.fixtures.container_sandbox import ok_result as _ok_result

if TYPE_CHECKING:
    from pathlib import Path


def _prepare(tmp_path: Path, monkeypatch, **files: str):
    mounts = _mounts(tmp_path)
    for name, text in files.items():
        (mounts.source_root / name.replace("__", ".")).write_text(text, encoding="utf-8")
    mock = MagicMock(return_value=_ok_result())
    monkeypatch.setattr(SubprocessExecutor, "execute", mock)
    monkeypatch.setattr(
        "specweaver.sandbox.execution.container_executor.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
    executor._ensure_prepared()
    argvs = [list(c.args[0]) for c in mock.call_args_list if c.args]
    return executor, argvs


class TestPrepareOtherToolchainRunsTheFetch:
    def test_a_rust_project_fetches_its_crates(self, tmp_path: Path, monkeypatch) -> None:
        _, argvs = _prepare(
            tmp_path, monkeypatch, Cargo__toml='[package]\nname = "p"\n', Cargo__lock=""
        )

        joined = [" ".join(a) for a in argvs]
        assert any("cargo fetch" in j for j in joined), joined

    def test_the_rust_fetch_lands_where_the_run_can_read_it(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`/cache` is the only path the execute phase still sees, and it sees it read-only."""
        _, argvs = _prepare(
            tmp_path, monkeypatch, Cargo__toml='[package]\nname = "p"\n', Cargo__lock=""
        )

        fetch = next(a for a in argvs if "fetch" in a)
        assert "CARGO_HOME=/cache/cargo" in fetch, fetch

    def test_a_maven_project_resolves_offline_first(self, tmp_path: Path, monkeypatch) -> None:
        _, argvs = _prepare(tmp_path, monkeypatch, pom__xml="<project/>")

        joined = [" ".join(a) for a in argvs]
        assert any("dependency:go-offline" in j for j in joined), joined

    def test_a_crate_without_a_lockfile_is_skipped_with_its_reason(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Resolving writes `Cargo.lock` into the read-only source mount, so there is nothing to run.

        Skipped rather than raised: the project is not broken, it is unsupported, and the warning
        says which one line of `cargo generate-lockfile` makes it supported.
        """
        _, argvs = _prepare(tmp_path, monkeypatch, Cargo__toml='[package]\nname = "p"\n')

        assert not any("fetch" in " ".join(a) for a in argvs), argvs

    def test_a_gradle_project_is_skipped_without_raising(self, tmp_path: Path, monkeypatch) -> None:
        """It has no steps, and a plan with no steps must not be mistaken for a failed prepare."""
        _, argvs = _prepare(tmp_path, monkeypatch, build__gradle="")

        assert not any("gradle" in " ".join(a) for a in argvs if "run" in a), argvs

    def test_a_python_project_still_takes_the_uv_path(self, tmp_path: Path, monkeypatch) -> None:
        """The control. Three new toolchains must not move the one that already worked."""
        _, argvs = _prepare(
            tmp_path,
            monkeypatch,
            pyproject__toml='[project]\nname = "t"\nversion = "0"\ndependencies = []\n',
            uv__lock="locked",
        )

        joined = [" ".join(a) for a in argvs]
        assert any("uv sync --frozen" in j for j in joined), joined


class TestResolveImageFollowsTheToolchain:
    """An image without the toolchain in it makes every other fix irrelevant."""

    @pytest.mark.parametrize(
        ("manifest", "expected"),
        [
            ("Cargo__toml", "rust"),
            ("pom__xml", "maven"),
            ("pyproject__toml", "specweaver-sandbox-python"),
        ],
    )
    def test_the_image_contains_the_toolchain(
        self, tmp_path: Path, monkeypatch, manifest: str, expected: str
    ) -> None:
        executor, _ = _prepare(tmp_path, monkeypatch, **{manifest: "x"})

        assert expected in executor._image, executor._image

    def test_an_explicit_image_still_wins(self, tmp_path: Path, monkeypatch) -> None:
        """The parameter is how the live tests pin a known image; detection must not override it."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts, image="my/own:tag")

        assert executor._image == "my/own:tag"


class TestBuildContainerCmdCarriesToolchainEnv:
    def test_the_run_sees_the_fetched_crates(self, tmp_path: Path, monkeypatch) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")
        (mounts.source_root / "Cargo.lock").write_text("", encoding="utf-8")
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        cmd = executor._build_container_cmd("podman", "n", ["cargo", "test"], None)

        assert "CARGO_HOME=/cache/cargo" in cmd, cmd
        assert "CARGO_TARGET_DIR=/scratch/target" in cmd, cmd

    def test_the_python_venv_path_is_not_forced_on_another_toolchain(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`cargo` lives outside `/cache/venv/bin`, and overriding PATH with it hides the toolchain
        the image was chosen for."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")
        (mounts.source_root / "Cargo.lock").write_text("", encoding="utf-8")
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        cmd = executor._build_container_cmd("podman", "n", ["cargo", "test"], None)

        assert not any(a.startswith("PATH=/cache/venv") for a in cmd), cmd

    def test_a_python_run_keeps_its_prepared_path(self, tmp_path: Path, monkeypatch) -> None:
        """The control: the Python path is the one thing that must not regress here."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        cmd = executor._build_container_cmd("podman", "n", ["python", "-m", "pytest"], None)

        assert any(a.startswith("PATH=/cache/venv/bin:") for a in cmd), cmd
