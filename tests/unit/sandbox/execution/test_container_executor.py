# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ContainerMounts and ContainerSubprocessExecutor (INT-US-09 SF-01)."""

from __future__ import annotations

import dataclasses
import os
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.container_executor import (
    ContainerEngineUnavailableError,
    ContainerSubprocessExecutor,
)
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ContainerMounts, SubprocessResult

if TYPE_CHECKING:
    from pathlib import Path


def _ok_result(stdout: str = "", exit_code: int = 0) -> SubprocessResult:
    return SubprocessResult(exit_code=exit_code, stdout=stdout, stderr="", duration_seconds=0.01)


def _mounts(tmp_path: Path) -> ContainerMounts:
    source_root = tmp_path / "project"
    source_root.mkdir()
    return ContainerMounts(
        source_root=source_root,
        scratch_root=source_root / ".specweaver" / ".sandbox" / "scratch",
        cache_root=source_root / ".specweaver" / ".sandbox" / "cache",
    )


def _find_call(mock_execute: MagicMock, *needles: str) -> list | None:
    """Return the argv of the first recorded call containing all needles, or None."""
    for call in mock_execute.call_args_list:
        argv = call.args[0] if call.args else call.kwargs.get("cmd")
        if argv and all(any(needle in str(part) for part in argv) for needle in needles):
            return argv
    return None


# ---------------------------------------------------------------------------
# T1: ContainerMounts
# ---------------------------------------------------------------------------


class TestContainerMounts:
    """Tests for the ContainerMounts frozen dataclass."""

    def test_create_with_all_fields(self, tmp_path: Path) -> None:
        mounts = ContainerMounts(
            source_root=tmp_path / "src",
            scratch_root=tmp_path / "scratch",
            cache_root=tmp_path / "cache",
        )
        assert mounts.source_root == tmp_path / "src"
        assert mounts.scratch_root == tmp_path / "scratch"
        assert mounts.cache_root == tmp_path / "cache"

    def test_frozen_cannot_mutate(self, tmp_path: Path) -> None:
        mounts = ContainerMounts(
            source_root=tmp_path / "src",
            scratch_root=tmp_path / "scratch",
            cache_root=tmp_path / "cache",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            mounts.source_root = tmp_path / "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T2: Engine detection (_ensure_engine)
# ---------------------------------------------------------------------------


class TestEngineDetection:
    """Tests for lazy, memoized podman/docker detection."""

    def test_prefers_podman_when_both_available(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        engine = executor._ensure_engine()

        assert engine == "/usr/bin/podman"

    def test_falls_back_to_docker_when_podman_absent(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: None if name == "podman" else f"/usr/bin/{name}",
        )
        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(return_value=_ok_result()))

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        engine = executor._ensure_engine()

        assert engine == "/usr/bin/docker"

    def test_detection_cached_after_first_call(self, tmp_path, monkeypatch) -> None:
        which_mock = MagicMock(side_effect=lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which", which_mock
        )
        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(return_value=_ok_result()))

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        executor._ensure_engine()
        executor._ensure_engine()

        assert which_mock.call_count == 1

    def test_engine_unavailable_raises_typed_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which", lambda name: None
        )
        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(return_value=_ok_result()))

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        with pytest.raises(ContainerEngineUnavailableError, match="podman"):
            executor._ensure_engine()

    def test_engine_on_path_but_not_live_raises(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        monkeypatch.setattr(
            SubprocessExecutor, "execute", MagicMock(return_value=_ok_result(exit_code=1))
        )

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        with pytest.raises(ContainerEngineUnavailableError):
            executor._ensure_engine()

    def test_falls_through_dead_podman_to_live_docker(self, tmp_path, monkeypatch) -> None:
        """Partial fallback: podman is on PATH but dead, docker is on PATH and live."""
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )

        def probe_side_effect(cmd, **kwargs):
            if cmd[0] == "/usr/bin/podman":
                return _ok_result(exit_code=1)
            return _ok_result(exit_code=0)

        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(side_effect=probe_side_effect))

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        engine = executor._ensure_engine()

        assert engine == "/usr/bin/docker"


