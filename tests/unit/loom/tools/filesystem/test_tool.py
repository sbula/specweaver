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

from typing import TYPE_CHECKING

import pytest

from specweaver.loom.commons.filesystem.executor import FileExecutor
from specweaver.loom.security import AccessMode, FolderGrant
from specweaver.loom.tools.filesystem.models import (
    ROLE_INTENTS,
    FileSystemToolError,
)
from specweaver.loom.tools.filesystem.tool import FileSystemTool

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a project with subdirectories and files."""
    # Source tree
    (tmp_path / "src" / "domain" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "domain" / "billing" / "calc.py").write_text(
        "def total(a, b): return a + b",
        encoding="utf-8",
    )
    (tmp_path / "src" / "domain" / "billing" / "context.yaml").write_text(
        "name: billing\nlevel: module\npurpose: Billing logic\narchetype: pure-logic\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "shared" / "currency").mkdir(parents=True)
    (tmp_path / "src" / "shared" / "currency" / "rates.py").write_text(
        "EUR = 1.0\nUSD = 1.1",
        encoding="utf-8",
    )
    (tmp_path / "src" / "shared" / "currency" / "context.yaml").write_text(
        "name: currency\nlevel: module\npurpose: Currency exchange rates and conversion\narchetype: pure-logic\n",
        encoding="utf-8",
    )
    # Specs
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "billing_spec.md").write_text("# Billing Spec\n", encoding="utf-8")
    # Tests
    (tmp_path / "tests" / "unit" / "billing").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "billing" / "test_calc.py").write_text(
        "def test_total(): assert True",
        encoding="utf-8",
    )
    # Root context
    (tmp_path / "context.yaml").write_text(
        "name: test-project\nlevel: system\n",
        encoding="utf-8",
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
        assert ROLE_INTENTS["implementer"] == frozenset(expected)

    def test_reviewer_intents(self) -> None:
        expected = {"read_file", "list_directory", "search_content", "grep", "find_files"}
        assert ROLE_INTENTS["reviewer"] == frozenset(expected)

    def test_drafter_intents(self) -> None:
        expected = {
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
            "tests/unit/billing/test_invoice.py",
            "def test_it(): pass",
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


# ===========================================================================
# Grant Bypass Attack Vectors
# ===========================================================================


class TestGrantBypassAttempts:
    """Security: prevent agents from escaping grants via path manipulation."""

    def test_dotdot_read_escape_blocked_outside_grants(self, implementer: FileSystemTool) -> None:
        """Agent tries ../.. to reach a path with NO grant at all."""
        result = implementer.read_file("src/domain/billing/../../../specs/billing_spec.md")
        assert result.status == "error"

    def test_dotdot_write_escalation_blocked(self, implementer: FileSystemTool) -> None:
        """Agent has FULL on billing, READ on shared/currency. Tries to
        WRITE to shared via ../ from billing — must be blocked."""
        result = implementer.write_file(
            "src/domain/billing/../../shared/currency/rates.py",
            "hacked",
        )
        assert result.status == "error"

    def test_dotdot_write_escape(self, implementer: FileSystemTool) -> None:
        """Agent tries to WRITE outside grant via ../."""
        result = implementer.write_file(
            "src/domain/billing/../../../specs/hacked.md",
            "hacked",
        )
        assert result.status == "error"

    def test_dotdot_to_root_context_yaml(self, implementer: FileSystemTool) -> None:
        """Agent tries to reach root context.yaml via ../."""
        result = implementer.write_file(
            "src/domain/billing/../../../context.yaml",
            "hacked: true",
        )
        assert result.status == "error"

    def test_backslash_normalization(self, implementer: FileSystemTool) -> None:
        """Agent uses backslashes to confuse path matching."""
        result = implementer.read_file("src\\domain\\billing\\calc.py")
        assert result.status == "success"

    def test_trailing_slash_in_path(self, implementer: FileSystemTool) -> None:
        """Trailing slash should not confuse grant matching."""
        result = implementer.list_directory("src/domain/billing/")
        assert result.status == "success"

    def test_empty_grants_blocks_everything(self, executor: FileExecutor) -> None:
        """Tool with no grants blocks all operations."""
        tool = FileSystemTool(executor=executor, role="implementer", grants=[])
        result = tool.read_file("src/domain/billing/calc.py")
        assert result.status == "error"

    def test_dotdot_in_middle_of_granted_path(
        self,
        executor: FileExecutor,
        project: Path,
    ) -> None:
        """src/domain/../domain/billing/calc.py normalizes INTO grant — should be allowed."""
        grants = [FolderGrant("src/domain/billing", AccessMode.FULL, recursive=True)]
        tool = FileSystemTool(executor=executor, role="implementer", grants=grants)
        result = tool.read_file("src/domain/../domain/billing/calc.py")
        assert result.status == "success"

    def test_dotdot_escapes_then_returns(self, implementer: FileSystemTool) -> None:
        """src/domain/billing/../../shared/../../domain/billing/calc.py resolves
        to domain/billing/calc.py (NOT src/domain/billing/calc.py) because
        the .. segments consume 'src'. This is correctly outside any grant."""
        result = implementer.read_file(
            "src/domain/billing/../../shared/../../domain/billing/calc.py",
        )
        # Normalizes to domain/billing/calc.py — no grant covers this
        assert result.status == "error"


# ===========================================================================
# find_placement MVP (keyword matching)
# ===========================================================================


class TestFindPlacement:
    """find_placement uses keyword matching on context.yaml purpose fields."""

    def test_finds_matching_boundary(self, implementer: FileSystemTool) -> None:
        """Keywords in description match purpose field."""
        result = implementer.find_placement("billing calculation")
        assert result.status == "success"
        assert len(result.data) > 0
        paths = [m["path"] for m in result.data]
        assert any("billing" in p for p in paths)

    def test_no_match(self, implementer: FileSystemTool) -> None:
        """No keywords match any purpose field."""
        result = implementer.find_placement("quantum teleportation flux")
        assert result.status == "success"
        assert len(result.data) == 0

    def test_returns_purpose_and_path(self, implementer: FileSystemTool) -> None:
        """Each match includes path, name, and purpose."""
        result = implementer.find_placement("currency")
        assert result.status == "success"
        assert len(result.data) > 0
        for match in result.data:
            assert "path" in match
            assert "name" in match
            assert "purpose" in match

    def test_case_insensitive(self, implementer: FileSystemTool) -> None:
        """Matching is case-insensitive."""
        result = implementer.find_placement("BILLING")
        assert result.status == "success"
        assert len(result.data) > 0

    def test_partial_word_match(self, implementer: FileSystemTool) -> None:
        """Partial words still match (substring matching)."""
        result = implementer.find_placement("exchang")  # partial 'exchange'
        assert result.status == "success"
        assert len(result.data) > 0

    def test_multiple_keywords_ranked(self, implementer: FileSystemTool) -> None:
        """More keyword matches = higher score."""
        result = implementer.find_placement("currency exchange rates conversion")
        assert result.status == "success"
        # currency module should score highest (all keywords match)
        if len(result.data) > 0:
            assert "currency" in result.data[0]["name"] or "currency" in result.data[0]["path"]


# ===========================================================================
# search_content recursive
# ===========================================================================


class TestSearchContentRecursive:
    """search_content should support recursive subdirectory search."""

    def test_recursive_search_finds_nested_files(
        self,
        executor: FileExecutor,
        project: Path,
    ) -> None:
        """Recursive search finds matches in subdirectories."""
        grants = [FolderGrant("src", AccessMode.READ, recursive=True)]
        tool = FileSystemTool(executor=executor, role="reviewer", grants=grants)
        result = tool.search_content("src", r"def \w+", recursive=True)
        assert result.status == "success"
        # Should find 'def total' in src/domain/billing/calc.py
        found_files = [m["file"] for m in result.data]
        assert any("calc.py" in f for f in found_files)

    def test_non_recursive_search_direct_children_only(
        self,
        executor: FileExecutor,
    ) -> None:
        """Non-recursive search only searches direct children."""
        grants = [FolderGrant("src", AccessMode.READ, recursive=True)]
        tool = FileSystemTool(executor=executor, role="reviewer", grants=grants)
        result = tool.search_content("src", r"def \w+", recursive=False)
        assert result.status == "success"
        # Direct children of src/ are directories, no .py files
        assert len(result.data) == 0

    def test_default_is_non_recursive(self, implementer: FileSystemTool) -> None:
        """Default behavior is non-recursive (backward compatible)."""
        result = implementer.search_content("src/domain/billing", r"def \w+")
        assert result.status == "success"
        assert len(result.data) > 0  # finds calc.py (direct child)


# ===========================================================================
# Path Traversal Attack Surface (edge cases)
# ===========================================================================


class TestPathTraversalEdgeCases:
    """Security-critical: test path normalization against traversal attacks."""

    def test_absolute_unix_path_blocked(self, implementer: FileSystemTool) -> None:
        """Absolute path like /etc/passwd should not match any grant."""
        result = implementer.read_file("/etc/passwd")
        assert result.status == "error"

    def test_absolute_windows_path_blocked(self, implementer: FileSystemTool) -> None:
        """Absolute Windows path should not match any grant."""
        result = implementer.read_file("C:\\Windows\\System32\\config.sys")
        assert result.status == "error"

    def test_empty_path_normalization(self, executor: FileExecutor) -> None:
        """Empty path normalizes to '' — no grant should cover it."""
        from specweaver.loom.tools.filesystem.tool import FileSystemTool as FSTool

        _ = FSTool(executor=executor, role="implementer", grants=[])
        assert FSTool._normalize_path("") == ""

    def test_empty_path_read_blocked(self, implementer: FileSystemTool) -> None:
        """Reading empty path should be blocked (no grant covers root)."""
        result = implementer.read_file("")
        assert result.status == "error"

    def test_dot_path_normalization(self) -> None:
        """Single dot normalizes to empty string."""
        from specweaver.loom.tools.filesystem.tool import FileSystemTool as FSTool

        assert FSTool._normalize_path(".") == ""

    def test_dotdot_beyond_root(self) -> None:
        """Path that goes above root via .. should normalize safely."""
        from specweaver.loom.tools.filesystem.tool import FileSystemTool as FSTool

        # posixpath.normpath("a/../../b") == "../b"
        result = FSTool._normalize_path("a/../../b")
        assert ".." not in result or result.startswith("..")
        # The key is that this should NOT match any grant starting with "a/"

    def test_dotdot_escape_with_delete(self, implementer: FileSystemTool) -> None:
        """Agent tries to delete a file outside grants via .. traversal."""
        result = implementer.delete_file("src/domain/billing/../../../specs/billing_spec.md")
        assert result.status == "error"

    def test_dotdot_escape_with_create(self, implementer: FileSystemTool) -> None:
        """Agent tries to create a file outside grants via .. traversal."""
        result = implementer.create_file(
            "src/domain/billing/../../../evil.py",
            "import os; os.system('rm -rf /')",
        )
        assert result.status == "error"

    def test_dotdot_escape_with_edit(self, implementer: FileSystemTool) -> None:
        """Agent tries to edit a file outside grants via .. traversal."""
        result = implementer.edit_file(
            "src/domain/billing/../../../specs/billing_spec.md",
            old="# Billing Spec",
            new="# HACKED",
        )
        assert result.status == "error"

    def test_dotdot_escape_with_list(self, implementer: FileSystemTool) -> None:
        """Agent tries to list a directory outside grants via .. traversal."""
        result = implementer.list_directory("src/domain/billing/../../../")
        assert result.status == "error"

    def test_dotdot_escape_with_search(self, implementer: FileSystemTool) -> None:
        """Agent tries to search in a directory outside grants via .. traversal."""
        result = implementer.search_content(
            "src/domain/billing/../../../specs",
            r".*",
        )
        assert result.status == "error"

    def test_multiple_slashes_normalized(self, implementer: FileSystemTool) -> None:
        """Multiple consecutive slashes should not bypass normalization."""
        result = implementer.read_file("src///domain///billing///calc.py")
        assert result.status == "success"

    def test_grant_at_root_covers_everything(self, executor: FileExecutor) -> None:
        """A grant with empty path does NOT cover subdirectories (security)."""
        grants = [FolderGrant("", AccessMode.READ, recursive=True)]
        tool = FileSystemTool(executor=executor, role="reviewer", grants=grants)
        result = tool.read_file("src/domain/billing/calc.py")
        # Empty-string grant path is treated as invalid — doesn't match
        assert result.status == "error"


# ===========================================================================
# search_content edge cases
# ===========================================================================


class TestSearchContentEdgeCases:
    """Edge cases for the search_content intent."""

    def test_invalid_regex_returns_error(self, implementer: FileSystemTool) -> None:
        """Invalid regex pattern should return an ToolResult error, not crash."""
        result = implementer.search_content("src/domain/billing", r"[invalid")
        assert result.status == "error"
        assert "Invalid regex" in result.message

    def test_search_empty_pattern_matches_everything(
        self,
        implementer: FileSystemTool,
    ) -> None:
        """Empty regex matches every line."""
        result = implementer.search_content("src/domain/billing", r"")
        assert result.status == "success"
        assert len(result.data) > 0


# ===========================================================================
# find_placement edge cases
# ===========================================================================


class TestFindPlacementEdgeCases:
    """Edge cases for the find_placement intent."""

    def test_empty_description(self, implementer: FileSystemTool) -> None:
        """Empty description has no keywords → empty results."""
        result = implementer.find_placement("")
        assert result.status == "success"
        assert result.data == []

    def test_short_words_filtered(self, implementer: FileSystemTool) -> None:
        """Words shorter than 3 chars are filtered out as noise."""
        result = implementer.find_placement("a to of")
        assert result.status == "success"
        assert result.data == []

    def test_find_placement_no_context_yaml(self, tmp_path: Path) -> None:
        """find_placement in a project with no context.yaml returns empty."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "code.py").write_text("x=1", encoding="utf-8")
        executor = FileExecutor(cwd=tmp_path)
        grants = [FolderGrant("src", AccessMode.READ, recursive=True)]
        tool = FileSystemTool(executor=executor, role="implementer", grants=grants)
        result = tool.find_placement("some feature")
        assert result.status == "success"
        assert result.data == []
