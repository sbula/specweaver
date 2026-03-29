# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.loom.tools.filesystem.interfaces — TDD.

Same exhaustive invisibility pattern as git interfaces:
- Each interface exposes ONLY the methods for its role
- Non-permitted methods are physically absent (not just blocked)
- Factory function builds the right interface for any role
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.loom.security import (
    AccessMode,
    FolderGrant,
)
from specweaver.loom.tools.filesystem.interfaces import (
    DrafterFileInterface,
    ImplementerFileInterface,
    ReviewerFileInterface,
    create_filesystem_interface,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a project with files to operate on."""
    (tmp_path / "src" / "domain" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "domain" / "billing" / "calc.py").write_text(
        "def total(a, b): return a + b",
        encoding="utf-8",
    )
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "billing.md").write_text("# Billing\n", encoding="utf-8")
    (tmp_path / "context.yaml").write_text("name: test\nlevel: system\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Factory grants for each role
# ---------------------------------------------------------------------------

_IMPLEMENTER_GRANTS = [
    FolderGrant("src/domain/billing", AccessMode.FULL, recursive=True),
]
_REVIEWER_GRANTS = [
    FolderGrant("src", AccessMode.READ, recursive=True),
    FolderGrant("specs", AccessMode.READ, recursive=True),
]
_DRAFTER_GRANTS = [
    FolderGrant("specs", AccessMode.FULL, recursive=True),
    FolderGrant("src", AccessMode.READ, recursive=True),
]


# ===========================================================================
# Method Visibility — Exhaustive Parametrized
# ===========================================================================


# All possible intent methods across all roles
_ALL_METHODS = {
    "read_file",
    "write_file",
    "edit_file",
    "create_file",
    "delete_file",
    "list_directory",
    "search_content",
    "find_placement",
    "grep",
    "find_files",
}

_IMPLEMENTER_METHODS = {
    "read_file",
    "write_file",
    "edit_file",
    "create_file",
    "delete_file",
    "list_directory",
    "search_content",
    "find_placement",
    "grep",
    "find_files",
}
_REVIEWER_METHODS = {"read_file", "list_directory", "search_content", "grep", "find_files"}
_DRAFTER_METHODS = {
    "read_file",
    "write_file",
    "create_file",
    "delete_file",
    "list_directory",
    "search_content",
    "find_placement",
    "grep",
    "find_files",
}


class TestImplementerMethodVisibility:
    """ImplementerFileInterface exposes all file methods."""

    @pytest.mark.parametrize("method", sorted(_IMPLEMENTER_METHODS))
    def test_has_method(self, method: str, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        assert hasattr(iface, method), f"Missing method: {method}"

    # Implementer has ALL methods, so this set is empty → pytest skips.
    # This is correct: there are no methods the implementer should NOT have.
    @pytest.mark.parametrize("method", sorted(_ALL_METHODS - _IMPLEMENTER_METHODS))
    def test_missing_method(self, method: str, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        assert not hasattr(iface, method), f"Should not have: {method}"


class TestReviewerMethodVisibility:
    """ReviewerFileInterface exposes only read/list/search."""

    @pytest.mark.parametrize("method", sorted(_REVIEWER_METHODS))
    def test_has_method(self, method: str, project: Path) -> None:
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        assert hasattr(iface, method), f"Missing method: {method}"

    @pytest.mark.parametrize("method", sorted(_ALL_METHODS - _REVIEWER_METHODS))
    def test_missing_method(self, method: str, project: Path) -> None:
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        assert not hasattr(iface, method), f"Should not have: {method}"


class TestDrafterMethodVisibility:
    """DrafterFileInterface exposes read/write/create/delete/list/search/find_placement."""

    @pytest.mark.parametrize("method", sorted(_DRAFTER_METHODS))
    def test_has_method(self, method: str, project: Path) -> None:
        iface = create_filesystem_interface("drafter", project, _DRAFTER_GRANTS)
        assert hasattr(iface, method), f"Missing method: {method}"

    @pytest.mark.parametrize("method", sorted(_ALL_METHODS - _DRAFTER_METHODS))
    def test_missing_method(self, method: str, project: Path) -> None:
        iface = create_filesystem_interface("drafter", project, _DRAFTER_GRANTS)
        assert not hasattr(iface, method), f"Should not have: {method}"


# ===========================================================================
# Functional — interfaces delegate to tool correctly
# ===========================================================================


class TestImplementerFunctional:
    """ImplementerFileInterface delegates correctly."""

    def test_read_file(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.read_file("src/domain/billing/calc.py")
        assert result.status == "success"
        assert "total" in result.data

    def test_write_file(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.write_file("src/domain/billing/calc.py", "# updated\n")
        assert result.status == "success"

    def test_create_file(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.create_file("src/domain/billing/new.py", "# new")
        assert result.status == "success"

    def test_delete_file(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.delete_file("src/domain/billing/calc.py")
        assert result.status == "success"

    def test_list_directory(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.list_directory("src/domain/billing")
        assert result.status == "success"

    def test_search_content(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.search_content("src/domain/billing", r"def")
        assert result.status == "success"

    def test_edit_file(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        result = iface.edit_file(
            "src/domain/billing/calc.py",
            old="return a + b",
            new="return a + b  # sum",
        )
        assert result.status == "success"


class TestReviewerFunctional:
    """ReviewerFileInterface delegates correctly."""

    def test_read_file(self, project: Path) -> None:
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        result = iface.read_file("src/domain/billing/calc.py")
        assert result.status == "success"

    def test_list_directory(self, project: Path) -> None:
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        result = iface.list_directory("src/domain/billing")
        assert result.status == "success"

    def test_search_content(self, project: Path) -> None:
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        result = iface.search_content("src/domain/billing", r"def")
        assert result.status == "success"


class TestDrafterFunctional:
    """DrafterFileInterface delegates correctly."""

    def test_read_source(self, project: Path) -> None:
        iface = create_filesystem_interface("drafter", project, _DRAFTER_GRANTS)
        result = iface.read_file("src/domain/billing/calc.py")
        assert result.status == "success"

    def test_write_spec(self, project: Path) -> None:
        iface = create_filesystem_interface("drafter", project, _DRAFTER_GRANTS)
        result = iface.write_file("specs/billing.md", "# Updated\n")
        assert result.status == "success"

    def test_cannot_write_source(self, project: Path) -> None:
        """Drafter has READ-only on src — boundary enforcement still works through interface."""
        iface = create_filesystem_interface("drafter", project, _DRAFTER_GRANTS)
        result = iface.write_file("src/domain/billing/calc.py", "hacked")
        assert result.status == "error"


# ===========================================================================
# Factory
# ===========================================================================


class TestFactory:
    """create_filesystem_interface builds correct types."""

    def test_implementer(self, project: Path) -> None:
        iface = create_filesystem_interface("implementer", project, _IMPLEMENTER_GRANTS)
        assert isinstance(iface, ImplementerFileInterface)

    def test_reviewer(self, project: Path) -> None:
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        assert isinstance(iface, ReviewerFileInterface)

    def test_drafter(self, project: Path) -> None:
        iface = create_filesystem_interface("drafter", project, _DRAFTER_GRANTS)
        assert isinstance(iface, DrafterFileInterface)

    def test_unknown_role_raises(self, project: Path) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            create_filesystem_interface("hacker", project, [])

    def test_return_type_is_union(self, project: Path) -> None:
        """Factory return type is the FileInterface union."""
        iface = create_filesystem_interface("reviewer", project, _REVIEWER_GRANTS)
        assert isinstance(
            iface, (ImplementerFileInterface, ReviewerFileInterface, DrafterFileInterface)
        )
