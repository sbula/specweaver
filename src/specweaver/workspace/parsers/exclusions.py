# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
from pathlib import Path

import pathspec

logger = logging.getLogger(__name__)

class SpecWeaverIgnoreParser:
    """
    High-performance polyglot exclusion engine.
    Centralizes the deterministic matching of files against .specweaverignore,
    language-specific binary patterns, and globally scaffolded defaults.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.ignore_path = self.project_root / ".specweaverignore"

    def ensure_scaffolded(self, default_directories: list[str]) -> None:
        """
        Safely seeds the .specweaverignore file with defaults if they don't already exist.
        """
        existing_lines = []
        if self.ignore_path.exists():
            if self.ignore_path.is_file():
                existing_lines = [line.strip() for line in self.ignore_path.read_text(encoding="utf-8").splitlines()]
            else:
                logger.warning(f"Exclusion path {self.ignore_path} exists but is not a file. Skipping scaffolding.")
                return

        # Deduplicate defaults against existing lines, preserving existing ones
        to_append = []
        for d in default_directories:
            if d.strip() not in existing_lines:
                to_append.append(d)

        if to_append:
            mode = "a" if self.ignore_path.exists() else "w"
            with open(self.ignore_path, mode, encoding="utf-8") as f:
                for line in to_append:
                    f.write(f"{line}\n")
            logger.info(f"Scaffolded new exclusion directories to {self.ignore_path}: {to_append}")

    def get_compiled_spec(self, runtime_patterns: list[str]) -> pathspec.PathSpec:
        """
        Loads .specweaverignore and joins it with the dynamic polyglot runtime patterns.

        Args:
            runtime_patterns: Binary exclusion patterns dynamically supplied from CodeStructureInterfaces.

        Returns:
            A pathspec.PathSpec compiled tree capable of very fast exclusion matching.
        """
        lines: list[str] = []

        # 1. Add the dynamic interface patterns first
        for p in runtime_patterns:
            if p not in lines:
                lines.append(p)

        # 2. Add the physical user override patterns last
        if self.ignore_path.exists() and self.ignore_path.is_file():
            for line in self.ignore_path.read_text(encoding="utf-8").splitlines():
                if line not in lines:
                    lines.append(line)

        # We use gitignore which is standard for .gitignore-like regex specs
        return pathspec.PathSpec.from_lines("gitignore", lines)
