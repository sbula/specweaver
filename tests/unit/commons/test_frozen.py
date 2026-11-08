# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`freeze` makes a value that cannot change at any depth, and copies of it are the value itself.

Proves: TECH-088 FR-14

| Bucket | Case |
|---|---|
| Happy | a dict becomes a read-only mapping, a list a tuple, a set a frozenset, all the way down; scalars stay |
| Boundary | empty containers; a value already frozen comes back as the same object; it compares equal to the plain dict it came from |
| Degradation | — `freeze` reads no file and calls no service; `copy` and `deepcopy` return the same object |
| Hostile | the caller changes the dict and its nested list after building, and the frozen value does not change; a write raises; a `bytearray` or an arbitrary object is refused at build time |
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from typing import Any

import pytest

from specweaver.commons.frozen import FrozenMap, freeze


def _config() -> dict[str, Any]:
    return {"s": {"command": ["python"], "args": ["server.py"], "env": {"K": "v"}}, "tags": {"a"}}


def test_every_container_is_frozen_all_the_way_down() -> None:
    frozen = freeze(_config())

    assert isinstance(frozen, FrozenMap)
    server = frozen["s"]
    assert isinstance(server, FrozenMap)
    assert server["command"] == ("python",)
    assert server["args"] == ("server.py",)
    assert isinstance(server["env"], FrozenMap)
    assert frozen["tags"] == frozenset({"a"})


@pytest.mark.parametrize(
    "scalar", ["s", b"b", 1, 1.5, True, None, date(2026, 1, 1), datetime(2026, 1, 1)]
)
def test_an_immutable_scalar_stays_as_it_is(scalar: object) -> None:
    assert freeze(scalar) is scalar


def test_a_list_holding_dicts_freezes_them_too() -> None:
    frozen = freeze([{"a": [1]}, ({"b": 2},)])

    assert frozen == (FrozenMap({"a": (1,)}), (FrozenMap({"b": 2}),))
    assert isinstance(frozen[0]["a"], tuple)


def test_empty_containers() -> None:
    assert freeze({}) == FrozenMap({})
    assert freeze([]) == ()
    assert freeze(set()) == frozenset()


def test_a_frozen_value_comes_back_as_itself() -> None:
    frozen = freeze(_config())

    assert freeze(frozen) is frozen


def test_it_equals_the_dict_it_came_from_once_lists_are_tuples() -> None:
    assert freeze({"a": "x", "b": {"c": 1}}) == {"a": "x", "b": {"c": 1}}
    assert dict(freeze({"a": "x"})) == {"a": "x"}


def test_copies_are_the_value_itself() -> None:
    frozen = freeze(_config())

    assert copy.copy(frozen) is frozen
    assert copy.deepcopy(frozen) is frozen
    assert copy.deepcopy({"held": frozen})["held"] is frozen


def test_the_callers_dict_and_list_cannot_reach_inside() -> None:
    config = _config()
    frozen = freeze(config)

    config["s"]["args"].append("--evil")
    config["s"]["env"]["K"] = "changed"
    config["new"] = 1

    assert frozen["s"]["args"] == ("server.py",)
    assert frozen["s"]["env"]["K"] == "v"
    assert "new" not in frozen


def test_the_mapping_constructor_freezes_too() -> None:
    nested = {"args": ["a"]}
    mapping = FrozenMap({"s": nested})

    nested["args"].append("b")

    assert mapping["s"]["args"] == ("a",)


def test_a_write_raises() -> None:
    frozen = freeze(_config())

    with pytest.raises(TypeError):
        frozen["s"] = {}
    with pytest.raises(TypeError):
        del frozen["s"]
    with pytest.raises(AttributeError):
        frozen["s"]["args"].append("x")


@pytest.mark.parametrize("leaf", [bytearray(b"x"), object(), [bytearray(b"x")]])
def test_a_mutable_leaf_is_refused_at_build_time(leaf: object) -> None:
    with pytest.raises(TypeError, match="cannot freeze"):
        freeze({"k": leaf})
