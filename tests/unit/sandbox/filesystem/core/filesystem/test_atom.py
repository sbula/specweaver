# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.sandbox.filesystem.core.atom — TDD.

FileSystemAtom is the engine-level counterpart. It has unrestricted access
(uses EngineFileExecutor) for operations like:
- scaffold: create directory structure + context.yaml from spec boundaries
- backup / restore: file rollback for engine state management
- aggregate_context: build project-wide boundary map
- validate_boundaries: check all boundaries for consistency
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.filesystem.core.atom import FileSystemAtom

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with some existing structure."""
    (tmp_path / "src" / "domain" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "domain" / "billing" / "calc.py").write_text(
        "def total(a, b): return a + b",
        encoding="utf-8",
    )
    (tmp_path / "src" / "domain" / "billing" / "context.yaml").write_text(
        "name: billing\nlevel: module\npurpose: Billing logic\narchetype: pure-logic\n",
        encoding="utf-8",
    )
    (tmp_path / "context.yaml").write_text(
        "name: test-project\nlevel: system\npurpose: Test project\narchetype: orchestrator\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def atom(project: Path) -> FileSystemAtom:
    return FileSystemAtom(cwd=project)


# ===========================================================================
# Dispatch
# ===========================================================================


class TestDispatch:
    """Atom.run() dispatches to the correct intent."""

    def test_missing_intent_fails(self, atom: FileSystemAtom) -> None:
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "intent" in result.message.lower()

    def test_unknown_intent_fails(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "explode"})
        assert result.status == AtomStatus.FAILED
        assert "explode" in result.message

    def test_known_intents(self, atom: FileSystemAtom) -> None:
        """All expected intents are registered."""
        expected = {"scaffold", "backup", "restore", "aggregate_context", "validate_boundaries"}
        assert expected <= atom._known_intents()


# ===========================================================================
# Scaffold Intent
# ===========================================================================


class TestScaffoldIntent:
    """scaffold creates directory structure with context.yaml files."""

    def test_scaffold_creates_directories(self, atom: FileSystemAtom, project: Path) -> None:
        result = atom.run(
            {
                "intent": "scaffold",
                "boundaries": [
                    {
                        "path": "src/domain/payments",
                        "name": "payments",
                        "level": "module",
                        "purpose": "Payment processing",
                        "archetype": "orchestrator",
                    },
                ],
            }
        )
        assert result.status == AtomStatus.SUCCESS
        assert (project / "src" / "domain" / "payments").is_dir()

    def test_scaffold_creates_context_yaml(self, atom: FileSystemAtom, project: Path) -> None:
        atom.run(
            {
                "intent": "scaffold",
                "boundaries": [
                    {
                        "path": "src/domain/payments",
                        "name": "payments",
                        "level": "module",
                        "purpose": "Payment processing",
                        "archetype": "orchestrator",
                    },
                ],
            }
        )
        ctx = project / "src" / "domain" / "payments" / "context.yaml"
        assert ctx.is_file()
        content = ctx.read_text(encoding="utf-8")
        assert "payments" in content
        assert "module" in content
        assert "Payment processing" in content

    def test_scaffold_multiple_boundaries(self, atom: FileSystemAtom, project: Path) -> None:
        result = atom.run(
            {
                "intent": "scaffold",
                "boundaries": [
                    {
                        "path": "src/infra/db",
                        "name": "db",
                        "level": "module",
                        "purpose": "Database access",
                        "archetype": "adapter",
                    },
                    {
                        "path": "src/infra/cache",
                        "name": "cache",
                        "level": "module",
                        "purpose": "Caching layer",
                        "archetype": "adapter",
                    },
                ],
            }
        )
        assert result.status == AtomStatus.SUCCESS
        assert (project / "src" / "infra" / "db" / "context.yaml").is_file()
        assert (project / "src" / "infra" / "cache" / "context.yaml").is_file()

    def test_scaffold_does_not_overwrite_existing_context(
        self,
        atom: FileSystemAtom,
        project: Path,
    ) -> None:
        """If context.yaml already exists, scaffold does NOT overwrite it."""
        result = atom.run(
            {
                "intent": "scaffold",
                "boundaries": [
                    {
                        "path": "src/domain/billing",
                        "name": "billing-v2",
                        "level": "module",
                        "purpose": "New billing",
                        "archetype": "pure-logic",
                    },
                ],
            }
        )
        assert result.status == AtomStatus.SUCCESS
        # Original content preserved
        content = (project / "src/domain/billing/context.yaml").read_text()
        assert "billing" in content  # original name
        assert "billing-v2" not in content  # NOT overwritten

    def test_scaffold_missing_boundaries_fails(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "scaffold"})
        assert result.status == AtomStatus.FAILED

    def test_scaffold_exports_created_paths(self, atom: FileSystemAtom) -> None:
        result = atom.run(
            {
                "intent": "scaffold",
                "boundaries": [
                    {
                        "path": "src/new",
                        "name": "new",
                        "level": "module",
                        "purpose": "New module",
                        "archetype": "pure-logic",
                    },
                ],
            }
        )
        assert "created_paths" in result.exports

    def test_scaffold_with_consumes_and_forbids(
        self,
        atom: FileSystemAtom,
        project: Path,
    ) -> None:
        """Scaffold writes consumes/forbids into context.yaml."""
        atom.run(
            {
                "intent": "scaffold",
                "boundaries": [
                    {
                        "path": "src/domain/taxes",
                        "name": "taxes",
                        "level": "module",
                        "purpose": "Tax calcs",
                        "archetype": "pure-logic",
                        "consumes": ["shared/currency"],
                        "forbids": ["infra/*"],
                    },
                ],
            }
        )
        content = (project / "src/domain/taxes/context.yaml").read_text()
        assert "shared/currency" in content
        assert "infra/*" in content


# ===========================================================================
# Backup / Restore Intents
# ===========================================================================


class TestBackupRestoreIntents:
    """backup copies files, restore reverts them."""

    def test_backup_file(self, atom: FileSystemAtom, project: Path) -> None:
        (project / ".specweaver" / "backups").mkdir(parents=True)
        result = atom.run(
            {
                "intent": "backup",
                "source": "src/domain/billing/calc.py",
                "backup_dir": ".specweaver/backups",
            }
        )
        assert result.status == AtomStatus.SUCCESS
        # Backup file exists somewhere in backup_dir
        backups = list((project / ".specweaver" / "backups").iterdir())
        assert len(backups) > 0

    def test_backup_nonexistent_file_fails(self, atom: FileSystemAtom, project: Path) -> None:
        (project / ".specweaver" / "backups").mkdir(parents=True)
        result = atom.run(
            {
                "intent": "backup",
                "source": "nonexistent.py",
                "backup_dir": ".specweaver/backups",
            }
        )
        assert result.status == AtomStatus.FAILED

    def test_restore_file(self, atom: FileSystemAtom, project: Path) -> None:
        """Backup then restore should return original content."""
        (project / ".specweaver" / "backups").mkdir(parents=True)
        # Backup
        backup_result = atom.run(
            {
                "intent": "backup",
                "source": "src/domain/billing/calc.py",
                "backup_dir": ".specweaver/backups",
            }
        )
        backup_path = backup_result.exports["backup_path"]

        # Modify original
        (project / "src/domain/billing/calc.py").write_text("CORRUPTED", encoding="utf-8")

        # Restore
        result = atom.run(
            {
                "intent": "restore",
                "source": backup_path,
                "target": "src/domain/billing/calc.py",
            }
        )
        assert result.status == AtomStatus.SUCCESS
        assert "total" in (project / "src/domain/billing/calc.py").read_text()

    def test_backup_missing_source_key(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "backup", "backup_dir": ".specweaver/backups"})
        assert result.status == AtomStatus.FAILED

    def test_restore_missing_keys(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "restore"})
        assert result.status == AtomStatus.FAILED


# ===========================================================================
# Aggregate Context Intent
# ===========================================================================


class TestAggregateContextIntent:
    """aggregate_context collects all context.yaml files into a project map."""

    def test_finds_all_boundaries(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "aggregate_context"})
        assert result.status == AtomStatus.SUCCESS
        boundaries = result.exports.get("boundaries", [])
        # Should find root context.yaml + billing context.yaml
        paths = [b["path"] for b in boundaries]
        assert any("billing" in p for p in paths)

    def test_exports_boundary_data(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "aggregate_context"})
        boundaries = result.exports["boundaries"]
        for b in boundaries:
            assert "path" in b
            assert "name" in b
            assert "level" in b


# ===========================================================================
# Validate Boundaries Intent
# ===========================================================================


class TestValidateBoundariesIntent:
    """validate_boundaries checks all context.yaml files for consistency."""

    def test_valid_project_succeeds(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "validate_boundaries"})
        assert result.status == AtomStatus.SUCCESS

    def test_invalid_context_yaml_reports_errors(
        self,
        atom: FileSystemAtom,
        project: Path,
    ) -> None:
        """A context.yaml missing required 'name' field should be flagged."""
        (project / "src" / "domain" / "billing" / "context.yaml").write_text(
            "level: module\n",
            encoding="utf-8",  # missing 'name'
        )
        result = atom.run({"intent": "validate_boundaries"})
        # Could be SUCCESS with warnings, or FAILED — depends on severity
        errors = result.exports.get("errors", [])
        assert len(errors) > 0

    def test_invalid_consumes_reference(
        self,
        atom: FileSystemAtom,
        project: Path,
    ) -> None:
        """A context.yaml that consumes a nonexistent path should be flagged."""
        (project / "src" / "domain" / "billing" / "context.yaml").write_text(
            "name: billing\nlevel: module\nconsumes:\n  - nonexistent/module\n",
            encoding="utf-8",
        )
        result = atom.run({"intent": "validate_boundaries"})
        errors = result.exports.get("errors", [])
        assert any("nonexistent" in e for e in errors)

    def test_valid_consumes_reference(
        self,
        atom: FileSystemAtom,
        project: Path,
    ) -> None:
        """A context.yaml that consumes an existing path should NOT be flagged."""
        # Create a module that billing consumes
        (project / "src" / "shared" / "currency").mkdir(parents=True)
        (project / "src" / "shared" / "currency" / "context.yaml").write_text(
            "name: currency\nlevel: module\n",
            encoding="utf-8",
        )
        (project / "src" / "domain" / "billing" / "context.yaml").write_text(
            "name: billing\nlevel: module\nconsumes:\n  - src/shared/currency\n",
            encoding="utf-8",
        )
        result = atom.run({"intent": "validate_boundaries"})
        errors = result.exports.get("errors", [])
        consumes_errors = [e for e in errors if "consumes" in e.lower()]
        assert len(consumes_errors) == 0


# ===========================================================================
# Symlink Intent
# ===========================================================================


class TestSymlinkIntent:
    """symlink intent routes correctly to file executor."""

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_valid(self, atom: FileSystemAtom, project: Path) -> None:
        (project / "node_modules").mkdir()
        result = atom.run(
            {
                "intent": "symlink",
                "target": "node_modules",
                "link_name": ".worktrees/agent/node_modules",
            }
        )
        assert result.status == AtomStatus.SUCCESS
        assert (project / ".worktrees" / "agent" / "node_modules").is_symlink()

    def test_symlink_missing_keys(self, atom: FileSystemAtom) -> None:
        result = atom.run({"intent": "symlink"})
        assert result.status == AtomStatus.FAILED
        assert "Missing" in result.message
