import sys
from pathlib import Path

base_path = Path("src/specweaver/interfaces/cli")
dest_path = Path("src/specweaver/workspace/project/interfaces/cli.py")

files = ["projects.py", "constitution.py", "hooks.py"]

content_lines = [
    "# Copyright (c) 2026 sbula. All rights reserved.",
    "# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.",
    "",
    '"""CLI commands for workspace project management: projects, constitution, hooks."""',
    "",
    "from __future__ import annotations",
    "",
    "import logging",
    "import stat",
    "import sys",
    "import shutil",
    "from pathlib import Path",
    "from typing import TYPE_CHECKING, Any",
    "",
    "import anyio",
    "import typer",
    "from rich.table import Table",
    "",
    "from specweaver.interfaces.cli import _core",
    "from specweaver.workspace.project.discovery import resolve_project_path",
    "from specweaver.workspace.project.scaffold import scaffold_project",
    "from specweaver.workspace.project.tach_sync import sync_tach_toml",
    "from specweaver.workspace.project.constitution import check_constitution, find_constitution",
    "from specweaver.workspace.store import WorkspaceRepository",
    "",
    "logger = logging.getLogger(__name__)",
    "",
]

# Add _run_workspace_op
content_lines.extend([
    "def _run_workspace_op(method_name: str, *args: Any, **kwargs: Any) -> Any:",
    "    db = _core.get_db()",
    "    async def _action() -> Any:",
    "        async with db.async_session_scope() as session:",
    "            repo = WorkspaceRepository(session)",
    "            method = getattr(repo, method_name)",
    "            return await method(*args, **kwargs)",
    "    return anyio.run(_action)",
    "",
])

# Read and merge files
for f_name in files:
    f_path = base_path / f_name
    text = f_path.read_text(encoding="utf-8")
    
    # Remove header comments and imports
    lines = text.split("\n")
    import_done = False
    new_lines = []
    for line in lines:
        if not import_done:
            # Skip until we hit the first @ or specific app def
            if line.startswith("@") or line.startswith("constitution_app =") or line.startswith("hooks_app ="):
                import_done = True
            else:
                if line.startswith("HOOK_TEMPLATE"):
                    import_done = True
                else:
                    continue
        
        # Replace _helpers._run_workspace_op with just _run_workspace_op
        line = line.replace("_helpers._run_workspace_op", "_run_workspace_op")
        
        new_lines.append(line)
        
    content_lines.extend(new_lines)

dest_path.parent.mkdir(parents=True, exist_ok=True)
dest_path.write_text("\n".join(content_lines), encoding="utf-8")
print(f"Created {dest_path}")
