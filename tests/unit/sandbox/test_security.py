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
        from specweaver.core.flow.handlers.base import RunContext

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "specs" / "feature_spec.md",
        )
        boundary = WorkspaceBoundary.from_run_context(ctx)
        assert boundary.roots == [tmp_path]

    def test_component_level_uses_workspace_roots(self, tmp_path: Path) -> None:
        from specweaver.core.flow.handlers.base import RunContext

        svc_root = tmp_path / "services" / "auth"
        svc_root.mkdir(parents=True)
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=svc_root / "specs" / "login_spec.md",
            workspace_roots=[str(svc_root)],
        )
        boundary = WorkspaceBoundary.from_run_context(ctx)
        assert boundary.roots == [svc_root]

    def test_component_level_with_api_paths(self, tmp_path: Path) -> None:
        from specweaver.core.flow.handlers.base import RunContext

        svc_root = tmp_path / "services" / "auth"
        api_path = tmp_path / "services" / "payments" / "api"
        svc_root.mkdir(parents=True)
        api_path.mkdir(parents=True)
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=svc_root / "specs" / "login_spec.md",
            workspace_roots=[str(svc_root)],
            api_contract_paths=[str(api_path)],
        )
        boundary = WorkspaceBoundary.from_run_context(ctx)
        assert boundary.roots == [svc_root]
        assert boundary.api_paths == [api_path]
