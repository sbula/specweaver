# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the sandbox will do with a project's dependencies, decided once.

The container executor acts on this and `sw sandbox preflight` prints it. Deciding it in one place
is the point: a preflight that re-derived the decision would agree with the sandbox only until one
of them changed, and a report describing something other than what runs is worse than no report.

Resides in L0 commons for the same reason as the QA result models beside it — the delivery layer
must be able to read this without importing the sandbox, and reading a manifest is knowledge about
packaging rather than a way to execute anything.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from specweaver.commons.tooling_sources import ToolingSource, declared_pytest

if TYPE_CHECKING:
    from pathlib import Path


#: The QA runner invokes `python -m pytest` and nothing else, so this is the entire predicate: a
#: group is worth syncing exactly when it puts pytest in the environment.
#:
#: `tox` and `nox` are deliberately absent even though both are test runners. They build their own
#: environments and would leave `python -m pytest` failing exactly as before, while installing the
#: rest of that group — and the prepare phase executes arbitrary sdist build code, so widening what
#: an untrusted project builds for no gain is the wrong trade. `coverage` is absent for the simpler
#: reason that it measures a run and cannot start one.
_TEST_RUNNERS: tuple[str, ...] = ("pytest",)

#: `uv sync` installs this group unasked. Requesting it again would be noise.
_DEFAULT_GROUP = "dev"

#: Installed only when the project names no runner anywhere. Bare: which plugins a suite needs
#: is exactly what the project failed to say, so guessing at them would add arbitrary packages
#: to an already arbitrary choice.
_LAST_RESORT_RUNNER = "pytest"


def _declares_a_runner(deps: list[object]) -> bool:
    """Whether a dependency-group's entries include something that can run a test suite."""
    for dep in deps:
        if not isinstance(dep, str):
            # A PEP 735 `{include-group = "..."}` table. The included group is judged on its own
            # entries, so following the reference here would only find it twice.
            continue
        name = re.split(r"[<>=!~;\[\s]", dep.strip(), maxsplit=1)[0].lower().replace("_", "-")
        if any(name == runner or name.startswith(f"{runner}-") for runner in _TEST_RUNNERS):
            return True
    return False


def _manifest_declares_a_runner(manifest_text: str) -> bool:
    """Whether `uv` can install pytest from this manifest alone, by group or at runtime.

    The gate on reading any other file. A project that declares pytest has pinned it, and layering a
    `tox.ini` block over that resolution would turn a reproducible run into a mixed one.
    """
    try:
        manifest = tomllib.loads(manifest_text)
    except (tomllib.TOMLDecodeError, ValueError):
        return False
    runtime = (manifest.get("project") or {}).get("dependencies")
    return bool(_groups_holding_a_runner(manifest_text)) or (
        isinstance(runtime, list) and _declares_a_runner(runtime)
    )


def _groups_holding_a_runner(manifest_text: str) -> list[str]:
    """Every PEP 735 group that declares pytest, `dev` included.

    `dev` is returned rather than filtered here because the two prepare paths disagree about it:
    `uv sync` installs it unasked, while `uv pip install` installs nothing it is not given. Dropping
    it at the source would silently strip the most common runner location from the second path.

    Detection is by content because the names are a long tail: `test`, `tests`, `testing`, `ci`,
    `test-core` and `dev-base` all carry pytest across the measured corpus, while
    `tests-postgresql` and `tests-mysql` carry database drivers and none. A name list would miss
    the first set and install the second.

    It is also the only safe rule. `uv sync --group <undeclared>` exits 2 rather than warning, so a
    speculative name would break the prepare phase for every project that does not use it; only
    groups this manifest actually declares are ever returned.

    A manifest that cannot be parsed yields no groups. Group detection improves the sync; it is
    never a new way for it to fail.
    """
    try:
        manifest = tomllib.loads(manifest_text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []
    groups = manifest.get("dependency-groups")
    if not isinstance(groups, dict):
        return []
    return sorted(
        name for name, deps in groups.items() if isinstance(deps, list) and _declares_a_runner(deps)
    )


#: Which build tool owns a project, by the manifest it reads. Python first: a polyglot tree — this
#: repo has Java and Kotlin fixtures inside a Python one — resolves to Python for QA today, and
#: changing that is a routing decision rather than a prepare-phase one.
_TOOLCHAIN_MANIFESTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("uv", ("pyproject.toml", "uv.lock")),
    ("cargo", ("Cargo.toml",)),
    ("maven", ("pom.xml",)),
    ("gradle", ("build.gradle", "build.gradle.kts")),
)

