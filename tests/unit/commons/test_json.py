# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the `specweaver.commons.json` facade."""

from __future__ import annotations

import io

import pytest

from specweaver.commons import json


def test_dumps_returns_string() -> None:
    """Test that dumps natively decodes to UTF-8 string, unlike raw orjson."""
    data = {"key": "value", "count": 1}
    result = json.dumps(data)
    assert isinstance(result, str)
    assert result == '{"key":"value","count":1}'


def test_loads_parses_string_and_bytes() -> None:
    """Test loads handles both string and native orjson bytes."""
    data_dict = {"key": "value"}

    # Test string
    res1 = json.loads('{"key":"value"}')
    assert res1 == data_dict

    # Test bytes
    res2 = json.loads(b'{"key":"value"}')
    assert res2 == data_dict


def test_dumps_applies_indent() -> None:
    """Test that indent kwarg correctly bridges to OPT_INDENT_2."""
    data = {"a": 1, "b": 2}
    result = json.dumps(data, indent=4)
    # The orjson OPT_INDENT_2 enforces a constant 2-space layout, ignoring the '4' int value.
    assert result == '{\n  "a": 1,\n  "b": 2\n}'


def test_dumps_applies_sort_keys() -> None:
    """Test that sort_keys kwarg bridges to OPT_SORT_KEYS."""
    data = {"z": 1, "a": 2, "g": 3}
    result = json.dumps(data, sort_keys=True)
    # The output struct must be strictly alphabetized
    assert result == '{"a":2,"g":3,"z":1}'


def test_dumps_with_custom_default() -> None:
    """Test that the default kwarg operates correctly for unhandled types."""

    class Unserializable:
        def __init__(self, val: str) -> None:
            self.val = val

    obj = {"node": Unserializable("test")}

    # Without default hook, it should raise TypeError
    with pytest.raises(TypeError):
        json.dumps(obj)

    # With hook
    def _default(o: object) -> object:
        if isinstance(o, Unserializable):
            return o.val
        raise TypeError

    result = json.dumps(obj, default=_default)
    assert result == '{"node":"test"}'


def test_dump_and_load_file_pointers() -> None:
    """Test that dump and load work with strictly file-like string pointers."""
    buffer = io.StringIO()
    data = {"test": 42}

    json.dump(data, buffer)

    # Move pointer to start
    buffer.seek(0)

    loaded = json.load(buffer)
    assert loaded == data


def test_json_decode_error_bubbled() -> None:
    """Test that malformed JSON triggers the exposed JSONDecodeError."""
    with pytest.raises(json.JSONDecodeError):
        json.loads("{malformed:")
