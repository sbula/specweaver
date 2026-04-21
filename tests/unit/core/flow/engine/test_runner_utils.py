# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.core.flow.engine.runner_utils import setup_sandbox_caches
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.loom.atoms.base import AtomResult, AtomStatus


def test_setup_sandbox_caches_uses_file_system_atom(tmp_path: Path) -> None:
    """Test that setup_sandbox_caches uses FileSystemAtom for safe linking."""
    # Create mock context
    context = MagicMock(spec=RunContext)
    context.project_path = tmp_path

    # Create dummy node_modules to trigger linking
    (tmp_path / "node_modules").mkdir()

    logger = MagicMock()

    success_result = AtomResult(status=AtomStatus.SUCCESS, message="OK")

    with patch("specweaver.core.loom.atoms.filesystem.atom.FileSystemAtom") as mock_atom_cls:
        mock_atom_instance = mock_atom_cls.return_value
        mock_atom_instance.run.return_value = success_result

        setup_sandbox_caches(context, ".worktrees/default", logger)

        # Ensure FileSystemAtom was used
        mock_atom_cls.assert_called_once_with(cwd=tmp_path)

        # Verify run was called with correct intent
        mock_atom_instance.run.assert_called_with(
            {
                "intent": "symlink",
                "target": "node_modules",
                "link_name": ".worktrees/default/node_modules",
            }
        )
