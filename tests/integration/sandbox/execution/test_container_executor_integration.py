# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real-engine integration tests for ContainerSubprocessExecutor (B-EXEC-01).

Requires a live Podman or Docker engine on the host. Skips cleanly (per NFR-10)
when neither is detected, so this file is safe to run in environments without
a container runtime.

Uses the public ``python:3.13-slim`` image rather than SpecWeaver's own not-yet-
published sandbox image (Containerfile.sandbox's CI publish pipeline is Backlog,
per the implementation plan) — this keeps the test independent of that follow-up.

Proves: TECH-031 FR-1, TECH-031 FR-2, TECH-031 FR-3, TECH-031 FR-4
Proves: TECH-031 FR-5, TECH-031 FR-6, TECH-031 FR-7
Proves: TECH-031 FR-8, TECH-031 FR-9
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.models import ContainerMounts
from specweaver.sandbox.language.core.python.runner import PythonQARunner

if TYPE_CHECKING:
    from pathlib import Path

_TEST_IMAGE = "python:3.13-slim"


def _detect_live_engine() -> str | None:
    for name in ("podman", "docker"):
        resolved = shutil.which(name)
        if not resolved:
            continue
        try:
            result = subprocess.run(
                [resolved, "info"], capture_output=True, timeout=10, check=False
            )
        except OSError:
            continue
        if result.returncode == 0:
            return resolved
    return None


_LIVE_ENGINE = _detect_live_engine()

pytestmark = pytest.mark.skipif(
    _LIVE_ENGINE is None, reason="no live podman/docker engine detected on this host"
)


def _mounts(tmp_path: Path) -> ContainerMounts:
    source_root = tmp_path / "project"
    source_root.mkdir()
    return ContainerMounts(
        source_root=source_root,
        scratch_root=source_root / ".specweaver" / ".sandbox" / "scratch",
        cache_root=source_root / ".specweaver" / ".sandbox" / "cache",
    )


