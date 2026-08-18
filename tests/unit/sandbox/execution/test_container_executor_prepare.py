# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`TECH-031`: whether the prepare phase produces an environment the QA runner can actually use.

Split out of `test_container_executor.py`, which covers the executor's argv construction and
delegation contract. This module covers one question that runs the other way: given a real target
project, does the phase build a toolchain, and is it the toolchain the execute phase then finds?
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.container_executor import (
    ContainerSubprocessExecutor,
    _groups_holding_a_runner,
)
from specweaver.sandbox.execution.executor import SubprocessExecutor
from tests.fixtures.container_sandbox import find_call as _find_call
from tests.fixtures.container_sandbox import mounts as _mounts
from tests.fixtures.container_sandbox import ok_result as _ok_result

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.models import ContainerMounts


# ---------------------------------------------------------------------------
# TECH-031: the prepare phase has never produced a usable environment
# ---------------------------------------------------------------------------


class TestEnsurePreparedProducesAUsableEnvironment:
    """Three walls stand between `uv sync` and a venv the QA runner can use.

    Re-measured against live podman 2026-08-18, six days after the ticket recorded them, and every
    one still reproduces verbatim:

    1. `uv` writes `.venv` into the workdir, which is mounted `:ro` inside a `--read-only` container:
       `failed to create directory /workspace/.venv: Read-only file system (os error 30)`, exit 2 —
       for *every* project, on every layout, before the manifest is even read.
    2. With the venv redirected, a target whose lockfile is stale makes `uv` re-resolve and rewrite
       `/workspace/uv.lock`, which fails the same way. Measured: a lockfile that is merely *present*
       is not enough — adding one dependency after locking is sufficient to trigger it.
    3. Even with both fixed, the execute phase set no `PATH`, so `python -m pytest` resolved to the
       image's interpreter rather than the environment just prepared.

    The fourth defect — the QA runner reporting an absent toolchain as success — is already fixed and
    is what kept the other three invisible.
    """

    def _prepare_cmd(self, tmp_path: Path, monkeypatch) -> list[str]:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-content-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)._ensure_prepared()
        call = _find_call(mock_execute, "uv", "sync")
        assert call is not None, "the prepare phase did not run at all"
        return list(call)

    def test_the_venv_is_built_on_a_writable_mount(self, tmp_path: Path, monkeypatch) -> None:
        """Wall 1. Without this the phase cannot create an environment for any project at all."""
        cmd = self._prepare_cmd(tmp_path, monkeypatch)

        assert any(arg.startswith("UV_PROJECT_ENVIRONMENT=") for arg in cmd), (
            f"`uv` defaults to `.venv` in the workdir, which is mounted read-only:\n{cmd}"
        )
        target = next(a for a in cmd if a.startswith("UV_PROJECT_ENVIRONMENT="))
        assert target.split("=", 1)[1].startswith("/cache"), (
            f"the environment must land on the rw cache mount, not {target}"
        )

    def test_the_lockfile_is_never_rewritten(self, tmp_path: Path, monkeypatch) -> None:
        """Wall 2. A stale lockfile makes `uv` rewrite it, into a read-only mount."""
        cmd = self._prepare_cmd(tmp_path, monkeypatch)

        assert "--frozen" in cmd, (
            "without `--frozen` a target whose lockfile has drifted fails with a read-only error "
            f"that names uv.lock and explains nothing:\n{cmd}"
        )

    def test_the_execute_phase_uses_what_prepare_built(self, tmp_path: Path, monkeypatch) -> None:
        """Wall 3. Fixing the first two changes nothing observable without this one."""
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))

        cmd = executor._build_container_cmd("podman", "n", ["python", "-m", "pytest"], None)

        path_env = [a for a in cmd if a.startswith("PATH=")]
        assert path_env, f"no PATH is set, so `python -m pytest` is the image's interpreter:\n{cmd}"
        assert "/cache/venv/bin" in path_env[0], (
            f"PATH does not put the prepared environment first: {path_env[0]}"
        )

    def test_a_failed_prepare_is_surfaced_not_logged(self, tmp_path: Path, monkeypatch) -> None:
        """A warning nobody reads is why this survived: the failure must reach the caller.

        The QA runner's own vacuous-success defect is fixed, so a missing toolchain now reports
        honestly — but only if the prepare phase's own failure is not swallowed one level earlier.
        """
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-content-v1")

        def only_sync_fails(cmd, **kwargs):
            # Failing every call would fail the engine probe first, and the test would pass for a
            # reason that has nothing to do with the prepare phase.
            return _ok_result(exit_code=2) if "sync" in cmd else _ok_result()

        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(side_effect=only_sync_fails))
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        with pytest.raises(RuntimeError, match="prepare"):
            executor._ensure_prepared()


