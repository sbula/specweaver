# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.core.config.archetype_resolver import ArchetypeResolver


def test_archetype_resolver_finds_nearest_context(tmp_path: Path) -> None:
    # Arrange
    project_root = tmp_path

    # Root level context without archetype
    root_context = project_root / "context.yaml"
    root_context.write_text("operational:\n  dal_level: D1")

    # Sub-directory with archetype
    api_dir = project_root / "src" / "api"
    api_dir.mkdir(parents=True)
    api_context = api_dir / "context.yaml"
    api_context.write_text("archetype: spring-boot")

    # Deep directory
    deep_dir = api_dir / "controllers" / "users"
    deep_dir.mkdir(parents=True)

    resolver = ArchetypeResolver(project_root)

    # Act & Assert
    assert resolver.resolve(deep_dir) == "spring-boot"
    assert resolver.resolve(api_dir) == "spring-boot"
    assert resolver.resolve(project_root) is None


def test_archetype_resolver_handles_empty_file(tmp_path: Path) -> None:
    project_root = tmp_path
    context = project_root / "context.yaml"
    context.touch()

    resolver = ArchetypeResolver(project_root)
    assert resolver.resolve(project_root) is None


def test_archetype_resolver_handles_malformed_yaml(tmp_path: Path) -> None:
    project_root = tmp_path
    context = project_root / "context.yaml"
    context.write_text("this is not: valid: yaml: : :")

    resolver = ArchetypeResolver(project_root)
    assert resolver.resolve(project_root) is None
