# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.loom.tools.filesystem.tool — TDD (tests first).

Test structure:
- FolderGrant / AccessMode models
- Role-intent mapping (implementer, reviewer, drafter)
- Intent dispatch (all intents)
- Boundary enforcement (grants, protected patterns, no grant = blocked)
- Role gating (non-whitelisted intents raise)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.loom.commons.filesystem.executor import FileExecutor
from specweaver.loom.tools.filesystem.tool import (
    ROLE_INTENTS,
    AccessMode,
    FileSystemTool,
    FileSystemToolError,
    FolderGrant,
    ToolResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a project with subdirectories and files."""
    # Source tree
    (tmp_path / "src" / "domain" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "domain" / "billing" / "calc.py").write_text(
        "def total(a, b): return a + b", encoding="utf-8",
    )
    (tmp_path / "src" / "domain" / "billing" / "context.yaml").write_text(
        "name: billing\nlevel: module\npurpose: Billing logic\narchetype: pure-logic\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "shared" / "currency").mkdir(parents=True)
    (tmp_path / "src" / "shared" / "currency" / "rates.py").write_text(
        "EUR = 1.0\nUSD = 1.1", encoding="utf-8",
    )
    # Specs
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "billing_spec.md").write_text("# Billing Spec\n", encoding="utf-8")
    # Tests
    (tmp_path / "tests" / "unit" / "billing").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "billing" / "test_calc.py").write_text(
        "def test_total(): assert True", encoding="utf-8",
    )
    # Root context
    (tmp_path / "context.yaml").write_text(
        "name: test-project\nlevel: system\n", encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def executor(project: Path) -> FileExecutor:
    return FileExecutor(cwd=project)


@pytest.fixture
def implementer_grants() -> list[FolderGrant]:
    """Grants for an implementer working on billing."""
    return [
        FolderGrant(path="src/domain/billing", mode=AccessMode.FULL, recursive=True),
        FolderGrant(path="tests/unit/billing", mode=AccessMode.FULL, recursive=True),
        FolderGrant(path="src/shared/currency", mode=AccessMode.READ, recursive=True),
    ]


@pytest.fixture
def implementer(executor: FileExecutor, implementer_grants: list[FolderGrant]) -> FileSystemTool:
    return FileSystemTool(executor=executor, role="implementer", grants=implementer_grants)


@pytest.fixture
def reviewer(executor: FileExecutor) -> FileSystemTool:
    """Reviewer with read-only access to source and specs."""
    grants = [
        FolderGrant(path="src", mode=AccessMode.READ, recursive=True),
        FolderGrant(path="specs", mode=AccessMode.READ, recursive=True),
        FolderGrant(path="tests", mode=AccessMode.READ, recursive=True),
    ]
    return FileSystemTool(executor=executor, role="reviewer", grants=grants)


@pytest.fixture
def drafter(executor: FileExecutor) -> FileSystemTool:
    """Drafter with full access to specs, read to source."""
    grants = [
        FolderGrant(path="specs", mode=AccessMode.FULL, recursive=True),
        FolderGrant(path="src", mode=AccessMode.READ, recursive=True),
    ]
    return FileSystemTool(executor=executor, role="drafter", grants=grants)


# ===========================================================================
# FolderGrant / AccessMode Model Tests
# ===========================================================================


class TestModels:
    """Basic model behavior."""

    def test_access_mode_values(self) -> None:
        assert AccessMode.READ == "read"
        assert AccessMode.WRITE == "write"
        assert AccessMode.FULL == "full"

    def test_folder_grant_creation(self) -> None:
        grant = FolderGrant(path="src", mode=AccessMode.FULL, recursive=True)
        assert grant.path == "src"
        assert grant.mode == AccessMode.FULL
        assert grant.recursive is True

    def test_folder_grant_immutable(self) -> None:
        grant = FolderGrant(path="src", mode=AccessMode.FULL, recursive=True)
        with pytest.raises(AttributeError):
            grant.path = "hacked"  # type: ignore[misc]


# ===========================================================================
# Role-Intent Mapping
# ===========================================================================


class TestRoleIntentMapping:
    """Verify role → intent whitelist is correct."""

    def test_implementer_intents(self) -> None:
        expected = {
            "read_file", "write_file", "edit_file", "create_file",
            "delete_file", "list_directory", "search_content", "find_placement",
        }
        assert ROLE_INTENTS["implementer"] == frozenset(expected)

    def test_reviewer_intents(self) -> None:
        expected = {"read_file", "list_directory", "search_content"}
        assert ROLE_INTENTS["reviewer"] == frozenset(expected)

    def test_drafter_intents(self) -> None:
        expected = {
            "read_file", "write_file", "create_file", "delete_file",
            "list_directory", "search_content", "find_placement",
        }
        assert ROLE_INTENTS["drafter"] == frozenset(expected)

    def test_unknown_role_raises(self, executor: FileExecutor) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            FileSystemTool(executor=executor, role="hacker", grants=[])


# ===========================================================================
# Constructor
# ===========================================================================


class TestConstructor:
    """FileSystemTool constructor behavior."""

    def test_role_property(self, implementer: FileSystemTool) -> None:
        assert implementer.role == "implementer"

    def test_allowed_intents(self, implementer: FileSystemTool) -> None:
        assert "read_file" in implementer.allowed_intents
        assert "write_file" in implementer.allowed_intents

    def test_reviewer_cannot_write(self, reviewer: FileSystemTool) -> None:
        assert "write_file" not in reviewer.allowed_intents
        assert "delete_file" not in reviewer.allowed_intents


# ===========================================================================
# Intent Dispatch — Implementer (FULL access within boundary)
# ===========================================================================


class TestImplementerIntents:
    """Implementer can read/write/create/delete within granted boundaries."""

    def test_read_file_in_boundary(self, implementer: FileSystemTool) -> None:
        result = implementer.read_file("src/domain/billing/calc.py")
        assert result.status == "success"
        assert "total" in result.data

    def test_write_file_in_boundary(self, implementer: FileSystemTool, project: Path) -> None:
        result = implementer.write_file("src/domain/billing/calc.py", "# updated\n")
        assert result.status == "success"
        assert (project / "src/domain/billing/calc.py").read_text() == "# updated\n"

    def test_create_file_in_boundary(self, implementer: FileSystemTool, project: Path) -> None:
        result = implementer.create_file("src/domain/billing/invoice.py", "class Invoice: pass")
        assert result.status == "success"
        assert (project / "src/domain/billing/invoice.py").is_file()

    def test_create_file_already_exists(self, implementer: FileSystemTool) -> None:
        """create_file fails if file already exists (use write_file to overwrite)."""
        result = implementer.create_file("src/domain/billing/calc.py", "overwrite")
        assert result.status == "error"

    def test_delete_file_in_boundary(self, implementer: FileSystemTool, project: Path) -> None:
        result = implementer.delete_file("src/domain/billing/calc.py")
        assert result.status == "success"
        assert not (project / "src/domain/billing/calc.py").exists()

    def test_list_directory_in_boundary(self, implementer: FileSystemTool) -> None:
        result = implementer.list_directory("src/domain/billing")
        assert result.status == "success"
        assert "calc.py" in result.data

    def test_search_content_in_boundary(self, implementer: FileSystemTool) -> None:
        result = implementer.search_content("src/domain/billing", r"def \w+")
        assert result.status == "success"
        assert len(result.data) > 0

    def test_edit_file_in_boundary(self, implementer: FileSystemTool, project: Path) -> None:
        result = implementer.edit_file(
            "src/domain/billing/calc.py",
            old="return a + b",
            new="return a + b  # sum",
        )
        assert result.status == "success"
        content = (project / "src/domain/billing/calc.py").read_text()
        assert "# sum" in content

    def test_edit_file_old_not_found(self, implementer: FileSystemTool) -> None:
        """edit_file returns error if old content not found."""
        result = implementer.edit_file(
            "src/domain/billing/calc.py",
            old="nonexistent string",
            new="replacement",
        )
        assert result.status == "error"

    def test_write_file_in_test_boundary(self, implementer: FileSystemTool, project: Path) -> None:
        """Implementer can also write to test directory."""
        result = implementer.create_file(
            "tests/unit/billing/test_invoice.py", "def test_it(): pass",
        )
        assert result.status == "success"
        assert (project / "tests/unit/billing/test_invoice.py").is_file()


# ===========================================================================
# Boundary Enforcement — READ-only grants
# ===========================================================================


class TestReadOnlyGrants:
    """READ grants allow only reading, not mutation."""

    def test_implementer_can_read_shared(self, implementer: FileSystemTool) -> None:
        """Implementer has READ grant on shared/currency."""
        result = implementer.read_file("src/shared/currency/rates.py")
        assert result.status == "success"

    def test_implementer_cannot_write_shared(self, implementer: FileSystemTool) -> None:
        """Implementer has READ-only grant on shared/currency — write blocked."""
        result = implementer.write_file("src/shared/currency/rates.py", "hacked")
        assert result.status == "error"

    def test_implementer_cannot_create_in_shared(self, implementer: FileSystemTool) -> None:
        """Cannot create files in read-only boundary."""
        result = implementer.create_file("src/shared/currency/hack.py", "bad")
        assert result.status == "error"

    def test_implementer_cannot_delete_in_shared(self, implementer: FileSystemTool) -> None:
        """Cannot delete files in read-only boundary."""
        result = implementer.delete_file("src/shared/currency/rates.py")
        assert result.status == "error"


# ===========================================================================
# Boundary Enforcement — No Grant = Blocked
# ===========================================================================


class TestNoGrantBlocked:
    """Paths not covered by any grant are blocked entirely."""

    def test_read_outside_grants(self, implementer: FileSystemTool) -> None:
        """Cannot read files outside any grant."""
        result = implementer.read_file("specs/billing_spec.md")
        assert result.status == "error"

    def test_write_outside_grants(self, implementer: FileSystemTool) -> None:
        """Cannot write to files outside any grant."""
        result = implementer.write_file("specs/billing_spec.md", "hacked")
        assert result.status == "error"

    def test_list_outside_grants(self, implementer: FileSystemTool) -> None:
        """Cannot list directories outside any grant."""
        result = implementer.list_directory("specs")
        assert result.status == "error"

    def test_search_outside_grants(self, implementer: FileSystemTool) -> None:
        """Cannot search in directories outside any grant."""
        result = implementer.search_content("specs", r".*")
        assert result.status == "error"


# ===========================================================================
# Boundary Enforcement — Recursive vs Exclusive
# ===========================================================================


class TestRecursiveVsExclusive:
    """Recursive flag controls subdirectory access."""

    def test_recursive_grant_allows_subdirs(self, executor: FileExecutor, project: Path) -> None:
        """Recursive grant includes all subdirectories."""
        (project / "src" / "domain" / "billing" / "sub").mkdir()
        (project / "src" / "domain" / "billing" / "sub" / "deep.py").write_text("x=1")
        grants = [FolderGrant("src/domain/billing", AccessMode.FULL, recursive=True)]
        tool = FileSystemTool(executor=executor, role="implementer", grants=grants)
        result = tool.read_file("src/domain/billing/sub/deep.py")
        assert result.status == "success"

    def test_exclusive_grant_blocks_subdirs(self, executor: FileExecutor, project: Path) -> None:
        """Non-recursive grant only allows the exact directory."""
        (project / "src" / "domain" / "billing" / "sub").mkdir()
        (project / "src" / "domain" / "billing" / "sub" / "deep.py").write_text("x=1")
        grants = [FolderGrant("src/domain/billing", AccessMode.FULL, recursive=False)]
        tool = FileSystemTool(executor=executor, role="implementer", grants=grants)
        result = tool.read_file("src/domain/billing/sub/deep.py")
        assert result.status == "error"

    def test_exclusive_grant_allows_direct_children(self, executor: FileExecutor) -> None:
        """Non-recursive grant allows direct children of the directory."""
        grants = [FolderGrant("src/domain/billing", AccessMode.FULL, recursive=False)]
        tool = FileSystemTool(executor=executor, role="implementer", grants=grants)
        result = tool.read_file("src/domain/billing/calc.py")
        assert result.status == "success"


# ===========================================================================
# Protected Patterns (still enforced at tool level)
# ===========================================================================


class TestToolProtectedPatterns:
    """context.yaml is protected even with FULL grants."""

    def test_write_context_yaml_blocked(self, implementer: FileSystemTool) -> None:
        """Cannot write context.yaml even with FULL grant on the directory."""
        result = implementer.write_file("src/domain/billing/context.yaml", "hacked: true")
        assert result.status == "error"

    def test_delete_context_yaml_blocked(self, implementer: FileSystemTool) -> None:
        """Cannot delete context.yaml even with FULL grant."""
        result = implementer.delete_file("src/domain/billing/context.yaml")
        assert result.status == "error"

    def test_read_context_yaml_allowed(self, implementer: FileSystemTool) -> None:
        """Can read context.yaml (protection is write-only)."""
        result = implementer.read_file("src/domain/billing/context.yaml")
        assert result.status == "success"


# ===========================================================================
# Role Gating — non-whitelisted intents raise
# ===========================================================================


class TestRoleGating:
    """Non-whitelisted intents for a role should raise FileSystemToolError."""

    def test_reviewer_cannot_write(self, reviewer: FileSystemTool) -> None:
        """Reviewer role does not have write_file intent."""
        with pytest.raises(FileSystemToolError, match="not allowed"):
            reviewer.write_file("src/domain/billing/calc.py", "hacked")

    def test_reviewer_cannot_create(self, reviewer: FileSystemTool) -> None:
        with pytest.raises(FileSystemToolError, match="not allowed"):
            reviewer.create_file("src/new.py", "bad")

    def test_reviewer_cannot_delete(self, reviewer: FileSystemTool) -> None:
        with pytest.raises(FileSystemToolError, match="not allowed"):
            reviewer.delete_file("src/domain/billing/calc.py")

    def test_reviewer_cannot_edit(self, reviewer: FileSystemTool) -> None:
        with pytest.raises(FileSystemToolError, match="not allowed"):
            reviewer.edit_file("src/domain/billing/calc.py", old="x", new="y")

    def test_reviewer_can_read(self, reviewer: FileSystemTool) -> None:
        result = reviewer.read_file("src/domain/billing/calc.py")
        assert result.status == "success"

    def test_reviewer_can_list(self, reviewer: FileSystemTool) -> None:
        result = reviewer.list_directory("src/domain/billing")
        assert result.status == "success"

    def test_reviewer_can_search(self, reviewer: FileSystemTool) -> None:
        result = reviewer.search_content("src/domain/billing", r"def")
        assert result.status == "success"


# ===========================================================================
# Drafter Role
# ===========================================================================


class TestDrafterRole:
    """Drafter can manage specs and read source."""

    def test_drafter_can_read_specs(self, drafter: FileSystemTool) -> None:
        result = drafter.read_file("specs/billing_spec.md")
        assert result.status == "success"

    def test_drafter_can_write_specs(self, drafter: FileSystemTool, project: Path) -> None:
        result = drafter.write_file("specs/billing_spec.md", "# Updated\n")
        assert result.status == "success"
        assert "Updated" in (project / "specs/billing_spec.md").read_text()

    def test_drafter_can_create_specs(self, drafter: FileSystemTool, project: Path) -> None:
        result = drafter.create_file("specs/new_spec.md", "# New\n")
        assert result.status == "success"

    def test_drafter_can_delete_specs(self, drafter: FileSystemTool, project: Path) -> None:
        result = drafter.delete_file("specs/billing_spec.md")
        assert result.status == "success"

    def test_drafter_can_read_source(self, drafter: FileSystemTool) -> None:
        result = drafter.read_file("src/domain/billing/calc.py")
        assert result.status == "success"

    def test_drafter_cannot_write_source(self, drafter: FileSystemTool) -> None:
        """Drafter has READ-only on src — cannot modify source code."""
        result = drafter.write_file("src/domain/billing/calc.py", "hacked")
        assert result.status == "error"


# ===========================================================================
# Additive Grant Resolution
# ===========================================================================


class TestAdditiveGrants:
    """Multiple grants combine — most permissive wins for overlapping paths."""

    def test_overlapping_grants_most_permissive_wins(self, executor: FileExecutor) -> None:
        """If two grants cover the same path, most permissive mode wins."""
        grants = [
            FolderGrant("src", AccessMode.READ, recursive=True),
            FolderGrant("src/domain/billing", AccessMode.FULL, recursive=True),
        ]
        tool = FileSystemTool(executor=executor, role="implementer", grants=grants)
        # Can write to billing (FULL wins over parent READ)
        result = tool.write_file("src/domain/billing/calc.py", "# updated")
        assert result.status == "success"
        # Can only read from shared (only READ grant)
        result = tool.read_file("src/shared/currency/rates.py")
        assert result.status == "success"
        result = tool.write_file("src/shared/currency/rates.py", "hacked")
        assert result.status == "error"
