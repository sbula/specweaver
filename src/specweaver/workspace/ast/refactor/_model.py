# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a rename plan holds: spots, the plan, a refusal."""

from __future__ import annotations

from dataclasses import dataclass, field

#: A refusal or a report names at most this many spots, then counts the rest.
MAX_SPOTS = 50


@dataclass(frozen=True, order=True)
class Spot:
    """A line in a file."""

    path: str
    line: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class RenamePlan:
    """The new content of every file the rename changes, and the text mentions it left alone."""

    changes: dict[str, str]
    mentions: list[Spot] = field(default_factory=list)


@dataclass
class RenameRefusal:
    """Why nothing may change, and the spots that say so."""

    reason: str
    spots: list[Spot] = field(default_factory=list)


@dataclass
class Found:
    """What a language's resolver found: spans to rename, unsure spots, text mentions."""

    old: str
    proven: dict[str, list[tuple[int, int]]]
    unsure: list[Spot]
    mentions: list[Spot]


def listing(spots: list[Spot], cap: int = MAX_SPOTS) -> str:
    """The spots as `path:line`, at most `cap` of them, then the count of the rest."""
    shown = ", ".join(str(s) for s in spots[:cap])
    rest = len(spots) - cap
    return f"{shown} … +{rest} more" if rest > 0 else shown