# ---------------------------------------------------------------------------
# T3: Construction — mount handling, lazy dir creation, image resolution
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_scratch_and_cache_dirs_created_lazily(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        assert not mounts.scratch_root.exists()
        assert not mounts.cache_root.exists()

        ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        assert mounts.scratch_root.is_dir()
        assert mounts.cache_root.is_dir()

    def test_image_defaults_from_requires_python(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.12"\n'
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.12")

    def test_image_defaults_to_latest_when_pyproject_absent(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.13")

    def test_image_defaults_to_latest_when_requires_python_unparseable(
        self, tmp_path: Path
    ) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text("not valid toml [[[")
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.13")

    def test_explicit_image_overrides_detection(self, tmp_path: Path) -> None:
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=_mounts(tmp_path), image="my-custom-image:latest"
        )
        assert executor._image == "my-custom-image:latest"

    def test_image_clamps_below_oldest_supported_tag(self, tmp_path: Path) -> None:
        """requires-python below 3.11 clamps to the oldest supported tag, not a literal 3.9."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.9"\n'
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.11")

    def test_image_clamps_above_newest_supported_tag(self, tmp_path: Path) -> None:
        """requires-python above 3.13 clamps to the default tag, not a literal 3.14."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.14"\n'
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.13")

    def test_image_defaults_when_requires_python_does_not_match_version_regex(
        self, tmp_path: Path
    ) -> None:
        """An empty/unversioned requires-python takes the 'no match' branch, not the
        'pyproject.toml absent' branch — same outcome, different code path."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text('[project]\nrequires-python = ""\n')
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.13")

    def test_image_defaults_when_requires_python_is_not_a_string(self, tmp_path: Path) -> None:
        """A non-string requires-python (TOML int) raises TypeError inside re.search,
        caught, falling back to the default tag rather than crashing construction."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            "[project]\nrequires-python = 312\n"
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        assert executor._image.endswith(":3.13")


# ---------------------------------------------------------------------------
# T4: _build_container_cmd — mounts, network, caps, resource limits, user flag
# ---------------------------------------------------------------------------


class TestBuildContainerCmd:
    def test_read_only_source_mount_present(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        argv = executor._build_container_cmd("podman", "n1", ["echo", "hi"], None)
        assert "--read-only" in argv
        assert f"{mounts.source_root}:/workspace:ro" in argv

    def test_writable_scratch_mount_present_and_distinct(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        argv = executor._build_container_cmd("podman", "n1", ["echo", "hi"], None)
        assert f"{mounts.scratch_root}:/scratch:rw" in argv
        assert f"{mounts.source_root}:/workspace:ro" != f"{mounts.scratch_root}:/scratch:rw"

    def test_network_none_present(self, tmp_path: Path) -> None:
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        argv = executor._build_container_cmd("podman", "n1", ["echo"], None)
        idx = argv.index("--network")
        assert argv[idx + 1] == "none"

    def test_capabilities_dropped(self, tmp_path: Path) -> None:
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        argv = executor._build_container_cmd("podman", "n1", ["echo"], None)
        assert "--cap-drop" in argv
        assert "ALL" in argv
        assert "--security-opt" in argv
        assert "no-new-privileges:true" in argv

    def test_resource_limits_match_bash_action_atom_defaults(self, tmp_path: Path) -> None:
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        argv = executor._build_container_cmd("podman", "n1", ["echo"], None)
        mem_idx = argv.index("--memory")
        pids_idx = argv.index("--pids-limit")
        assert argv[mem_idx + 1] == "2147483648"
        assert argv[pids_idx + 1] == "128"

    def test_user_flag_matches_invoking_uid_on_linux(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(os, "getuid", lambda: 1000, raising=False)
        monkeypatch.setattr(os, "getgid", lambda: 1000, raising=False)

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        argv = executor._build_container_cmd("podman", "n1", ["echo"], None)

        idx = argv.index("--user")
        assert argv[idx + 1] == "1000:1000"

    def test_user_flag_omitted_on_windows_with_warning(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        monkeypatch.setattr(sys, "platform", "win32")

        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        with caplog.at_level("WARNING"):
            argv = executor._build_container_cmd("podman", "n1", ["echo"], None)

        assert "--user" not in argv
        assert any("Windows" in rec.message for rec in caplog.records)

    def test_extra_env_becomes_dash_e_flags(self, tmp_path: Path) -> None:
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))
        argv = executor._build_container_cmd("podman", "n1", ["echo"], {"MY_VAR": "value"})
        assert "-e" in argv
        assert "MY_VAR=value" in argv

    def test_final_argv_ends_with_image_and_original_cmd(self, tmp_path: Path) -> None:
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=_mounts(tmp_path), image="pinned:tag"
        )
        argv = executor._build_container_cmd("podman", "n1", ["python", "-m", "pytest"], None)
        assert argv[-4:] == ["pinned:tag", "python", "-m", "pytest"]


# ---------------------------------------------------------------------------
# T5: execute() override — naming, cleanup, result passthrough
# ---------------------------------------------------------------------------


class TestExecuteOverride:
    def _executor(self, tmp_path: Path, monkeypatch, run_id: str = "run123") -> ContainerSubprocessExecutor:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        return ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=_mounts(tmp_path), run_id=run_id
        )

    def test_deterministic_name_includes_run_id_and_uuid_suffix(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = self._executor(tmp_path, monkeypatch, run_id="abc123")

        executor.execute(["python", "-m", "pytest"])

        run_argv = _find_call(mock_execute, "run", "--name")
        assert run_argv is not None
        name = run_argv[run_argv.index("--name") + 1]
        assert name.startswith("specweaver-qa-abc123-")
        suffix = name.removeprefix("specweaver-qa-abc123-")
        assert len(suffix) == 8

    def test_cleanup_runs_before_and_after_execution(self, tmp_path: Path, monkeypatch) -> None:
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = self._executor(tmp_path, monkeypatch)

        executor.execute(["python", "-m", "pytest"])

        rm_calls = [
            call
            for call in mock_execute.call_args_list
            if call.args and "rm" in call.args[0] and "-f" in call.args[0]
        ]
        assert len(rm_calls) == 2

    def test_cleanup_runs_on_super_execute_exception(self, tmp_path: Path, monkeypatch) -> None:
        def side_effect(cmd, **kwargs):
            if "info" in cmd:
                return _ok_result()
            if "rm" in cmd:
                return _ok_result()
            raise RuntimeError("boom")

        mock_execute = MagicMock(side_effect=side_effect)
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = self._executor(tmp_path, monkeypatch)

        with pytest.raises(RuntimeError, match="boom"):
            executor.execute(["python", "-m", "pytest"])

        rm_calls = [
            call
            for call in mock_execute.call_args_list
            if call.args and "rm" in call.args[0] and "-f" in call.args[0]
        ]
        assert len(rm_calls) == 2

    def test_cwd_override_ignored_with_warning(self, tmp_path: Path, monkeypatch, caplog) -> None:
        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(return_value=_ok_result()))
        executor = self._executor(tmp_path, monkeypatch)

        other_dir = tmp_path / "other"
        other_dir.mkdir()
        with caplog.at_level("WARNING"):
            executor.execute(["echo"], cwd_override=other_dir)

        assert any("cwd_override" in rec.message for rec in caplog.records)

    def test_result_contract_unchanged_shape(self, tmp_path: Path, monkeypatch) -> None:
        expected = _ok_result(stdout="5 passed in 0.5s")
        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(return_value=expected))
        executor = self._executor(tmp_path, monkeypatch)

        result = executor.execute(["python", "-m", "pytest"])

        assert isinstance(result, SubprocessResult)
        assert result.stdout == "5 passed in 0.5s"
        assert result.exit_code == 0

    def test_engine_unavailable_propagates_before_any_run(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which", lambda name: None
        )
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))

        with pytest.raises(ContainerEngineUnavailableError):
            executor.execute(["python", "-m", "pytest"])

        assert mock_execute.call_count == 0

    def test_input_text_forwarded_to_wrapped_run(self, tmp_path: Path, monkeypatch) -> None:
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = self._executor(tmp_path, monkeypatch)

        executor.execute(["cat"], input_text="piped stdin content")

        run_call = next(
            call for call in mock_execute.call_args_list if call.args and "cat" in call.args[0]
        )
        assert run_call.kwargs.get("input_text") == "piped stdin content"

    def test_timeout_seconds_forwarded_to_wrapped_run(self, tmp_path: Path, monkeypatch) -> None:
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = self._executor(tmp_path, monkeypatch)

        executor.execute(["python", "-m", "pytest"], timeout_seconds=999)

        run_call = next(
            call
            for call in mock_execute.call_args_list
            if call.args and "pytest" in call.args[0]
        )
        assert run_call.kwargs.get("timeout_seconds") == 999
        # Distinct from the fixed 5s engine-probe / 10s cleanup timeouts elsewhere.
        other_timeouts = {
            call.kwargs.get("timeout_seconds")
            for call in mock_execute.call_args_list
            if call is not run_call
        }
        assert 999 not in other_timeouts


