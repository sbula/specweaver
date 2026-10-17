# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""DependencyHasher — Merkle-tree hashing for cache state.

Replaces shallow file hashing with "Dependency Hashing". Uses the LanguageAnalyzer
components to deeply extract imports, generating a robust structural signature.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from specweaver.commons import json

if TYPE_CHECKING:
    from specweaver.workspace.context.analyzer_protocols import AnalyzerFactoryProtocol
logger = logging.getLogger(__name__)


def _ensure_gitignore(project_root: Path) -> None:
    """Ignore the topology cache in the repository's `.gitignore`, and nothing else.

    `.specweaver/` also holds the project's scripts, pipelines and evaluators, which belong in git;
    only `topology.cache.json` is machine state. The line is relative to the git root, so a project
    in a subfolder of the repository ignores its own cache.
    """
    root = project_root.resolve()
    git_home = next((d for d in (root, *root.parents) if (d / ".git").is_dir()), None)
    if git_home is None:
        logger.debug("Failed to locate .git repository root. Skipping gitignore enforcement.")
        return

    cache = (root / ".specweaver" / "topology.cache.json").relative_to(git_home).as_posix()
    entry = f"/{cache}"
    gitignore_path = git_home / ".gitignore"
    try:
        contents = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        if entry in contents.splitlines():
            return
        separator = "\n" if contents and not contents.endswith("\n") else ""
        with gitignore_path.open("a", encoding="utf-8") as f:
            f.write(f"{separator}{entry}\n")
        logger.info("Added %s to %s", entry, gitignore_path)
    except Exception as e:
        logger.warning("Failed to ensure the topology cache is ignored by Git: %s", e)


def _relative_to(path: Path, base: Path) -> str:
    """`path` relative to `base` as posix, or its absolute posix form when it is outside."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


class DependencyHasher:
    """Computes semantic merkle-tree hashes for topology boundaries."""

    def __init__(self, project_root: Path, analyzer_factory: AnalyzerFactoryProtocol):
        self.project_root = project_root.resolve()
        self.cache_dir = self.project_root / ".specweaver"
        self.cache_path = self.cache_dir / "topology.cache.json"
        self.analyzer_factory = analyzer_factory

    @staticmethod
    def _hash_file(filepath: Path) -> str:
        """Compute SHA-256 for a single file."""
        hasher = hashlib.sha256()
        try:
            with filepath.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as e:
            logger.debug("DependencyHasher failed to read %s: %s", filepath, e)
            return ""

    def _ignore_rules(self) -> tuple[set[str], Any]:
        """`(directory names to skip, pathspec or None)` assembled from every analyzer.

        Each analyzer contributes its language's build/vendor directories and binary globs;
        `.specweaverignore` appends project-specific ones. `pathspec` is optional at runtime, and
        a missing one degrades to "match nothing" with a warning rather than failing the hash.
        """
        skip_dirs = {".git"}
        binary_patterns: list[str] = []
        for analyzer in self.analyzer_factory.get_all_analyzers():
            for ign in analyzer.get_default_directory_ignores():
                skip_dirs.add(ign.rstrip("/"))
            binary_patterns.extend(analyzer.get_binary_ignore_patterns())

        ignore_file = self.project_root / ".specweaverignore"
        if ignore_file.is_file():
            binary_patterns.extend(ignore_file.read_text(encoding="utf-8").splitlines())

        if not binary_patterns:
            return skip_dirs, None
        try:
            import pathspec
        except ImportError:
            logger.warning("pathspec not installed; ignoring binary and .specweaverignore patterns")
            return skip_dirs, None
        return skip_dirs, pathspec.PathSpec.from_lines("gitignore", binary_patterns)

    def _is_hashable(self, filepath: Path, name: str, spec: Any) -> bool:
        """Whether this file contributes to the boundary's semantic hash.

        Symlinks are excluded deliberately: hashing a link's target would make the boundary's
        identity depend on something outside it.
        """
        if name.startswith("."):
            return False
        if filepath.is_symlink() or not filepath.is_file():
            return False
        return not (spec and spec.match_file(_relative_to(filepath, self.project_root)))

    def _hash_directory(self, directory: Path) -> dict[str, str]:
        """Compute the semantic hash payload for a specific boundary directory."""
        import os

        skip_dirs, spec = self._ignore_rules()

        file_hashes = {}
        for root, dirs, files in os.walk(directory):
            # In-place: os.walk reads this list back to decide where to descend.
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            root_path = Path(root)
            for f in files:
                filepath = root_path / f
                if not self._is_hashable(filepath, f, spec):
                    continue
                h = self._hash_file(filepath)
                if h:
                    file_hashes[_relative_to(filepath, directory)] = h

        local_analyzer = self.analyzer_factory.for_directory(directory)
        dependencies = local_analyzer.extract_imports(directory) if local_analyzer else []

        payload = {"files": file_hashes, "dependencies": sorted(dependencies)}

        rendered = json.dumps(payload, sort_keys=True)
        merkle_root = hashlib.sha256(rendered.encode("utf-8")).hexdigest()

        return {"merkle_root": merkle_root, "rendered_payload": rendered}

    def load_cache(self) -> dict[str, dict[str, str]]:
        """Read the existing semantic cache from disk."""
        if not self.cache_path.exists():
            return {}
        try:
            raw = self.cache_path.read_text(encoding="utf-8")
            return cast("dict[str, dict[str, str]]", json.loads(raw))
        except Exception as e:
            logger.warning("Failed to load semantic cache %s: %s", self.cache_path, e)
            return {}

    def save_cache(self, cache_state: dict[str, dict[str, str]] | None = None) -> None:
        """Write the active semantic state securely to disk."""
        if cache_state is None:
            manifests = list(self.project_root.rglob("context.yaml"))
            cache_state = self.compute_hashes(manifests)

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            _ensure_gitignore(self.project_root)
            payload = json.dumps(cache_state, sort_keys=True)
            self.cache_path.write_text(payload, encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to persist topology cache: %s", e)

    def compute_hashes(self, manifests: list[Path]) -> dict[str, dict[str, str]]:
        """Compute semantic hashes across all active manifests and prune orphans.

        Loads active cache, processes each context.yaml boundary, drops deleted bounds,
        and returns the consolidated Merkle state.
        """
        # Used for structural diffing eventually: active_cache = self.load_cache()
        new_state = {}

        for manifest in manifests:
            directory = manifest.parent
            # Convert physical path to string key for JSON compatibility
            bound_key = directory.relative_to(self.project_root).as_posix()

            # Recalculating hash (In a true incremental crawl, we'd check mtime first,
            # but compute logic runs here)
            new_state[bound_key] = self._hash_directory(directory)

        return new_state
