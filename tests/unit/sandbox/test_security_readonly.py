from pathlib import Path

import pytest

from specweaver.sandbox.security import (
    ReadOnlyWorkspaceBoundary,
    WorkspaceBoundary,
    WorkspaceBoundaryError,
)


class TestReadOnlyWorkspaceBoundary:
    def test_requires_api_paths(self):
        with pytest.raises(
            ValueError, match="ReadOnlyWorkspaceBoundary requires at least one api_path"
        ):
            ReadOnlyWorkspaceBoundary([])

    def test_is_read_only(self):
        boundary = ReadOnlyWorkspaceBoundary([Path("/var/api")])
        assert boundary.is_read_only is True

    def test_roots_is_empty(self):
        boundary = ReadOnlyWorkspaceBoundary([Path("/var/api")])
        assert boundary.roots == []

    def test_validate_path_within_api_path(self):
        parent = Path("/var/api").resolve()
        boundary = ReadOnlyWorkspaceBoundary([parent])
        child = parent / "file.txt"
        assert boundary.validate_path(child) == child

    def test_validate_path_outside_boundary(self):
        parent = Path("/var/api").resolve()
        boundary = ReadOnlyWorkspaceBoundary([parent])
        outside = Path("/var/outside").resolve()
        with pytest.raises(WorkspaceBoundaryError):
            boundary.validate_path(outside)

    def test_regular_boundary_still_rejects_empty_roots(self):
        with pytest.raises(ValueError, match="WorkspaceBoundary requires at least one root"):
            WorkspaceBoundary(roots=[])
