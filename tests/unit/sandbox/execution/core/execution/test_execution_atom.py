# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for BashActionAtom (C-EXEC-02 SF-1)."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import Atom, AtomStatus
from specweaver.sandbox.execution.core.atom import (
    _MAX_OUTPUT_BYTES,
    BashActionAtom,
    _truncate,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# T2: _truncate() helper
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_under_limit_passthrough(self) -> None:
        text = "hello world"
        assert _truncate(text) == text

    def test_exactly_at_limit_passthrough(self) -> None:
        text = "a" * _MAX_OUTPUT_BYTES
        result = _truncate(text)
        assert result == text
        assert "TRUNCATED" not in result

    def test_over_limit_truncated_with_marker(self) -> None:
        text = "a" * (_MAX_OUTPUT_BYTES + 100)
        result = _truncate(text)
        assert result.endswith("...[TRUNCATED]")
        assert len(result.encode("utf-8")) <= _MAX_OUTPUT_BYTES + len("...[TRUNCATED]")

    def test_multibyte_char_at_boundary_does_not_raise(self) -> None:
        # A multi-byte UTF-8 char (emoji, 4 bytes) placed so it straddles the
        # exact byte boundary — must not raise UnicodeDecodeError.
        text = ("a" * (_MAX_OUTPUT_BYTES - 2)) + "😀" * 50
        result = _truncate(text)  # must not raise
        assert result.endswith("...[TRUNCATED]")


# ---------------------------------------------------------------------------
# T3: Construction + cheap input validation
# ---------------------------------------------------------------------------


class TestConstructionAndCheapValidation:
    def test_atom_is_atom_subclass(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        assert isinstance(atom, Atom)

    def test_missing_script_key_fails(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "script" in result.message.lower()

    def test_script_name_with_slash_rejected(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "sub/dir.sh"})
        assert result.status == AtomStatus.FAILED
        assert "bare filename" in result.message.lower()

    def test_script_name_with_backslash_rejected(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "sub\\dir.sh"})
        assert result.status == AtomStatus.FAILED
        assert "bare filename" in result.message.lower()

    def test_script_name_with_traversal_rejected(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "../../etc/passwd"})
        assert result.status == AtomStatus.FAILED
        assert "bare filename" in result.message.lower()

    def test_timeout_over_ceiling_rejected(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "x.sh", "timeout_seconds": 7200})
        assert result.status == AtomStatus.FAILED
        assert "3600" in result.message

    def test_env_path_override_rejected_case_insensitive(self, tmp_path: Path) -> None:
        atom = BashActionAtom(cwd=tmp_path)
        for variant in ("PATH", "Path", "path"):
            result = atom.run({"script": "x.sh", "env": {variant: "/evil"}})
            assert result.status == AtomStatus.FAILED
            assert "path" in result.message.lower()


# ---------------------------------------------------------------------------
# T4: Containment + existence
# ---------------------------------------------------------------------------


