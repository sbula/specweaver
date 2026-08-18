# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which toolchain a project needs, and what has to happen before it can run offline.

The prepare phase existed for Python only: `_ensure_prepared` returned immediately when a project had
no `pyproject.toml`, so a Rust or JVM project reached the execute phase with nothing installed. That
matters because the execute phase runs `--network none` by design — dependency resolution has to
happen in the prepare phase, which is the one with network, or not at all.

The mount layout is what makes this possible and it is already there: `/cache` is read-write in the
prepare phase and read-only in the execute phase, and `/scratch` is read-write in the execute phase.
So dependencies are fetched into the cache once, and builds write to scratch — never to
`/workspace`, which is read-only in both.

Proves: TECH-031 FR-16
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.prepare_plan import detect_toolchain, plan_for

if TYPE_CHECKING:
    from pathlib import Path


def _project(tmp_path: Path, **files: str) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    for name, text in files.items():
        (root / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return root


class TestDetectToolchain:
    """Named from the manifest, because that is what the build tool itself reads."""

    def test_a_cargo_manifest_is_rust(self, tmp_path: Path) -> None:
        assert detect_toolchain(_project(tmp_path, Cargo__toml="[package]\n")) == "cargo"

    def test_a_pom_is_maven(self, tmp_path: Path) -> None:
        assert detect_toolchain(_project(tmp_path, pom__xml="<project/>")) == "maven"

    def test_a_groovy_gradle_script_is_gradle(self, tmp_path: Path) -> None:
        assert detect_toolchain(_project(tmp_path, build__gradle="")) == "gradle"

    def test_a_kotlin_gradle_script_is_gradle(self, tmp_path: Path) -> None:
        """Separate test rather than a second call: the helper builds the project directory."""
        assert detect_toolchain(_project(tmp_path, **{"build__gradle__kts": ""})) == "gradle"

    def test_a_pyproject_is_uv(self, tmp_path: Path) -> None:
        assert detect_toolchain(_project(tmp_path, pyproject__toml="[project]\n")) == "uv"

    def test_python_wins_when_a_project_carries_both(self, tmp_path: Path) -> None:
        """A polyglot repo is real — this repo has Java and Kotlin fixtures inside a Python tree.

        Python is checked first because that is what the QA runner resolves for such a tree today;
        changing which language wins is a routing decision, not a prepare-phase one.
        """
        root = _project(tmp_path, pyproject__toml="[project]\n", Cargo__toml="[package]\n")

        assert detect_toolchain(root) == "uv"

    def test_a_tree_with_no_manifest_names_no_toolchain(self, tmp_path: Path) -> None:
        assert detect_toolchain(_project(tmp_path, README__md="")) == ""


class TestPlanForOtherToolchains:
    """The plan the executor acts on, for the three languages it could not prepare at all."""

    def test_a_rust_project_fetches_its_dependencies_first(self, tmp_path: Path) -> None:
        """`cargo fetch` in the phase with network; the build then runs `--offline`."""
        plan = plan_for(_project(tmp_path, Cargo__toml='[package]\nname = "p"\n', Cargo__lock=""))

        assert plan.toolchain == "cargo"
        assert plan.route == "fetch"
        joined = [" ".join(cmd) for _, cmd in plan.steps]
        assert any("cargo fetch" in j for j in joined), joined

    def test_rust_dependencies_land_in_the_cache_not_the_source_tree(self, tmp_path: Path) -> None:
        """`/workspace` is read-only, and the default `CARGO_HOME` is outside it anyway — what
        matters is that the fetch survives into the execute phase, which only sees `/cache`."""
        plan = plan_for(_project(tmp_path, Cargo__toml='[package]\nname = "p"\n', Cargo__lock=""))

        assert any("/cache" in v for v in plan.env.values()), plan.env

    def test_a_crate_without_a_lockfile_is_reported_rather_than_attempted(
        self, tmp_path: Path
    ) -> None:
        """`cargo fetch` resolves, and resolving writes `Cargo.lock` into a read-only mount.

        Cargo says so itself under `--locked`: *"cannot create the lock file … because --locked was
        passed"*. The alternative is a writable source tree while arbitrary build scripts run.
        """
        plan = plan_for(_project(tmp_path, Cargo__toml='[package]\nname = "p"\n'))

        assert plan.toolchain == "cargo"
        assert plan.steps == ()
        assert any("Cargo.lock" in w for w in plan.warnings), plan.warnings

    def test_the_rust_run_is_offline_but_the_fetch_is_not(self, tmp_path: Path) -> None:
        """The fetch is the one step that needs the network; the run must not have it."""
        plan = plan_for(_project(tmp_path, Cargo__toml='[package]\nname = "p"\n', Cargo__lock=""))

        assert plan.execute_env.get("CARGO_NET_OFFLINE") == "true"
        assert "CARGO_NET_OFFLINE" not in plan.env

    def test_a_maven_project_goes_offline_first(self, tmp_path: Path) -> None:
        plan = plan_for(_project(tmp_path, pom__xml="<project/>"))

        assert plan.toolchain == "maven"
        joined = [" ".join(cmd) for _, cmd in plan.steps]
        assert any("dependency:go-offline" in j for j in joined), joined
        assert any("/cache" in v for v in plan.env.values()), plan.env

    def test_a_gradle_project_is_reported_as_unsupported_rather_than_silently_skipped(
        self, tmp_path: Path
    ) -> None:
        """The honest answer for now. A Gradle wrapper downloads its own distribution on first use,
        which the execute phase has no network for, and the system Gradle is 4.4.1 — so claiming
        support would be the vacuous kind of green this ticket exists to remove."""
        plan = plan_for(_project(tmp_path, build__gradle=""))

        assert plan.toolchain == "gradle"
        assert plan.steps == ()
        assert any("gradle" in w.lower() for w in plan.warnings), plan.warnings

    def test_python_planning_is_unchanged(self, tmp_path: Path) -> None:
        """The control. Adding three toolchains must not move the one that already worked."""
        plan = plan_for(
            _project(
                tmp_path,
                pyproject__toml='[project]\nname = "t"\nversion = "0"\n\n'
                '[dependency-groups]\ntests = ["pytest"]\n',
                uv__lock="locked",
            )
        )

        assert plan.toolchain == "uv"
        assert plan.route == "locked"
        assert plan.runner_source == "pyproject.toml"
