# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for GitAtom and FileSystemAtom worktree orchestrations."""

import os
import subprocess
from pathlib import Path

import pytest

from specweaver.loom.atoms.base import AtomStatus
from specweaver.loom.atoms.filesystem.atom import FileSystemAtom
from specweaver.loom.atoms.git.atom import GitAtom


@pytest.fixture
def repo_with_cache(tmp_path: Path) -> Path:
    """Creates a real git repo with a dummy cache folder."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize real git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "agent@test.com"], cwd=repo_dir, check=True)

    # Create fake cache (like node_modules)
    cache_dir = repo_dir / "node_modules"
    cache_dir.mkdir()
    (cache_dir / "lib.js").write_text("console.log('hello');")

    # Commit to master
    (repo_dir / "README.md").write_text("# Main")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=repo_dir, check=True)

    return repo_dir


def test_worktree_sandbox_lifecycle_integration(repo_with_cache: Path) -> None:
    """Verifies FR-1, FR-2, FR-6 natively: add worktree -> symlink cache -> teardown."""

    git_atom = GitAtom(cwd=repo_with_cache)
    fs_atom = FileSystemAtom(cwd=repo_with_cache)

    wt_path = ".worktrees/agent-xyz"
    branch_name = "feat/agent-xyz"

    # 1. Add Worktree (FR-1)
    res_add = git_atom.run(
        {
            "intent": "worktree_add",
            "path": wt_path,
            "branch": branch_name,
        }
    )
    assert res_add.status == AtomStatus.SUCCESS

    abs_wt_path = repo_with_cache / wt_path
    assert abs_wt_path.exists()
    assert (abs_wt_path / "README.md").exists()

    # 2. Symlink Cache (FR-2)
    # Target is inside the repo, link_name is inside the worktree
    res_symlink = fs_atom.run(
        {
            "intent": "symlink",
            "target": "node_modules",
            "link_name": f"{wt_path}/node_modules",
        }
    )
    # Skip symlink assertion on Windows due to symlink perm failures without admin
    # Just checking it doesn't crash the atom loop.
    if os.name != "nt":
        assert res_symlink.status == AtomStatus.SUCCESS
        assert (abs_wt_path / "node_modules").is_symlink()
        assert (abs_wt_path / "node_modules" / "lib.js").exists()

    # 3. Simulate Agent edits inside sandbox
    (abs_wt_path / "agent.py").write_text("print(1)")
    subprocess.run(["git", "add", "agent.py"], cwd=abs_wt_path, check=True)
    subprocess.run(["git", "commit", "-m", "Agent commit"], cwd=abs_wt_path, check=True)

    # 4. Teardown Worktree (FR-6)
    res_teardown = git_atom.run(
        {
            "intent": "worktree_teardown",
            "path": wt_path,
        }
    )
    assert res_teardown.status == AtomStatus.SUCCESS
    assert not abs_wt_path.exists()  # Ensure physical removal

    # 5. Ensure parent repo is clean and agent branch exists
    output = subprocess.run(
        ["git", "branch"], cwd=repo_with_cache, capture_output=True, text=True
    ).stdout
    assert branch_name in output
