# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for WorkspaceBoundary — dynamic path enforcement for research tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.security import WorkspaceBoundary, WorkspaceBoundaryError

if TYPE_CHECKING:
    from pathlib import Path


class TestWorkspaceBoundaryInit:
    """Tests for boundary construction."""

    def test_single_root(self, tmp_path: Path) -> None:
        boundary = WorkspaceBoundary(roots=[tmp_path])
        assert boundary.roots == [tmp_path]
        assert boundary.api_paths == []

    def test_multiple_roots(self, tmp_path: Path) -> None:
        root_a = tmp_path / "service_a"
        root_b = tmp_path / "service_b"
        root_a.mkdir()
        root_b.mkdir()
        boundary = WorkspaceBoundary(roots=[root_a, root_b])
        assert len(boundary.roots) == 2

    def test_with_api_paths(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "other_service" / "api"
        api_dir.mkdir(parents=True)
        boundary = WorkspaceBoundary(roots=[tmp_path], api_paths=[api_dir])
        assert len(boundary.api_paths) == 1

    def test_empty_roots_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one root"):
            WorkspaceBoundary(roots=[])


class TestValidatePath:
    """Tests for path validation and boundary enforcement."""

    def test_path_within_root(self, tmp_path: Path) -> None:
        sub = tmp_path / "src" / "main.py"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.touch()
        boundary = WorkspaceBoundary(roots=[tmp_path])
        result = boundary.validate_path(sub)
        assert result == sub.resolve()

    def test_path_is_root(self, tmp_path: Path) -> None:
        boundary = WorkspaceBoundary(roots=[tmp_path])
        result = boundary.validate_path(tmp_path)
        assert result == tmp_path.resolve()

    def test_path_outside_root_raises(self, tmp_path: Path) -> None:
        boundary = WorkspaceBoundary(roots=[tmp_path / "project"])
        with pytest.raises(WorkspaceBoundaryError, match="outside workspace"):
            boundary.validate_path(tmp_path / "other" / "file.py")

    def test_traversal_attack_blocked(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        boundary = WorkspaceBoundary(roots=[project])
        with pytest.raises(WorkspaceBoundaryError, match="outside workspace"):
            boundary.validate_path(project / ".." / "secrets.txt")

    def test_path_in_api_paths_allowed(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "other_service" / "api"
        api_dir.mkdir(parents=True)
        api_file = api_dir / "openapi.yaml"
        api_file.touch()
        boundary = WorkspaceBoundary(
            roots=[tmp_path / "my_service"],
            api_paths=[api_dir],
        )
        (tmp_path / "my_service").mkdir(exist_ok=True)
        result = boundary.validate_path(api_file)
        assert result == api_file.resolve()

    def test_path_in_multiple_roots(self, tmp_path: Path) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        file_b = root_b / "code.py"
        file_b.touch()
        boundary = WorkspaceBoundary(roots=[root_a, root_b])
        result = boundary.validate_path(file_b)
        assert result == file_b.resolve()


class TestResolveRelative:
    """Tests for resolving relative paths."""

    def test_relative_to_primary_root(self, tmp_path: Path) -> None:
        boundary = WorkspaceBoundary(roots=[tmp_path])
        result = boundary.resolve_relative("src/main.py")
        assert result == (tmp_path / "src" / "main.py").resolve()

    def test_dot_resolves_to_root(self, tmp_path: Path) -> None:
        boundary = WorkspaceBoundary(roots=[tmp_path])
        result = boundary.resolve_relative(".")
        assert result == tmp_path.resolve()

    def test_traversal_in_relative_blocked(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        boundary = WorkspaceBoundary(roots=[project])
        with pytest.raises(WorkspaceBoundaryError, match="outside workspace"):
            boundary.resolve_relative("../../etc/passwd")


class TestFromRunContext:
    """Tests for boundary construction from RunContext."""

    def test_feature_level_uses_project_path(self, tmp_path: Path) -> None:
        from specweaver.core.flow.handlers.run_context import RunContext

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "specs" / "feature_spec.md",
        )
        boundary = WorkspaceBoundary.from_run_context(ctx)
        assert boundary.roots == [tmp_path]

    def test_component_level_uses_workspace_roots(self, tmp_path: Path) -> None:
        from specweaver.core.flow.handlers.run_context import GraphContext, RunContext

        svc_root = tmp_path / "services" / "auth"
        svc_root.mkdir(parents=True)
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=svc_root / "specs" / "login_spec.md",
            graph=GraphContext(workspace_roots=[str(svc_root)]),
        )
        boundary = WorkspaceBoundary.from_run_context(ctx)
        assert boundary.roots == [svc_root]

    def test_component_level_with_api_paths(self, tmp_path: Path) -> None:
        from specweaver.core.flow.handlers.run_context import GraphContext, RunContext

        svc_root = tmp_path / "services" / "auth"
        api_path = tmp_path / "services" / "payments" / "api"
        svc_root.mkdir(parents=True)
        api_path.mkdir(parents=True)
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=svc_root / "specs" / "login_spec.md",
            graph=GraphContext(workspace_roots=[str(svc_root)], api_contract_paths=[str(api_path)]),
        )
        boundary = WorkspaceBoundary.from_run_context(ctx)
        assert boundary.roots == [svc_root]
        assert boundary.api_paths == [api_path]


class TestFolderGrantPathValidation:
    """An empty grant path is rejected at construction (user decision, 2026-08-12)."""

    def test_an_empty_path_is_rejected(self) -> None:
        """An empty path granted the whole project on POSIX and nothing on Windows.

        The matcher compares path segments, and `_resolve_access` builds an absolute path first. On
        POSIX `/tmp/proj/x` splits to `['', 'tmp', ...]`, whose leading `''` matches an empty
        grant's `['']`; on Windows `C:/proj/x` splits to `['C:', ...]` and never matches. Measured:
        with one such grant, reads of `secrets/prod.env` and `.git/config` both succeeded though
        granted nowhere.

        Rejected at construction rather than treated as matching nothing, so the mistake is loud.
        A grant naming no directory is a bug or an unset config, and failing closed is the default
        a security primitive should take. The whole project is expressible already — pass the
        project root's absolute path.
        """
        import pytest

        from specweaver.sandbox.security import AccessMode, FolderGrant

        with pytest.raises(ValueError, match="empty"):
            FolderGrant("", AccessMode.READ, recursive=True)

    def test_a_whitespace_only_path_is_rejected(self) -> None:
        """Boundary: `" "` names no directory either, and would slip past an `if not path` check."""
        import pytest

        from specweaver.sandbox.security import AccessMode, FolderGrant

        with pytest.raises(ValueError, match="empty"):
            FolderGrant("   ", AccessMode.READ, recursive=True)

    def test_the_models_copy_rejects_it_too(self) -> None:
        """`FolderGrant` is defined twice — in `sandbox.security` and in `filesystem.interfaces`.

        Both are imported by real callers, so guarding only one leaves the hole open through the
        other. The duplication itself is worth removing, but not under a security fix.
        """
        import pytest

        from specweaver.sandbox.filesystem.interfaces.models import AccessMode, FolderGrant

        with pytest.raises(ValueError, match="empty"):
            FolderGrant("", AccessMode.READ, recursive=True)

    def test_an_ordinary_relative_path_is_accepted(self) -> None:
        """Control: the guard rejects the empty case, not every grant."""
        from specweaver.sandbox.security import AccessMode, FolderGrant

        grant = FolderGrant("src/domain/billing", AccessMode.READ, recursive=True)

        assert grant.path == "src/domain/billing"


class TestFolderGrantHasOneDefinition:
    """`TECH-037`. `AccessMode`, `FolderGrant` and the `MODE_ALLOWS_*` sets were declared twice.

    Not merely repetition. They were two distinct classes: `isinstance` across them returned
    False, and `AccessMode.READ == AccessMode.READ` held only because `StrEnum` compares by value.
    Production imported the `sandbox.security` copy while several tests built grants from the
    `filesystem.interfaces.models` copy and handed them to it — which worked by duck typing alone.

    The security consequence was the one `test_an_empty_path_is_rejected` records: a guard added to
    one copy leaves the hole open through the other. `models` now re-exports rather than redefines,
    so there is one class and one guard.
    """

    def test_folder_grant_is_one_class(self) -> None:
        from specweaver.sandbox.filesystem.interfaces.models import FolderGrant as FromModels
        from specweaver.sandbox.security import FolderGrant as FromSecurity

        assert FromModels is FromSecurity

    def test_access_mode_is_one_enum(self) -> None:
        from specweaver.sandbox.filesystem.interfaces.models import AccessMode as FromModels
        from specweaver.sandbox.security import AccessMode as FromSecurity

        assert FromModels is FromSecurity

    def test_the_mode_sets_are_one_object(self) -> None:
        from specweaver.sandbox import security
        from specweaver.sandbox.filesystem.interfaces import models

        for name in (
            "MODE_ALLOWS_READ",
            "MODE_ALLOWS_WRITE",
            "MODE_ALLOWS_CREATE",
            "MODE_ALLOWS_DELETE",
        ):
            assert getattr(models, name) is getattr(security, name), name

    def test_a_grant_built_from_either_module_is_accepted_by_the_other(self) -> None:
        """The duck-typing the old arrangement relied on is now real type identity."""
        from specweaver.sandbox.filesystem.interfaces.models import AccessMode, FolderGrant
        from specweaver.sandbox.security import FolderGrant as FromSecurity

        assert isinstance(FolderGrant("src", AccessMode.READ, recursive=True), FromSecurity)