class TestContainerExecutorRealEngine:
    """Round-trip tests against a real, live Podman/Docker engine."""

    def test_read_only_source_mount_blocks_writes(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="ro-test"
        )

        result = executor.execute(["sh", "-c", "echo bad > /workspace/hack.txt"])

        assert result.exit_code != 0
        assert not (mounts.source_root / "hack.txt").exists()

    def test_writable_scratch_mount_allows_writes(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="rw-test"
        )

        result = executor.execute(["sh", "-c", "echo ok > /scratch/output.txt"])

        assert result.exit_code == 0
        output_file = mounts.scratch_root / "output.txt"
        assert output_file.is_file()
        assert output_file.read_text().strip() == "ok"

    def test_network_none_blocks_egress(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="net-test"
        )

        result = executor.execute(
            [
                "python",
                "-c",
                "import socket; socket.create_connection(('8.8.8.8', 53), timeout=3)",
            ]
        )

        assert result.exit_code != 0

    def test_container_removed_after_execution(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        run_id = "cleanup-test"
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id=run_id
        )

        executor.execute(["sh", "-c", "echo hi"])

        ps = subprocess.run(
            [
                _LIVE_ENGINE,
                "ps",
                "-a",
                "--filter",
                f"name=specweaver-qa-{run_id}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert ps.stdout.strip() == ""

    def test_result_contract_matches_subprocess_result_from_real_run(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="result-test"
        )

        result = executor.execute(["python", "-c", "print('hello from container')"])

        assert result.exit_code == 0
        assert "hello from container" in result.stdout
        assert result.timed_out is False


#: An image that ships `uv`. The prepare phase invokes `uv sync`, so `python:3.13-slim` — fine for
#: every other test in this file — cannot exercise it at all, and cannot install `uv` either because
#: the container is `--read-only`.
_UV_IMAGE = "ghcr.io/astral-sh/uv:python3.12-bookworm"


_RUST_IMAGE = "docker.io/library/rust:1-slim"


def _rust_image_available() -> bool:
    return _image_available(_RUST_IMAGE)


def _uv_image_available() -> bool:
    return _image_available(_UV_IMAGE)


def _image_available(image: str) -> bool:
    if _LIVE_ENGINE is None:
        return False
    try:
        probe = subprocess.run(
            [_LIVE_ENGINE, "image", "exists", image], capture_output=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


class TestPrepareAndExecuteShareAnEnvironment:
    """`TECH-031`: the prepare phase builds a toolchain and the execute phase actually uses it.

    This is the journey `INT-US-09-SF01-MIG` is held on — container execution *actually exercised*
    rather than asserted through mocks. It runs the real executor against a real engine; every other
    proof of this path built the podman argv by hand, which tests podman rather than this code.

    Until 2026-08-18 it could not have passed. Three walls, each re-measured against live podman:
    `uv` wrote `.venv` into a read-only workdir; a drifted lockfile made it rewrite a read-only
    `uv.lock`; and the execute phase never mounted the cache the environment lives on, so even a
    correct `PATH` pointed at nothing.
    """

    def _project(self, tmp_path: Path, groups: str = 'dev = ["pytest"]') -> ContainerMounts:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            '[project]\nname = "t"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            f"dependencies = []\n\n[dependency-groups]\n{groups}\n",
            encoding="utf-8",
        )
        assert _LIVE_ENGINE is not None
        subprocess.run(  # one-off fixture setup, writable on purpose
            [
                _LIVE_ENGINE,
                "run",
                "--rm",
                "-v",
                f"{mounts.source_root}:/w:rw",
                "--workdir",
                "/w",
                _UV_IMAGE,
                "uv",
                "lock",
            ],
            capture_output=True,
            timeout=180,
            check=True,
        )
        return mounts

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_the_toolchain_prepare_installed_is_the_one_execute_finds(self, tmp_path: Path) -> None:
        """pytest is declared by the project, installed by prepare, and found by execute."""
        mounts = self._project(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=mounts.source_root, mounts=mounts, image=_UV_IMAGE
        )

        result = executor.execute(["python", "-m", "pytest", "--version"], timeout_seconds=300)

        assert result.exit_code == 0, (
            f"the prepared toolchain was not usable from the execute phase:\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "pytest" in result.stdout.lower(), result.stdout

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_runner_declared_outside_dev_is_installed_for_real(self, tmp_path: Path) -> None:
        """`uv sync` installs `dev` and nothing else, and 26 of 121 measured repositories put the
        runner in `test`/`tests` instead.

        The unit tests prove the argv carries `--group tests`. They cannot prove uv then installs
        anything — only a real `uv sync` against a real lockfile can, which is what this does. It is
        also the check that a name list would have passed and a real project would have failed:
        `uv sync --group <undeclared>` exits 2, so the flag is only ever safe when it is derived
        from the manifest in front of it.
        """
        mounts = self._project(tmp_path, groups='dev = ["iniconfig"]\ntests = ["pytest"]')
        executor = ContainerSubprocessExecutor(
            cwd=mounts.source_root, mounts=mounts, image=_UV_IMAGE
        )

        result = executor.execute(["python", "-m", "pytest", "--version"], timeout_seconds=300)

        assert result.exit_code == 0, (
            f"the runner sits in `tests`, which a default `uv sync` skips, so the prepared "
            f"environment has no pytest:\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "pytest" in result.stdout.lower(), result.stdout

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_project_with_no_manifest_fails_loudly(self, tmp_path: Path) -> None:
        """The control, and the half that used to look identical to success.

        The fixture used to be a project with a `pyproject.toml` declaring no runner. That case no
        longer reaches here: the sandbox now supplies pytest for it and says so on the result. What
        remains genuinely unpreparable is a tree with **no manifest at all** — 22 of the 150 corpus
        repositories, where `pyproject.toml` sits under a monorepo path or the project still uses
        `setup.py`. There is nothing for `uv` to read, so no environment is built.

        The guarantee is unchanged and still worth a test: an absent toolchain must not produce a
        run that merely reports nothing, which is exactly what a `logger.warning` allowed.
        """
        project = tmp_path / "no-manifest"
        project.mkdir()
        (project / "test_it.py").write_text("def test_v() -> None:\n    assert True\n", "utf-8")
        assert not (project / "pyproject.toml").exists()

        mounts = ContainerMounts(
            source_root=project,
            scratch_root=project / ".specweaver" / ".sandbox" / "scratch",
            cache_root=project / ".specweaver" / ".sandbox" / "cache",
        )
        executor = ContainerSubprocessExecutor(cwd=project, mounts=mounts, image=_UV_IMAGE)

        result = executor.execute(["python", "-m", "pytest", "--version"], timeout_seconds=300)

        assert result.exit_code != 0, (
            "a project with no test runner reported success — the shape that let an absent "
            f"toolchain read as an empty suite: {result.stdout!r}"
        )

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_project_with_no_lockfile_still_gets_a_working_environment(
        self, tmp_path: Path
    ) -> None:
        """Rung 1: 20 of 121 corpus repositories declare pytest and commit no `uv.lock`.

        `uv sync --frozen` refuses without one, and dropping `--frozen` makes uv try to *write*
        `uv.lock` into the read-only mount. The route taken instead — `uv venv` then `uv pip
        install` — resolves from the manifest and needs nothing writable in the source tree.

        Driven all the way through `PythonQARunner` and a real suite, because the claim is not that
        a command was issued but that the tests can run: the project itself has to be installed too,
        or pytest is present and `import mypkg` fails.
        """
        project = tmp_path / "unlocked"
        (project / "src" / "mypkg").mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            'dependencies = ["iniconfig"]\n\n'
            '[dependency-groups]\ntests = ["pytest"]\n\n'
            '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n',
            encoding="utf-8",
        )
        (project / "src" / "mypkg" / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
        (project / "test_it.py").write_text(
            "from mypkg import VALUE\n\n\ndef test_v() -> None:\n    assert VALUE == 42\n",
            encoding="utf-8",
        )
        assert not (project / "uv.lock").exists(), "the fixture must not be locked"

        mounts = ContainerMounts(
            source_root=project,
            scratch_root=project / ".specweaver" / ".sandbox" / "scratch",
            cache_root=project / ".specweaver" / ".sandbox" / "cache",
        )
        runner = PythonQARunner(
            cwd=project,
            executor=ContainerSubprocessExecutor(cwd=project, mounts=mounts, image=_UV_IMAGE),
        )

        result = runner.run_tests(".", kind="")

        assert result.passed == 1 and result.errors == 0, (
            f"a project with no lockfile did not get a usable environment: {result}"
        )
        assert not (project / "uv.lock").exists(), (
            "the prepare phase wrote into the project's source tree, which is mounted read-only "
            "precisely so it cannot"
        )

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_runner_declared_only_in_tox_ini_is_installed(self, tmp_path: Path) -> None:
        """Rung 2, in the shape it actually occurs: 31 corpus repositories declare pytest in
        `tox.ini` and 81 declare it nowhere in `pyproject.toml`.

        The fixture also carries a tox factor line, `py3{10-14}: -r extra.pip`, which needs tox's
        own substitution engine. It must be skipped rather than guessed at — and the run must still
        succeed, because that line is not what holds the runner.
        """
        project = tmp_path / "tox-only"
        (project / "src" / "mypkg").mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            'dependencies = ["iniconfig"]\n\n'
            '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n',
            encoding="utf-8",
        )
        (project / "tox.ini").write_text(
            "[tox]\nenvlist = py311\n\n[testenv]\ndeps =\n    pytest>=8\n"
            "    py3{10-14}: -r extra.pip\ncommands = pytest {posargs}\n",
            encoding="utf-8",
        )
        (project / "src" / "mypkg" / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
        (project / "test_it.py").write_text(
            "from mypkg import VALUE\n\n\ndef test_v() -> None:\n    assert VALUE == 42\n",
            encoding="utf-8",
        )
        assert "pytest" not in (project / "pyproject.toml").read_text(encoding="utf-8")

        mounts = ContainerMounts(
            source_root=project,
            scratch_root=project / ".specweaver" / ".sandbox" / "scratch",
            cache_root=project / ".specweaver" / ".sandbox" / "cache",
        )
        runner = PythonQARunner(
            cwd=project,
            executor=ContainerSubprocessExecutor(cwd=project, mounts=mounts, image=_UV_IMAGE),
        )

        result = runner.run_tests(".", kind="")

        assert result.passed == 1 and result.errors == 0, (
            f"the runner was declared in tox.ini and never installed: {result}"
        )

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_supplied_runner_runs_the_suite_and_says_so(self, tmp_path: Path) -> None:
        """Rung 3, the one that changes what a green run means.

        33 corpus repositories declare pytest nowhere readable. They now get one from the sandbox —
        which is only defensible because the result says so. The two assertions carry equal weight:
        the suite ran, *and* the caller is told the runner was not the project's.
        """
        project = tmp_path / "declares-nothing"
        (project / "src" / "mypkg").mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            'dependencies = ["iniconfig"]\n\n'
            '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n',
            encoding="utf-8",
        )
        (project / "src" / "mypkg" / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
        (project / "test_it.py").write_text(
            "from mypkg import VALUE\n\n\ndef test_v() -> None:\n    assert VALUE == 42\n",
            encoding="utf-8",
        )

        mounts = ContainerMounts(
            source_root=project,
            scratch_root=project / ".specweaver" / ".sandbox" / "scratch",
            cache_root=project / ".specweaver" / ".sandbox" / "cache",
        )
        runner = PythonQARunner(
            cwd=project,
            executor=ContainerSubprocessExecutor(cwd=project, mounts=mounts, image=_UV_IMAGE),
        )

        result = runner.run_tests(".", kind="")

        assert result.passed == 1 and result.errors == 0, (
            f"no runner was supplied, so the suite could not run at all: {result}"
        )
        assert "supplied by the sandbox" in result.toolchain_note, (
            "the run used a pytest the project never chose and the result does not say so — "
            f"which is the vacuous success this ticket exists to remove: {result.toolchain_note!r}"
        )

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_the_absent_toolchain_is_explained_to_the_caller(self, tmp_path: Path) -> None:
        """Failing loudly is not the same as failing usefully, and this is the majority path.

        Measured across the corpus, 101 of 121 resolvable repositories reach the sandbox without
        pytest installed, so this message is what most first runs against a new target will say. It
        used to be the interpreter's own line forwarded verbatim — naming `/cache/venv`, a path
        inside our container that appears nowhere in the reader's project.

        Driven through `PythonQARunner` rather than the executor, because the wiring is the claim:
        the pure explainer has its own unit tests and passing them proves nothing about what a
        caller is handed.

        The fixture is a tree with no manifest. A project that *has* one but declares no runner is
        now supplied with pytest instead, so this message no longer reaches it — the message still
        matters wherever no environment can be built at all.
        """
        project = tmp_path / "no-manifest"
        project.mkdir()
        (project / "test_it.py").write_text("def test_v() -> None:\n    assert True\n", "utf-8")
        mounts = ContainerMounts(
            source_root=project,
            scratch_root=project / ".specweaver" / ".sandbox" / "scratch",
            cache_root=project / ".specweaver" / ".sandbox" / "cache",
        )
        runner = PythonQARunner(
            cwd=project,
            executor=ContainerSubprocessExecutor(cwd=project, mounts=mounts, image=_UV_IMAGE),
        )

        result = runner.run_tests(".", kind="")

        assert result.errors == 1 and result.passed == 0, (
            f"an absent toolchain did not report as an error: {result}"
        )
        message = result.failures[0].message
        assert "/cache" not in message, f"an internal container path reached the user:\n{message}"
        assert "not a test failure" in message.lower(), message
        assert "Declare pytest" in message, message


class TestNonPythonToolchainsRunInTheContainer:
    """Rust and Maven inside the sandbox, which is what `US-03` P-4 has been waiting for.

    The prepare phase existed for Python only, so these projects reached an execute phase that has
    `--network none` with nothing fetched. The mount layout already allowed the fix: `/cache` is
    read-write while preparing and read-only during the run, `/scratch` is read-write during the run,
    and `/workspace` is read-only throughout — so dependencies are fetched once and builds write to
    scratch, never into the project.

    Proves: TECH-031 FR-17
    """

    @pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
    @pytest.mark.skipif(not _rust_image_available(), reason=f"{_RUST_IMAGE} not present locally")
    def test_a_rust_crate_runs_inside_the_sandbox(self, tmp_path: Path) -> None:
        """The whole chain: fetch with network, build and run without, source tree untouched."""
        image = _RUST_IMAGE
        project = tmp_path / "crate"
        (project / "src").mkdir(parents=True)
        (project / "Cargo.toml").write_text(
            '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8"
        )
        (project / "src" / "lib.rs").write_text(
            "pub fn v() -> i32 { 42 }\n\n#[cfg(test)]\nmod t {\n"
            "    #[test]\n    fn works() { assert_eq!(super::v(), 42); }\n}\n",
            encoding="utf-8",
        )
        subprocess.run(["cargo", "generate-lockfile", "-q"], cwd=project, check=True, timeout=300)

        mounts = ContainerMounts(
            source_root=project,
            scratch_root=project / ".specweaver" / ".sandbox" / "scratch",
            cache_root=project / ".specweaver" / ".sandbox" / "cache",
        )
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        result = RustRunner(
            cwd=project,
            executor=ContainerSubprocessExecutor(cwd=project, mounts=mounts, image=image),
        ).run_tests(".", timeout=900)

        assert result.passed == 1 and result.failed == 0, result
        assert not (project / "target").exists(), (
            "the build wrote into the project; `CARGO_TARGET_DIR` must point at /scratch"
        )
        # A pass alone would not prove the container did the work — the runner would report the same
        # if it had somehow run on the host. These are artefacts only the container could leave.
        assert list(mounts.scratch_root.rglob("target/debug/deps/probe*")), (
            "no build artefacts in the scratch mount, so nothing was compiled inside the sandbox"
        )
        assert (mounts.cache_root / "cargo").exists(), (
            "the prepare phase fetched nothing into the cache the offline run reads from"
        )

    def test_a_crate_without_a_lockfile_is_refused_with_its_reason(self, tmp_path: Path) -> None:
        """The control. Resolving writes `Cargo.lock` into a read-only mount, so this cannot run —
        and saying which one command fixes it is the difference between unsupported and broken.

        No toolchain needed: the refusal is decided from the manifest, before anything runs.
        """
        project = tmp_path / "nolock"
        (project / "src").mkdir(parents=True)
        (project / "Cargo.toml").write_text(
            '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8"
        )
        (project / "src" / "lib.rs").write_text("pub fn v() -> i32 { 42 }\n", encoding="utf-8")

        from specweaver.commons.prepare_plan import plan_for

        plan = plan_for(project)

        assert plan.steps == ()
        assert any("Cargo.lock" in w for w in plan.warnings), plan.warnings
