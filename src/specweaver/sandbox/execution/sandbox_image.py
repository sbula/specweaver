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

from specweaver.commons.prepare_plan import detect_toolchain
from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_SUPPORTED_TAGS: tuple[str, ...] = ("3.11", "3.12", "3.13")
_DEFAULT_TAG = "3.13"

#: An image per toolchain, because `cargo` is not in the Python sandbox image and no amount of
#: preparing puts it there. Public upstream images for the others: building one polyglot image would
#: pull every toolchain for every project, and the executor already picks per project.
_TOOLCHAIN_IMAGES = {
    "cargo": "docker.io/library/rust:1-slim",
    "maven": "docker.io/library/maven:3-eclipse-temurin-21",
}

#: SpecWeaver's own sandbox image: built on the machine from the shipped recipe, never pulled.
_DEFAULT_IMAGE_REPO = "localhost/specweaver-sandbox-python"
#: The recipe it is built from, shipped inside the package so any install can build it.
_RECIPE = Path(__file__).with_name("Containerfile.sandbox")


def own_image(version: str, recipe: bytes | None = None) -> str:
    """The image for a Python version; its tag carries the recipe, so a changed recipe rebuilds."""
    content = _RECIPE.read_bytes() if recipe is None else recipe
    return f"{_DEFAULT_IMAGE_REPO}:{version}-{hashlib.sha256(content).hexdigest()[:12]}"


# NFR-5 / AD-4: reuse BashActionAtom's resource-limit defaults verbatim (2 GiB / 128 procs)
# rather than inventing a second limits schema for the same underlying concern.

_ENGINES: tuple[str, ...] = ("podman", "docker")  # AD-6: podman preferred, docker fallback


def _resolve_image(source_root: Path) -> str:
    """The image for this project's toolchain.

    Python keeps its own sandbox image and its `requires-python` tag selection. Every other toolchain
    takes an upstream image that carries it, because the Python image contains no `cargo` and no JDK.
    """
    toolchain = detect_toolchain(source_root)
    if toolchain in _TOOLCHAIN_IMAGES:
        return _TOOLCHAIN_IMAGES[toolchain]
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
        f"PY_VERSION={version}",
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
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[str], bool] | None = None,
    ensure: Callable[[str, str, Callable[[list[str]], int]], bool] = ensure_sandbox_image,
) -> bool:
    """Whether tests of this project can run in a container: a live engine and the image it needs."""
    answers = probe or _engine_answers
    for name in _ENGINES:
        engine = which(name)
        if engine and answers(engine):
            return ensure(_resolve_image(project_root), engine, _on_host(project_root))
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