#: Where each tool's fetched dependencies live. On the cache mount, which is read-write while the
#: prepare phase runs and read-only afterwards, so the execute phase can read them with no network.
_CARGO_HOME = "/cache/cargo"
_MAVEN_REPO = "/cache/m2"

#: Where a build writes. `/workspace` is read-only, so the default output directory cannot be
#: used as-is — Rust is pointed here by `CARGO_TARGET_DIR`, and for the JVM the executor mounts
#: this path over `target/` so Maven's own defaults keep working.
_BUILD_DIR = "/scratch/target"


def detect_toolchain(source_root: Path) -> str:
    """The build tool this project declares, or `""` when it declares none."""
    for toolchain, manifests in _TOOLCHAIN_MANIFESTS:
        if any((source_root / name).is_file() for name in manifests):
            return toolchain
    return ""


@dataclass(frozen=True)
class PreparePlan:
    """Everything the prepare phase decides before it runs a container."""

    #: `"locked"` — `uv sync --frozen`, reproducing the project's pins. `"resolved"` — `uv venv`
    #: plus `uv pip install`, resolving fresh because no `uv.lock` was committed.
    route: str
    #: Where the test runner comes from: a manifest group, a file, `"sandbox"`, or `""` when the
    #: project has no manifest for `uv` to read at all.
    runner_source: str
    groups: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    #: The declaration the runner was found in, when it came from outside the manifest. Carried so
    #: the executor installs exactly what the report described, rather than looking it up again.
    source: ToolingSource | None = None
    #: The build tool that owns the project — `uv`, `cargo`, `maven`, `gradle`, or `""`.
    toolchain: str = "uv"
    #: Commands to run in the network-enabled prepare phase, as `(step name, argv)`.
    steps: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: Environment the prepare and execute phases must share, so a fetch survives into the run.
    env: dict[str, str] = field(default_factory=dict)
    #: Environment for the execute phase only — chiefly the offline switches, which must not
    #: apply to the prepare phase, since fetching is the one thing that needs the network.
    execute_env: dict[str, str] = field(default_factory=dict)


def plan_for(source_root: Path) -> PreparePlan:
    """What the prepare phase will do with the project at `source_root`."""
    toolchain = detect_toolchain(source_root)
    if toolchain and toolchain != "uv":
        return _plan_for_other(toolchain, source_root)

    manifest = source_root / "pyproject.toml"
    manifest_text = (
        manifest.read_text(encoding="utf-8", errors="replace") if manifest.is_file() else ""
    )
    locked = (source_root / "uv.lock").is_file()
    route = "locked" if locked else "resolved"

    if not manifest_text and not locked:
        return PreparePlan(
            route="none",
            runner_source="",
            warnings=(
                "No pyproject.toml and no uv.lock, so no environment can be built at all. The QA "
                "run will use the container image's own interpreter, which has no test runner.",
            ),
        )

    warnings: list[str] = []
    if not locked:
        warnings.append(
            "No uv.lock, so dependencies are resolved fresh from pyproject.toml. The environment "
            "will NOT reproduce the project's pinned set. Commit a lockfile to make runs match CI."
        )

    groups = tuple(_groups_holding_a_runner(manifest_text))
    if _manifest_declares_a_runner(manifest_text):
        return PreparePlan(route, "pyproject.toml", groups, warnings=tuple(warnings))

    fallback: ToolingSource | None = declared_pytest(source_root)
    if fallback is not None:
        if fallback.skipped:
            warnings.append(
                f"{len(fallback.skipped)} line(s) of {fallback.path} need tox's own substitution "
                f"engine and will not be installed — plugins declared there will be missing."
            )
        return PreparePlan(
            route, fallback.path, groups, fallback.skipped, tuple(warnings), source=fallback
        )

    warnings.append(
        "No test runner is declared in pyproject.toml, tox.ini or any requirements file, so the "
        "sandbox will install pytest itself. Its version is not the project's choice and any "
        "plugins the suite needs will be absent — results will say so."
    )
    return PreparePlan(route, "sandbox", groups, warnings=tuple(warnings))