# ---------------------------------------------------------------------------
# TECH-031: the runner is often in a group `uv sync` does not install
# ---------------------------------------------------------------------------


class TestEnsurePreparedSyncsTheGroupHoldingTheRunner:
    """Being on the supported layout is not sufficient — the group has to be the one uv syncs.

    `uv sync` installs the `dev` group and nothing else. Measured across the 150 most-downloaded
    PyPI packages (`docs/analysis/dependency_layout_corpus_2026-08-18.md`): 50 of the 121 resolvable
    repositories declare PEP 735 groups, and only 40 name one `dev`. `test` (17) and `tests` (9) are
    common, so a project can sit exactly on the layout the prepare phase supports and still get a
    venv with no test runner in it.

    Detection is by content, not by name, and the corpus is why. The group names are a long tail —
    `testing`, `ci`, `test-core` and `dev-base` all carry pytest — so no name
    list covers them. The tail also cuts the other way: SQLAlchemy declares `tests-postgresql`,
    `tests-mysql` and `tests-oracle`, which hold database drivers and no runner at all, so a
    `test*` prefix rule would install three database stacks to find nothing.

    A name list is not merely incomplete, it is unsafe: `uv sync --group nosuchgroup` exits 2 with
    *"Group `nosuchgroup` is not defined"* (verified against uv 0.12.3), so passing a speculative
    name breaks every project that does not happen to use it. Only groups the manifest actually
    declares may ever be passed.
    """

    def _sync_cmd(self, tmp_path: Path, monkeypatch, pyproject: str) -> list[str]:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-content-v1")
        (mounts.source_root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)._ensure_prepared()
        call = _find_call(mock_execute, "uv", "sync")
        assert call is not None, "the prepare phase did not run at all"
        return list(call)

    @staticmethod
    def _groups(cmd: list[str]) -> list[str]:
        return [cmd[i + 1] for i, a in enumerate(cmd) if a == "--group" and i + 1 < len(cmd)]

    def test_a_runner_outside_dev_is_still_installed(self, tmp_path: Path, monkeypatch) -> None:
        """The defect itself: 26 corpus projects put the runner in `test`/`tests`, not `dev`."""
        cmd = self._sync_cmd(
            tmp_path,
            monkeypatch,
            '[project]\nname = "t"\nversion = "0"\ndependencies = []\n\n'
            '[dependency-groups]\ndev = ["ruff"]\ntests = ["pytest>=8"]\n',
        )

        assert "tests" in self._groups(cmd), (
            "the runner lives in `tests`, which `uv sync` does not install by default, so the "
            f"prepared venv has no pytest and the QA run reports against the image:\n{cmd}"
        )

    def test_a_group_without_a_runner_is_left_alone(self, tmp_path: Path, monkeypatch) -> None:
        """The control, and the test above is worth nothing without it.

        `--all-groups` would satisfy the assertion above while installing every documentation and
        release toolchain the project declares — slower, and one unresolvable doc dependency would
        fail the whole prepare phase for a project whose tests were fine.
        """
        cmd = self._sync_cmd(
            tmp_path,
            monkeypatch,
            '[project]\nname = "t"\nversion = "0"\ndependencies = []\n\n'
            '[dependency-groups]\ntests = ["pytest"]\ndocs = ["sphinx"]\n'
            'tests-postgresql = ["psycopg2"]\n',
        )

        groups = self._groups(cmd)
        assert "docs" not in groups, f"a documentation toolchain was installed to run tests:\n{cmd}"
        assert "tests-postgresql" not in groups, (
            f"a name-shaped rule pulled a database stack that declares no runner:\n{cmd}"
        )

    def test_only_groups_the_manifest_declares_are_passed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A speculative `--group test` is not a harmless miss — uv exits 2 and prepares nothing."""
        cmd = self._sync_cmd(
            tmp_path,
            monkeypatch,
            '[project]\nname = "t"\nversion = "0"\ndependencies = []\n\n'
            '[dependency-groups]\ndev = ["pytest"]\n',
        )

        assert self._groups(cmd) == [], (
            "no group beyond the default was declared with a runner, so nothing may be requested; "
            f"uv fails hard on a group that is not defined:\n{cmd}"
        )

    def test_a_manifest_that_cannot_be_parsed_does_not_break_prepare(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Group detection is an improvement to the sync, never a new way for it to fail."""
        cmd = self._sync_cmd(tmp_path, monkeypatch, "this is not [ valid toml\n")

        assert self._groups(cmd) == []
        assert "sync" in cmd and "--frozen" in cmd, f"the prepare phase stopped working:\n{cmd}"


