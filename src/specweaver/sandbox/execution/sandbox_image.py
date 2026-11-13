# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which image a container run uses, and getting SpecWeaver's own one onto the machine.

SpecWeaver's Python sandbox image is built here from the shipped `Containerfile.sandbox` the first
time it is needed; no registry carries it. Upstream images for other toolchains are
left to the engine to pull.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_SUPPORTED_TAGS: tuple[str, ...] = ("3.11", "3.12", "3.13")
_DEFAULT_TAG = "3.13"

#: An image per toolchain, because `cargo` is not in the Python sandbox image and no amount of
#: preparing puts it there. Public upstream images for the others: building one polyglot image would
#: pull every toolchain for every project, and the executor already picks per project.
#: Every image is pinned by tag and multi-arch index digest, so it changes only in a commit that
#: means to change it; how to update one: `docs/dev_guides/subprocess_execution.md`.
TOOLCHAIN_IMAGES = {
    "cargo": "docker.io/library/rust:1.100.0-slim@sha256:cc9edbcadf2c27013a642b1d1bb7504e26b1142d6b5ebe58f64cf2eb2bc128ae",
    "maven": "docker.io/library/maven:3.10.0-eclipse-temurin-21@sha256:851ccd76d49d5646915645e5fb51e9b00ef53ad3dc68b0e9a2a9846b9c56bde3",
}

#: The base each Python version's sandbox image is built from, passed to the recipe as `PY_BASE`.
PYTHON_BASES = {
    "3.11": "docker.io/library/python:3.11.18-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535",
    "3.12": "docker.io/library/python:3.12.16-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b",
    "3.13": "docker.io/library/python:3.13.18-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90",
}

#: SpecWeaver's own sandbox image: built on the machine from the shipped recipe, never pulled.
_DEFAULT_IMAGE_REPO = "localhost/specweaver-sandbox-python"
#: The recipe it is built from, shipped inside the package so any install can build it.
_RECIPE = Path(__file__).with_name("Containerfile.sandbox")


def own_image(version: str, recipe: bytes | None = None) -> str:
    """The image for a Python version; its tag carries the recipe and the base, so a change to
    either rebuilds."""
    content = (_RECIPE.read_bytes() if recipe is None else recipe) + PYTHON_BASES[version].encode()
    return f"{_DEFAULT_IMAGE_REPO}:{version}-{hashlib.sha256(content).hexdigest()[:12]}"


# NFR-5 / AD-4: reuse BashActionAtom's resource-limit defaults verbatim (2 GiB / 128 procs)
# rather than inventing a second limits schema for the same underlying concern.

_ENGINES: tuple[str, ...] = ("podman", "docker")  # AD-6: podman preferred, docker fallback


def _resolve_image(source_root: Path, build_tool: str) -> str:
    """The image for the run's build tool.

    Python keeps its own sandbox image and its `requires-python` tag selection. Every other toolchain
    takes an upstream image that carries it, because the Python image contains no `cargo` and no JDK.
    """
    if build_tool in TOOLCHAIN_IMAGES:
        return TOOLCHAIN_IMAGES[build_tool]
    version = _DEFAULT_TAG
    pyproject = source_root / "pyproject.toml"
    if pyproject.exists():
        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            requires_python = data.get("project", {}).get("requires-python", "")
            match = re.search(r"3\.(\d+)", requires_python)
            if match:
                minor = int(match.group(1))
                candidate = f"3.{minor}"
                if candidate in _SUPPORTED_TAGS:
                    version = candidate
                elif minor < 11:
                    version = _SUPPORTED_TAGS[0]
                else:
                    version = _DEFAULT_TAG
        except (OSError, tomllib.TOMLDecodeError, AttributeError, TypeError):
            logger.debug(
                "ContainerSubprocessExecutor: could not parse %s for requires-python", pyproject
            )
    return own_image(version)


def ensure_sandbox_image(image: str, engine: str, run: Callable[[list[str]], int]) -> bool:
    """Whether `image` is ready: SpecWeaver's own image is built here when missing.

    No registry carries it, so the first run on a machine builds it from the shipped recipe. An
    upstream image (Rust, Maven) is left to the engine to pull.
    """
    if not image.startswith(f"{_DEFAULT_IMAGE_REPO}:"):
        return True
    exists = (
        [engine, "image", "exists", image]
        if "podman" in engine
        else [engine, "image", "inspect", image]
    )
    if run(exists) == 0:
        return True
    version = image.rsplit(":", 1)[1].split("-", 1)[0]
    logger.info("Building the sandbox image %s from %s (first use on this machine)", image, _RECIPE)
    build = [
        engine,
        "build",
        "-f",
        str(_RECIPE),
        "-t",
        image,
        "--build-arg",
        f"PY_BASE={PYTHON_BASES[version]}",
        str(_RECIPE.parent),
    ]
    return run(build) == 0


def container_available(
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[str], bool] | None = None,
) -> bool:
    """Whether a live container engine answers here; probed each call, never cached."""
    answers = probe or _engine_answers
    return any((path := which(name)) and answers(path) for name in _ENGINES)


def sandbox_ready(
    project_root: Path,
    build_tool: str,
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[str], bool] | None = None,
    ensure: Callable[[str, str, Callable[[list[str]], int]], bool] = ensure_sandbox_image,
) -> bool:
    """Whether tests of this project can run in a container: a live engine and the image it needs."""
    answers = probe or _engine_answers
    for name in _ENGINES:
        engine = which(name)
        if engine and answers(engine):
            return ensure(_resolve_image(project_root, build_tool), engine, _on_host(project_root))
    return False


def _on_host(project_root: Path) -> Callable[[list[str]], int]:
    """An engine command run on the host, for its exit code; an image build may take minutes."""
    host = SubprocessExecutor(cwd=project_root)
    return lambda argv: host.execute(argv, timeout_seconds=1800).exit_code


def _engine_answers(engine: str) -> bool:
    return (
        SubprocessExecutor(cwd=Path.cwd()).execute([engine, "info"], timeout_seconds=5).exit_code
        == 0
    )