def _plan_for_other(toolchain: str, source_root: Path) -> PreparePlan:
    """The plan for a toolchain that is not `uv`.

    Every one of these resolves dependencies over the network, and the execute phase has none. So the
    fetch happens here, into `/cache`, and the run that follows is explicitly offline. A project whose
    dependencies cannot be pre-fetched cannot be prepared, and saying so is the point.
    """
    if toolchain == "cargo":
        # `cargo fetch` resolves, and resolving writes `Cargo.lock` — into `/workspace`, which is
        # read-only in both phases. With a committed lockfile `--locked` asserts no write is needed;
        # without one cargo refuses outright, saying so itself: *"cannot create the lock file …
        # because --locked was passed"*. The alternative is making the source tree writable while
        # arbitrary build scripts run, which is the isolation the sandbox exists to keep.
        if not (source_root / "Cargo.lock").is_file():
            return PreparePlan(
                route="none",
                runner_source="Cargo.toml",
                toolchain=toolchain,
                warnings=(
                    "This crate has no committed Cargo.lock. Resolving one writes into the source "
                    "tree, which the sandbox mounts read-only, so its dependencies cannot be "
                    "fetched. Commit Cargo.lock — `cargo generate-lockfile` — and it is supported.",
                ),
            )
        return PreparePlan(
            route="fetch",
            runner_source="Cargo.toml",
            toolchain=toolchain,
            steps=(("fetch", ("cargo", "fetch", "--locked")),),
            # The build writes to `/scratch`, not to `target/` under the read-only source mount.
            env={
                "CARGO_HOME": _CARGO_HOME,
                "CARGO_TARGET_DIR": _BUILD_DIR,
                "HOME": "/scratch",
            },
            execute_env={"CARGO_NET_OFFLINE": "true"},
            warnings=(
                "Rust dependencies are fetched now and the test run is offline. A crate that "
                "resolves anything at build time — a build script reaching the network — will fail "
                "in the execute phase, which has none.",
            ),
        )
    if toolchain == "maven":
        return PreparePlan(
            route="fetch",
            runner_source="pom.xml",
            toolchain=toolchain,
            steps=(
                (
                    "fetch",
                    (
                        "mvn",
                        "-q",
                        "-B",
                        f"-Dmaven.repo.local={_MAVEN_REPO}",
                        "dependency:go-offline",
                    ),
                ),
            ),
            # `HOME` because the image defaults it to `/root`, which the sandbox's non-root user
            # cannot write — Maven fails at `mkdir /root` before it compiles anything.
            env={"MAVEN_REPO_LOCAL": _MAVEN_REPO, "HOME": "/scratch"},
            # Maven 3.9 reads `MAVEN_ARGS`, so the run goes offline against the fetched repository
            # without the QA runner needing to know it is inside a sandbox. The build directory is
            # redirected for the same reason as Rust's: the default `target/` is under `/workspace`,
            # which is read-only.
            execute_env={"MAVEN_ARGS": f"-o -Dmaven.repo.local={_MAVEN_REPO}"},
            warnings=(
                "Maven dependencies are resolved now and the test run is offline. A plugin that "
                "`dependency:go-offline` does not pre-fetch — some resolve at execution — will fail "
                "in the execute phase, which has no network.",
                "Running Maven inside the sandbox is NOT yet verified: the fetch succeeds, but "
                "surefire fails in the execute phase because a JVM build writes to `target/` inside "
                "the project and `/workspace` is read-only. Run JVM QA on the host until that is "
                "resolved.",
            ),
        )
    return PreparePlan(
        route="none",
        runner_source="",
        toolchain=toolchain,
        warnings=(
            "Gradle projects cannot be prepared yet: a Gradle wrapper downloads its own "
            "distribution on first use and the execute phase has no network, while the system "
            "Gradle is 4.4.1. Use Maven for a JVM project inside the sandbox, or run on the host.",
        ),
    )
