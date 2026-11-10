# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`conforms` gives a runtime protocol the same answer on every Python version.

Python 3.11 checks `isinstance` against a runtime protocol with `hasattr`, so a `MagicMock`, which
answers any attribute, passes it there; 3.12 and later look the members up statically and refuse it.

| Bucket | Case |
|---|---|
| Happy | a class with the methods, a frozen dataclass with the fields, an object with properties |
| Boundary | a member set on the instance counts; a member inherited from a base class counts; a field-only protocol is checked; a `MagicMock(spec=…)` of a conforming class conforms, as `isinstance` says |
| Degradation | — a pure check: no file, no service |
| Hostile | a bare `MagicMock`, `None`, an object missing one member or field, and a method set to `None` are refused |
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

import pytest

from specweaver.commons.protocols import conforms


@runtime_checkable
class _Speaks(Protocol):
    def speak(self) -> str: ...

    def listen(self) -> str: ...


@runtime_checkable
class _Named(Protocol):
    @property
    def name(self) -> str: ...


@runtime_checkable
class _Labelled(Protocol):
    label: str


class _Speaker:
    def speak(self) -> str:
        return "a"

    def listen(self) -> str:
        return "b"


class _Child(_Speaker):
    pass


@dataclass(frozen=True)
class _Record:
    name: str


class _WithProperty:
    @property
    def name(self) -> str:
        return "p"


class _HalfSpeaker:
    def speak(self) -> str:
        return "a"


class _MuteSpeaker(_Speaker):
    listen = None  # type: ignore[assignment]


@pytest.mark.parametrize(
    ("obj", "protocol"),
    [
        (_Speaker(), _Speaks),
        (_Child(), _Speaks),
        (_Record("r"), _Named),
        (_WithProperty(), _Named),
        (SimpleNamespace(name="n"), _Named),
        (SimpleNamespace(label="l"), _Labelled),
        (MagicMock(spec=_Speaker), _Speaks),
    ],
)
def test_a_conforming_object_conforms(obj: object, protocol: type) -> None:
    assert conforms(obj, protocol)


@pytest.mark.parametrize(
    ("obj", "protocol"),
    [
        (MagicMock(), _Speaks),
        (MagicMock(), _Named),
        (None, _Speaks),
        (_HalfSpeaker(), _Speaks),
        (_MuteSpeaker(), _Speaks),
        (SimpleNamespace(), _Labelled),
    ],
)
def test_anything_else_does_not(obj: object, protocol: type) -> None:
    assert not conforms(obj, protocol)