class TestGroupsHoldingARunnerReadsDependencySpecs:
    """The detector matches distribution names, and a dependency spec is not a bare name.

    Every form here appears in the measured corpus. A naive `"pytest" in dep` would accept
    `pytest-httpserver` (fine) and also `no-pytest-please` (not), while an equality test against the
    raw string accepts none of them.
    """

    @pytest.mark.parametrize(
        "spec",
        [
            "pytest",
            "pytest>=8.0",
            "pytest ; python_version >= '3.11'",
            "pytest[testing]>=7",
            "pytest_asyncio",
            "PyTest",
            "pytest-cov>=5",
        ],
    )
    def test_a_runner_is_recognised_through_its_spec(self, spec: str) -> None:
        manifest = f'[dependency-groups]\nqa = ["{spec}"]\n'
        assert _groups_holding_a_runner(manifest) == ["qa"], f"{spec!r} was not read as a runner"

    @pytest.mark.parametrize(
        "spec",
        [
            "psycopg2",
            "sphinx",
            "coverage",  # measures a run, cannot start one
            "nox",  # orchestrates its own environments; leaves `python -m pytest` failing
            "tox-uv",  # same, and installing it widens what an untrusted project builds
            "my-pytest-plugin",  # names the runner, is not it
        ],
    )
    def test_a_non_runner_does_not_pull_its_group_in(self, spec: str) -> None:
        manifest = f'[dependency-groups]\nextra = ["{spec}"]\n'
        assert _groups_holding_a_runner(manifest) == [], f"{spec!r} was mistaken for a runner"

    def test_the_default_group_is_reported_and_filtered_per_path(self) -> None:
        """`dev` is returned here, not dropped, because the two prepare paths disagree about it.

        `uv sync` installs `dev` unasked, so the sync path filters it out as noise. `uv pip install`
        installs nothing it is not given, so the lockless path must name it — and `dev` is the most
        common runner location. Filtering at the source would have stripped it from both.
        """
        assert _groups_holding_a_runner('[dependency-groups]\ndev = ["pytest"]\n') == ["dev"]

    def test_an_include_group_reference_is_not_a_dependency(self) -> None:
        """PEP 735 lets a group include another. The included group is judged on its own entries."""
        manifest = (
            '[dependency-groups]\ntests = ["pytest"]\nci = [{include-group = "tests"}, "codecov"]\n'
        )
        assert _groups_holding_a_runner(manifest) == ["tests"]

    @pytest.mark.parametrize(
        "manifest",
        [
            "this is not [ valid toml",
            "",
            '[project]\nname = "x"\n',  # no groups table at all
            "[dependency-groups]\nbroken = 42\n",  # a group that is not a list
        ],
    )
    def test_a_manifest_it_cannot_read_yields_nothing(self, manifest: str) -> None:
        assert _groups_holding_a_runner(manifest) == []


