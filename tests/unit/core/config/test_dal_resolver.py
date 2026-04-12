# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for DALResolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.enums.dal import DALLevel

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    return tmp_path / "project"


@pytest.fixture()
def dal_resolver(project_root: Path):
    from specweaver.core.config.dal_resolver import DALResolver

    return DALResolver(project_root)


def write_context(path: Path, dal_level: str | None = None) -> None:
    """Helper to write context.yaml."""
    path.mkdir(parents=True, exist_ok=True)
    yaml_file = path / "context.yaml"
    if dal_level:
        yaml_file.write_text(f"operational:\n  dal_level: {dal_level}\n")
    else:
        yaml_file.write_text("operational:\n  other: true\n")


def test_resolve_direct_directory(dal_resolver, project_root: Path):
    """Target directory has context.yaml with DAL."""
    target_dir = project_root / "src" / "core"
    write_context(target_dir, "DAL_A")
    target_file = target_dir / "app.py"

    dal = dal_resolver.resolve(target_file)
    assert dal == DALLevel.DAL_A


def test_resolve_fractal_lookup(dal_resolver, project_root: Path):
    """Target file looks up to parent directories."""
    parent_dir = project_root / "src"
    write_context(parent_dir, "DAL_B")

    # Subdir has no context.yaml
    target_dir = parent_dir / "core" / "utils"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "helper.py"

    dal = dal_resolver.resolve(target_file)
    assert dal == DALLevel.DAL_B


def test_resolve_skips_context_without_dal(dal_resolver, project_root: Path):
    """Looks past context.yaml files that lack dal_level."""
    root_dir = project_root
    write_context(root_dir, "DAL_C")

    # This context.yaml exists but has no DAL level
    sub_dir = project_root / "src"
    write_context(sub_dir, dal_level=None)

    target_file = sub_dir / "app.py"
    dal = dal_resolver.resolve(target_file)
    assert dal == DALLevel.DAL_C


def test_resolve_halts_at_project_root(dal_resolver, project_root: Path):
    """Returns None if root is reached without finding DAL."""
    # Write context outside project root, should NOT be hit
    write_context(project_root.parent, "DAL_A")

    target_file = project_root / "src" / "app.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.touch()

    dal = dal_resolver.resolve(target_file)
    assert dal is None


def test_resolve_invalid_dal_raises(dal_resolver, project_root: Path):
    """Raises ValueError if dal_level is invalid."""
    target_dir = project_root / "src"
    write_context(target_dir, "DAL_Z")
    target_file = target_dir / "app.py"

    with pytest.raises(ValueError, match="DAL_Z is not a valid DALLevel"):
        dal_resolver.resolve(target_file)


def test_resolve_caching(dal_resolver, project_root: Path):
    """Subsequent resolves from same path use cache."""
    target_dir = project_root / "src"
    write_context(target_dir, "DAL_D")

    target_file1 = target_dir / "app.py"
    target_file2 = target_dir / "utils.py"

    # First call walks the tree
    assert dal_resolver.resolve(target_file1) == DALLevel.DAL_D

    # Second call should be O(1) from cache!
    # Delete the context.yaml to prove it doesn't read the disk again
    (target_dir / "context.yaml").unlink()

    assert dal_resolver.resolve(target_file1) == DALLevel.DAL_D

    # target_file2 is effectively a new directory lookup for `target_file2.parent`
    # Wait, the cache is keyed by the target_path's parent directory, or the exact path?
    # The requirement is O(1) tree walking. A target file maps to its folder.
    # The cache should ideally key by directories walked to avoid re-walking.
    # For now, let's just make sure it caches by `target_path`.
    dal_resolver._cache[target_file2] = DALLevel.DAL_E
    assert dal_resolver.resolve(target_file2) == DALLevel.DAL_E


def test_resolve_invalid_yaml_skips(dal_resolver, project_root: Path):
    """If context.yaml contains unparseable syntax, it is treated as empty and traversal continues."""
    parent_dir = project_root / "src"
    write_context(parent_dir, "DAL_A")

    target_dir = parent_dir / "core"
    target_dir.mkdir(parents=True, exist_ok=True)
    yaml_file = target_dir / "context.yaml"
    yaml_file.write_text("operational:\n  dal_level: [invalid yaml parsing")

    target_file = target_dir / "app.py"
    dal = dal_resolver.resolve(target_file)
    # Should safely skip the broken YAML and find DAL_A in parent
    assert dal == DALLevel.DAL_A


def test_resolve_malformed_operational_block_skips(dal_resolver, project_root: Path):
    """If 'operational' is not a dict, it is ignored and traversal continues."""
    parent_dir = project_root / "src"
    write_context(parent_dir, "DAL_B")

    target_dir = parent_dir / "core"
    target_dir.mkdir(parents=True, exist_ok=True)
    yaml_file = target_dir / "context.yaml"
    yaml_file.write_text("operational: string_value_not_dict\n")

    target_file = target_dir / "app.py"
    dal = dal_resolver.resolve(target_file)
    assert dal == DALLevel.DAL_B


def test_resolve_os_root_boundary(dal_resolver, project_root: Path):
    """If target_path is entirely outside project_root, traversal hits OS root safely."""
    # Write a context.yaml in an entirely disparate path hierarchy
    external_dir = project_root.parent / "external_lib"
    external_dir.mkdir()
    target_file = external_dir / "lib.py"

    dal = dal_resolver.resolve(target_file)
    assert dal is None
