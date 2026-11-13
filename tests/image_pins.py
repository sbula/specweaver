# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every container image this repo pulls, found by one scanner.

The format guard (`tests/unit/sandbox/execution/test_images_are_pinned.py`) and the index check
(`tests/integration/sandbox/execution/test_image_pins_are_multi_arch.py`) read this same list, so
an image one of them misses, the other misses too, and neither can drift from the other.

A reference is recognised by its registry host. Write every real image fully qualified, with
Docker Hub's host and `library/` in front of an official image's name: a short name is invisible here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Where an image can be named. Docs are history and stay out.
_SCANNED = ("src", "tests", ".github/workflows", "Containerfile")
#: `container.yml` publishes this one; it is an output, never pulled.
_OURS = ("ghcr.io/sbula/",)

_REF = re.compile(
    r"\b(?:docker\.io|ghcr\.io|quay\.io)/[a-z0-9][a-z0-9._/-]*"
    r"(?::[A-Za-z0-9._-]+)?(?:@sha256:[0-9a-f]{64})?"
)
#: Tag AND digest: the tag says which version a reader sees, the digest is what is pulled.
PINNED = re.compile(r"^[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$")
#: The `FROM` or `COPY --from=` target of a container recipe line.
_RECIPE_SOURCE = re.compile(r"^\s*(?:FROM\s+(?:--platform=\S+\s+)?|COPY\s+--from=)(\S+)", re.I)


def _files() -> list[Path]:
    found: list[Path] = []
    for name in _SCANNED:
        path = ROOT / name
        if path.is_dir():
            found.extend(p for p in path.rglob("*") if p.is_file())
        else:
            found.append(path)
    return [p for p in found if "__pycache__" not in p.parts]


def refs_in(text: str) -> list[str]:
    """Every registry reference in `text`, our own published image left out."""
    return [m.group(0) for m in _REF.finditer(text) if not m.group(0).startswith(_OURS)]


def recipe_sources(text: str) -> list[str]:
    """Every image a container recipe builds from, stage names and `${ARG}`s left out."""
    stages = {m.group(1).lower() for m in re.finditer(r"\bAS\s+(\S+)", text, re.I)}
    sources = [m.group(1) for line in text.splitlines() if (m := _RECIPE_SOURCE.match(line))]
    return [s for s in sources if s.lower() not in stages and not s.startswith("$")]


def image_refs() -> dict[str, list[str]]:
    """`reference -> the files that name it`, over the whole scanned tree."""
    found: dict[str, list[str]] = {}
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        refs = refs_in(text)
        if path.name.startswith("Containerfile"):
            refs += recipe_sources(text)
        for ref in refs:
            found.setdefault(ref, []).append(path.relative_to(ROOT).as_posix())
    return found