class TestEnsurePreparedStampsEveryCommandInput:
    """The prepare phase is skipped when a stamp matches, so the stamp must cover every input.

    It used to be keyed on the lockfile alone, which was true while the lockfile was the only thing
    the command depended on. Group detection reads `pyproject.toml`, so moving a runner between
    groups now changes the command without touching `uv.lock` — and a stamp that ignored the
    manifest would keep serving the environment built before the move, forever.
    """

    def _prepare(
        self, tmp_path: Path, mounts: ContainerMounts, monkeypatch, pyproject: str
    ) -> list[str] | None:
        """Run the prepare phase against one project. Returns the `uv sync` argv, or None if the
        stamp suppressed it."""
        (mounts.source_root / "uv.lock").write_text("unchanged-lockfile")
        (mounts.source_root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)._ensure_prepared()
        call = _find_call(mock_execute, "uv", "sync")
        return None if call is None else list(call)

    def test_moving_the_runner_between_groups_rebuilds_the_environment(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        mounts = _mounts(tmp_path)
        before = '[dependency-groups]\ndev = ["pytest"]\n'
        after = '[dependency-groups]\ndev = ["ruff"]\ntests = ["pytest"]\n'

        first = self._prepare(tmp_path, mounts, monkeypatch, before)
        assert first is not None and "--group" not in first

        second = self._prepare(tmp_path, mounts, monkeypatch, after)

        assert second is not None, (
            "the stamp from the previous manifest suppressed the prepare phase, so the venv still "
            "has no pytest and nothing will ever rebuild it"
        )
        assert "tests" in second, (
            f"the rebuilt environment still misses the runner group:\n{second}"
        )

    def test_an_unchanged_project_is_not_rebuilt(self, tmp_path: Path, monkeypatch) -> None:
        """The control: the stamp must still do its job, or the fix above is just a disabled cache."""
        mounts = _mounts(tmp_path)
        manifest = '[dependency-groups]\ntests = ["pytest"]\n'

        assert self._prepare(tmp_path, mounts, monkeypatch, manifest) is not None
        assert self._prepare(tmp_path, mounts, monkeypatch, manifest) is None, (
            "an unchanged project re-ran `uv sync`, so the stamp no longer caches anything"
        )


class TestEnsurePreparedResolvesWithoutACommittedLockfile:
    """Rung 1 of the gap: a project with no `uv.lock` used to get no environment at all.

    `uv sync --frozen` refuses without a lockfile, and dropping `--frozen` does not help — `uv`
    then tries to *write* `uv.lock` into `/workspace`, which is mounted read-only. Measured against
    the corpus (`docs/analysis/dependency_layout_corpus_2026-08-18.md`), 20 of 121 repositories
    declare pytest in `pyproject.toml` and commit no lockfile, so this path alone doubles the
    supported share.

    The route is `uv venv` followed by `uv pip install`, which resolves from the manifest and needs
    nothing writable in the source tree — verified against live podman before it was written here.
    It differs from the sync path in one way that is easy to get wrong: **`uv pip install` does not
    install the `dev` group unless asked**, where `uv sync` always does. A path that reused the sync
    path's group list would silently drop the most common runner location.
    """

    def _steps(
        self, tmp_path: Path, monkeypatch, *, lockfile: bool, pyproject: str
    ) -> list[list[str]]:
        mounts = _mounts(tmp_path)
        if lockfile:
            (mounts.source_root / "uv.lock").write_text("lockfile-content-v1")
        (mounts.source_root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)._ensure_prepared()
        # The uv command only, not the whole container argv. The argv carries `-v …:/workspace:ro`
        # and `--workdir /workspace`, so asserting `/workspace` against it passes whether or not
        # the project is handed to `uv pip install` — which is how the first version of
        # `test_the_project_itself_is_installed` passed against a mutant that removed it.
        return [
            list(call.args[0])[list(call.args[0]).index("uv") :]
            for call in mock_execute.call_args_list
            if call.args and "uv" in call.args[0]
        ]

    _MANIFEST = (
        '[project]\nname = "t"\nversion = "0"\ndependencies = []\n\n'
        '[dependency-groups]\ndev = ["pytest"]\ndocs = ["sphinx"]\n'
    )

    def test_a_project_without_a_lockfile_is_still_prepared(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        steps = self._steps(tmp_path, monkeypatch, lockfile=False, pyproject=self._MANIFEST)

        assert steps, "no environment was built at all for a project with no lockfile"
        joined = [" ".join(s) for s in steps]
        assert any("uv venv" in j for j in joined), f"no environment was created:\n{joined}"
        assert any("uv pip install" in j for j in joined), (
            f"nothing was installed into it:\n{joined}"
        )
        assert not any("sync" in j for j in joined), (
            f"`uv sync` cannot work without a lockfile; it must not be attempted:\n{joined}"
        )

    def test_the_default_group_is_requested_explicitly_off_the_sync_path(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`uv pip install` installs no group unless named, including `dev`."""
        steps = self._steps(tmp_path, monkeypatch, lockfile=False, pyproject=self._MANIFEST)

        install = next(s for s in steps if "pip" in s)
        groups = [install[i + 1] for i, a in enumerate(install) if a == "--group"]
        assert "dev" in groups, (
            f"the runner lives in `dev`, and unlike `uv sync` this path does not install it "
            f"unasked, so the environment has no pytest:\n{install}"
        )
        assert "docs" not in groups, f"a documentation toolchain was installed:\n{install}"

    def test_the_project_itself_is_installed(self, tmp_path: Path, monkeypatch) -> None:
        """Without it the runner has pytest and the tests cannot import what they test.

        Measured live: omitting the target leaves `python -m pytest` collecting
        `ModuleNotFoundError` for the project's own package — pytest present, suite unrunnable.
        """
        steps = self._steps(tmp_path, monkeypatch, lockfile=False, pyproject=self._MANIFEST)

        install = next(s for s in steps if "pip" in s)
        assert "/workspace" in install, (
            f"only the tooling was installed, not the project under test:\n{install}"
        )

    def test_a_lockfile_still_takes_the_reproducible_path(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The control. Resolving fresh when a lockfile exists would throw away the project's pins.

        Without this the cheapest way to pass every other test in this class is to route every
        project through `uv pip install`, which silently stops reproducing what the project's own
        CI runs.
        """
        steps = self._steps(tmp_path, monkeypatch, lockfile=True, pyproject=self._MANIFEST)

        joined = [" ".join(s) for s in steps]
        assert any("sync --frozen" in j for j in joined), (
            f"a committed lockfile was ignored in favour of a fresh resolution:\n{joined}"
        )
        assert not any("pip install" in j for j in joined), joined


class TestEnsurePreparedFallsBackToOtherDeclarationSites:
    """Rung 2: 48 of 121 corpus repositories declare pytest outside `pyproject.toml`.

    Reading those files is worth nothing on its own — of the 68 projects in the two reachable
    failure classes only 29 committed a lockfile, so before rung 1 this recovered nine. With the
    lockless route in place it recovers 27 of the 48, taking the corpus from 33% to 55%.

    The reader is in `tooling_sources` and has its own tests, including a run against all 30 real
    `tox.ini` files from the corpus. What is asserted here is the wiring and, more importantly, when
    it must *not* fire.
    """

    def _uv_steps(self, tmp_path: Path, monkeypatch, files: dict[str, str]) -> list[list[str]]:
        mounts = _mounts(tmp_path)
        for name, text in files.items():
            path = mounts.source_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)._ensure_prepared()
        return [
            list(call.args[0])[list(call.args[0]).index("uv") :]
            for call in mock_execute.call_args_list
            if call.args and "uv" in call.args[0]
        ]

    _NO_RUNNER = '[project]\nname = "t"\nversion = "0"\ndependencies = []\n'

    def test_a_requirements_file_is_installed_when_the_manifest_has_no_runner(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        steps = self._uv_steps(
            tmp_path,
            monkeypatch,
            {
                "pyproject.toml": self._NO_RUNNER,
                "uv.lock": "locked",
                "requirements-dev.txt": "pytest>=8\npytest-cov\n",
            },
        )

        flat = [" ".join(s) for s in steps]
        assert any("-r /workspace/requirements-dev.txt" in f for f in flat), (
            f"the project declares pytest in a file we can read, and it was ignored:\n{flat}"
        )

    def test_tox_packages_are_installed_by_name(self, tmp_path: Path, monkeypatch) -> None:
        steps = self._uv_steps(
            tmp_path,
            monkeypatch,
            {
                "pyproject.toml": self._NO_RUNNER,
                "uv.lock": "locked",
                "tox.ini": "[testenv]\ndeps =\n    pytest>=8\n    pytest-cov\n",
            },
        )

        install = next((s for s in steps if "pip" in s), None)
        assert install is not None, f"nothing was installed from tox.ini:\n{steps}"
        assert "pytest>=8" in install and "pytest-cov" in install, install

    def test_a_manifest_that_declares_pytest_is_not_second_guessed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The control, and the one that matters most.

        A project that declares pytest in its manifest is already served by the lockfile it pinned.
        Installing a `tox.ini` block over the top would add a second, unpinned set of versions on
        top of a resolution the project controls — turning a reproducible run into a mixed one for
        no gain at all.
        """
        steps = self._uv_steps(
            tmp_path,
            monkeypatch,
            {
                "pyproject.toml": '[project]\nname = "t"\nversion = "0"\ndependencies = []\n\n'
                '[dependency-groups]\ndev = ["pytest"]\n',
                "uv.lock": "locked",
                "tox.ini": "[testenv]\ndeps =\n    pytest==1.0\n",
            },
        )

        flat = [" ".join(s) for s in steps]
        assert not any("pytest==1.0" in f for f in flat), (
            f"a tox pin was layered over the project's own locked resolution:\n{flat}"
        )

    def test_a_runtime_dependency_on_pytest_also_counts_as_declared(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Rare, but real: a testing library ships pytest as a runtime dependency."""
        steps = self._uv_steps(
            tmp_path,
            monkeypatch,
            {
                "pyproject.toml": '[project]\nname = "t"\nversion = "0"\n'
                'dependencies = ["pytest>=8"]\n',
                "uv.lock": "locked",
                "tox.ini": "[testenv]\ndeps =\n    pytest==1.0\n",
            },
        )

        flat = [" ".join(s) for s in steps]
        assert not any("pytest==1.0" in f for f in flat), flat

    def test_changing_the_fallback_file_rebuilds_the_environment(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The stamp must cover every input to the command, and this is now one of them."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(self._NO_RUNNER, encoding="utf-8")
        (mounts.source_root / "uv.lock").write_text("locked", encoding="utf-8")
        req = mounts.source_root / "requirements-dev.txt"
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )

        def prepare(text: str) -> bool:
            req.write_text(text, encoding="utf-8")
            mock = MagicMock(return_value=_ok_result())
            monkeypatch.setattr(SubprocessExecutor, "execute", mock)
            ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)._ensure_prepared()
            return _find_call(mock, "uv", "pip") is not None

        assert prepare("pytest>=8\n")
        assert not prepare("pytest>=8\n"), (
            "an unchanged project was rebuilt; the stamp caches nothing"
        )
        assert prepare("pytest>=8\npytest-asyncio\n"), (
            "the requirements file changed and the stamp served the old environment anyway"
        )