class TestContainmentAndExistence:
    def test_missing_script_file_fails(self, tmp_path: Path) -> None:
        (tmp_path / ".specweaver" / "scripts").mkdir(parents=True)
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "does_not_exist.sh"})
        assert result.status == AtomStatus.FAILED
        assert "not found" in result.message.lower()

    def test_script_outside_scripts_dir_via_symlink_rejected(self, tmp_path: Path) -> None:
        import os

        scripts_dir = tmp_path / ".specweaver" / "scripts"
        scripts_dir.mkdir(parents=True)
        outside_target = tmp_path.parent / "evil.sh"
        outside_target.write_text("echo escaped\n", encoding="utf-8")
        link_path = scripts_dir / "link.sh"
        try:
            os.symlink(str(outside_target), str(link_path))
        except OSError:
            pytest.skip("Cannot create symlinks (requires admin on Windows)")

        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "link.sh"})
        assert result.status == AtomStatus.FAILED
        assert "outside" in result.message.lower() or "boundary" in result.message.lower()

    def test_workspace_boundary_error_handled_without_symlink(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Platform-independent coverage of the WorkspaceBoundaryError except-branch
        itself, decoupled from *how* an escape is detected (symlinks need admin on
        Windows) — directly forces validate_path to raise."""
        from specweaver.sandbox.execution.core import atom as atom_module
        from specweaver.sandbox.security import WorkspaceBoundaryError

        scripts_dir = tmp_path / ".specweaver" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "x.sh").write_text("echo hi\n", encoding="utf-8")

        def _boom(self: object, requested: object) -> object:
            raise WorkspaceBoundaryError(f"Path '{requested}' is outside workspace boundaries")

        monkeypatch.setattr(atom_module.WorkspaceBoundary, "validate_path", _boom)
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "x.sh"})

        assert result.status == AtomStatus.FAILED
        assert "outside workspace boundaries" in result.message


# ---------------------------------------------------------------------------
# T5: bash availability check
# ---------------------------------------------------------------------------


class TestBashAvailability:
    def test_bash_not_on_path_fails_cleanly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "x.sh").write_text("echo hi\n", encoding="utf-8")

        monkeypatch.setattr(
            "specweaver.sandbox.execution.core.atom.shutil.which", lambda _name: None,
        )
        atom = BashActionAtom(cwd=tmp_path)
        result = atom.run({"script": "x.sh"})
        assert result.status == AtomStatus.FAILED
        assert "bash" in result.message.lower()
        assert "not found" in result.message.lower()


# ---------------------------------------------------------------------------
# T6: Happy-path execution
# ---------------------------------------------------------------------------

_BASH_UNAVAILABLE = shutil.which("bash") is None


def _write_script(scripts_dir: Path, name: str, body: str) -> None:
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / name).write_text(body, encoding="utf-8", newline="\n")


@pytest.mark.skipif(_BASH_UNAVAILABLE, reason="bash not on PATH")
class TestHappyPathExecution:
    def test_successful_script_execution_default_args(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "hello.sh", "#!/usr/bin/env bash\necho hello\nexit 0\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "hello.sh"})

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["exit_code"] == 0
        assert "hello" in result.exports["stdout"]
        assert isinstance(result.exports["duration_seconds"], float)

    def test_nonzero_exit_maps_to_failed(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "fail.sh", "#!/usr/bin/env bash\nexit 3\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "fail.sh"})

        assert result.status == AtomStatus.FAILED
        assert result.exports["exit_code"] == 3

    def test_args_passed_through(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "echo_arg.sh", "#!/usr/bin/env bash\necho \"$1\"\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "echo_arg.sh", "args": ["hello-arg"]})

        assert "hello-arg" in result.exports["stdout"]

    def test_working_dir_resolved_relative_to_project(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        _write_script(scripts_dir, "pwd.sh", "#!/usr/bin/env bash\npwd\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "pwd.sh", "working_dir": "subdir"})

        assert result.status == AtomStatus.SUCCESS
        assert "subdir" in result.exports["stdout"]

    def test_working_dir_nonexistent_rejected(self, tmp_path: Path) -> None:
        """working_dir points to a path that doesn't exist at all —
        SubprocessExecutor._validate_cwd's existence check fires first,
        raising FileNotFoundError."""
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "noop.sh", "#!/usr/bin/env bash\nexit 0\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "noop.sh", "working_dir": "../../outside"})

        assert result.status == AtomStatus.FAILED

    def test_working_dir_escaping_project_rejected(self, tmp_path: Path) -> None:
        """working_dir resolves to a REAL, existing directory outside project_path —
        distinctly exercises SubprocessExecutor._validate_cwd's boundary check
        (ValueError), not the existence check (FileNotFoundError)."""
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "noop.sh", "#!/usr/bin/env bash\nexit 0\n")
        # tmp_path.parent always exists (pytest's own base tmp dir) and is
        # outside the project_path (== tmp_path) boundary.
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "noop.sh", "working_dir": ".."})

        assert result.status == AtomStatus.FAILED
        assert "traversal" in result.message.lower() or "boundary" in result.message.lower()

    def test_resource_limits_applied_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from specweaver.sandbox.execution.core import atom as atom_module

        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "noop.sh", "#!/usr/bin/env bash\nexit 0\n")

        captured: dict[str, object] = {}
        real_executor_cls = atom_module.SubprocessExecutor

        def _spy(*args: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return real_executor_cls(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(atom_module, "SubprocessExecutor", _spy)
        atom = BashActionAtom(cwd=tmp_path)

        atom.run({"script": "noop.sh"})

        limits = captured["resource_limits"]
        assert limits.max_memory_bytes == 2_147_483_648
        assert limits.max_processes == 128


# ---------------------------------------------------------------------------
# T7: Output truncation + env passthrough integration
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_BASH_UNAVAILABLE, reason="bash not on PATH")
class TestTruncationAndEnvIntegration:
    def test_stdout_truncated_over_1mib(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        # printf a string well over 1 MiB without a giant literal in the script file
        _write_script(
            scripts_dir,
            "big_output.sh",
            "#!/usr/bin/env bash\nprintf 'a%.0s' {1..1200000}\n",
        )
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "big_output.sh"})

        assert result.exports["stdout"].endswith("...[TRUNCATED]")
        assert len(result.exports["stdout"].encode("utf-8")) <= _MAX_OUTPUT_BYTES + len(
            "...[TRUNCATED]"
        )

    def test_env_map_passed_through(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "echo_env.sh", "#!/usr/bin/env bash\necho \"$MY_VAR\"\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "echo_env.sh", "env": {"MY_VAR": "custom-value"}})

        assert "custom-value" in result.exports["stdout"]

    def test_env_does_not_leak_run_context_vars(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(
            scripts_dir, "echo_secret.sh", "#!/usr/bin/env bash\necho \"[$SECRET_VAR]\"\n",
        )
        atom = BashActionAtom(cwd=tmp_path)

        # No 'env' key passed — SECRET_VAR must NOT leak in from this test
        # process's own os.environ even if it were set there.
        result = atom.run({"script": "echo_secret.sh"})

        assert "[]" in result.exports["stdout"]


# ---------------------------------------------------------------------------
# T8: Timeout override + exception containment
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_BASH_UNAVAILABLE, reason="bash not on PATH")
class TestTimeoutAndExceptionContainment:
    def test_timeout_override_applied(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "sleep.sh", "#!/usr/bin/env bash\nsleep 5\necho done\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "sleep.sh", "timeout_seconds": 1})

        assert result.status == AtomStatus.FAILED
        assert "done" not in result.exports["stdout"]

    def test_crashing_executor_never_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from specweaver.sandbox.execution.core import atom as atom_module

        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "noop.sh", "#!/usr/bin/env bash\nexit 0\n")

        def _boom(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("boom")

        monkeypatch.setattr(atom_module.SubprocessExecutor, "execute", _boom)
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "noop.sh"})  # must not raise

        assert result.status == AtomStatus.FAILED
        assert "boom" in result.message


# ---------------------------------------------------------------------------
# Hostile args (NFR-2: no shell interpolation) — Phase 2 gap analysis stories 3-4
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_BASH_UNAVAILABLE, reason="bash not on PATH")
class TestHostileArgs:
    def test_shell_metacharacter_arg_treated_as_literal(self, tmp_path: Path) -> None:
        """A hostile arg containing shell metacharacters must reach the script
        as a single, inert, literal string — never interpreted/executed as a
        nested shell command. Proves NFR-2 (fixed argv, no shell=True)."""
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "echo_arg.sh", "#!/usr/bin/env bash\necho \"got: $1\"\n")
        atom = BashActionAtom(cwd=tmp_path)

        hostile_arg = "; echo pwned; $(whoami)"
        result = atom.run({"script": "echo_arg.sh", "args": [hostile_arg]})

        assert result.status == AtomStatus.SUCCESS
        assert f"got: {hostile_arg}" in result.exports["stdout"]
        assert "pwned" not in result.exports["stdout"].replace(f"got: {hostile_arg}", "")

    def test_non_string_arg_does_not_propagate_raw_exception(self, tmp_path: Path) -> None:
        """A non-string args entry raises TypeError deep inside Popen's argv
        construction — must be caught by the generic exception handler and
        returned as a FAILED AtomResult, not propagate as a raw exception."""
        scripts_dir = tmp_path / ".specweaver" / "scripts"
        _write_script(scripts_dir, "noop.sh", "#!/usr/bin/env bash\nexit 0\n")
        atom = BashActionAtom(cwd=tmp_path)

        result = atom.run({"script": "noop.sh", "args": [123]})  # must not raise

        assert result.status == AtomStatus.FAILED
