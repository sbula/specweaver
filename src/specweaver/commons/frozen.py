# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Values that cannot change at any depth: a read-only mapping, tuples and frozensets.

A value shared by every step of a run must not be changed by one of them.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any

_SCALARS = (str, bytes, int, float, bool, type(None), date)


class FrozenMap(Mapping[str, Any]):
    """A read-only mapping whose values are frozen when it is built.

    Nothing inside can change, so a copy would be the same value: `copy` and `deepcopy` return it.
    """

    __slots__ = ("_items",)

    def __init__(self, items: Mapping[str, Any]) -> None:
        self._items = {key: freeze(value) for key, value in items.items()}

    def __getitem__(self, key: str) -> Any:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"FrozenMap({self._items!r})"

    def __copy__(self) -> FrozenMap:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> FrozenMap:
        return self


def freeze(value: Any) -> Any:
    """`value` with every dict, list, tuple and set in it frozen; any other mutable type is refused."""
    if isinstance(value, (FrozenMap, frozenset, *_SCALARS)):
        return value
    if isinstance(value, Mapping):
        return FrozenMap(value)
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze(item) for item in value)
    raise TypeError(f"cannot freeze a {type(value).__name__}: it may change after loading")