# ---------------------------------------------------------------------------
# T6: _ensure_prepared — lockfile-hash-gated uv sync prepare phase
# ---------------------------------------------------------------------------


class TestEnsurePrepared:
    def _executor(self, tmp_path: Path, monkeypatch) -> ContainerSubprocessExecutor:
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        return ContainerSubprocessExecutor(cwd=tmp_path, mounts=_mounts(tmp_path))

    def test_prepare_skipped_when_no_lockfile_or_pyproject(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = self._executor(tmp_path, monkeypatch)

        executor._ensure_prepared()

        assert _find_call(mock_execute, "uv", "sync") is None

    def test_prepare_runs_uv_sync_first_time(self, tmp_path: Path, monkeypatch) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-content-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )

        executor._ensure_prepared()

        assert _find_call(mock_execute, "uv", "sync") is not None

    def test_prepare_runs_against_pyproject_when_no_lockfile(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """No uv.lock, but pyproject.toml exists — prepare phase still runs (fallback branch)."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text('[project]\nname = "x"\n')
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor._ensure_prepared()

        assert _find_call(mock_execute, "uv", "sync") is not None
        assert (mounts.cache_root.parent / ".prepared_hash").is_file()

    def test_prepare_failure_does_not_write_stamp_and_warns(
        self, tmp_path: Path, monkeypatch, caplog
    ) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-v1")

        def side_effect(cmd, **kwargs):
            if "sync" in cmd:
                return _ok_result(exit_code=1)
            return _ok_result()

        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(side_effect=side_effect))
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        with caplog.at_level("WARNING"):
            executor._ensure_prepared()

        assert not (mounts.cache_root.parent / ".prepared_hash").exists()
        assert any("uv sync" in rec.message for rec in caplog.records)

    def test_prepare_skipped_when_lockfile_hash_unchanged(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-content-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor._ensure_prepared()
        mock_execute.reset_mock()
        executor._ensure_prepared()

        assert _find_call(mock_execute, "uv", "sync") is None

    def test_prepare_reruns_on_lockfile_change(self, tmp_path: Path, monkeypatch) -> None:
        mounts = _mounts(tmp_path)
        lockfile = mounts.source_root / "uv.lock"
        lockfile.write_text("lockfile-content-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor._ensure_prepared()
        lockfile.write_text("lockfile-content-v2-changed")
        mock_execute.reset_mock()
        executor._ensure_prepared()

        assert _find_call(mock_execute, "uv", "sync") is not None

    def test_prepare_phase_has_network_execute_phase_does_not(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor.execute(["python", "-m", "pytest"])

        prepare_argv = _find_call(mock_execute, "uv", "sync")
        # Both prepare and execute phases now carry --name (Red/Blue fix — AD-8 cleanup
        # applies to both), so disambiguate the execute-phase call via --network too.
        run_argv = _find_call(mock_execute, "--name", "--network")
        assert prepare_argv is not None
        assert "--network" not in prepare_argv
        assert run_argv is not None
        assert "--network" in run_argv

    def test_prepare_phase_includes_same_security_hardening_as_execute_phase(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Red/Blue fix: uv sync can execute arbitrary sdist build code from PyPI, so the
        prepare phase gets the same cap-drop/resource/user hardening as the execute phase."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor._ensure_prepared()

        prepare_argv = _find_call(mock_execute, "uv", "sync")
        assert prepare_argv is not None
        assert "--cap-drop" in prepare_argv
        assert "ALL" in prepare_argv
        assert "--security-opt" in prepare_argv
        mem_idx = prepare_argv.index("--memory")
        assert prepare_argv[mem_idx + 1] == "2147483648"

    def test_prepare_phase_cleanup_before_and_after(self, tmp_path: Path, monkeypatch) -> None:
        """Red/Blue fix: --rm alone is the exact anti-pattern AD-8 exists to avoid — the
        prepare phase gets the same deterministic-name + pre/post idempotent cleanup."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-v1")
        mock_execute = MagicMock(return_value=_ok_result())
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor._ensure_prepared()

        prepare_argv = _find_call(mock_execute, "uv", "sync")
        assert prepare_argv is not None
        assert "--name" in prepare_argv
        name = prepare_argv[prepare_argv.index("--name") + 1]
        assert name.startswith("specweaver-prepare-")

        rm_calls = [
            call
            for call in mock_execute.call_args_list
            if call.args and "rm" in call.args[0] and "-f" in call.args[0] and name in call.args[0]
        ]
        assert len(rm_calls) == 2

    def test_prepare_phase_cleanup_runs_on_exception(self, tmp_path: Path, monkeypatch) -> None:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-v1")

        def side_effect(cmd, **kwargs):
            if "sync" in cmd:
                raise RuntimeError("uv sync crashed")
            return _ok_result()

        mock_execute = MagicMock(side_effect=side_effect)
        monkeypatch.setattr(SubprocessExecutor, "execute", mock_execute)
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        with pytest.raises(RuntimeError, match="uv sync crashed"):
            executor._ensure_prepared()

        rm_calls = [
            call
            for call in mock_execute.call_args_list
            if call.args and "rm" in call.args[0] and "-f" in call.args[0]
        ]
        assert len(rm_calls) == 2

    def test_stamp_file_lives_alongside_not_inside_cache_root(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Red/Blue correction: the stamp file must not live inside cache_root itself,
        since a real `uv sync` may reorganize/clear the directory it treats as its cache."""
        mounts = _mounts(tmp_path)
        (mounts.source_root / "uv.lock").write_text("lockfile-v1")
        monkeypatch.setattr(SubprocessExecutor, "execute", MagicMock(return_value=_ok_result()))
        monkeypatch.setattr(
            "specweaver.sandbox.execution.container_executor.shutil.which",
            lambda name: f"/usr/bin/{name}",
        )
        executor = ContainerSubprocessExecutor(cwd=tmp_path, mounts=mounts)

        executor._ensure_prepared()

        stamp = mounts.cache_root.parent / ".prepared_hash"
        assert stamp.is_file()
        assert not (mounts.cache_root / ".prepared_hash").exists()
