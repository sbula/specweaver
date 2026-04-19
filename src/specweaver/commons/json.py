# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Drop-in replacement for the standard library `json` module, powered by `orjson`.

This module acts as a facade. It mimics standard `json` interfaces (`dumps`, `loads`)
while seamlessly executing `orjson` bindings under the hood to completely preserve
legacy string types without causing TypeError byte desyncs across the LLM and API paths.
"""

from __future__ import annotations

from typing import Any

import orjson

# Re-expose the decode error for try/except blocks natively
JSONDecodeError = orjson.JSONDecodeError


def dumps(obj: Any, **kwargs: Any) -> str:
    """Serialize obj to a JSON formatted str utilizing orjson.

    Automatically decodes the raw bytes returned by `orjson` back into standard
    string format to prevent breaking Pydantic models or standard loggers.
    """
    option = 0

    if kwargs.get("indent"):
        option |= orjson.OPT_INDENT_2
    if kwargs.get("sort_keys"):
        option |= orjson.OPT_SORT_KEYS

    default = kwargs.get("default")

    return orjson.dumps(obj, option=option, default=default).decode("utf-8")


def loads(s: str | bytes, **kwargs: Any) -> Any:
    """Deserialize s to a Python object utilizing orjson."""
    return orjson.loads(s)


def dump(obj: Any, fp: Any, **kwargs: Any) -> None:
    """Serialize obj and write to file pointer utilizing orjson."""
    fp.write(dumps(obj, **kwargs))


def load(fp: Any, **kwargs: Any) -> Any:
    """Deserialize file pointer utilizing orjson."""
    return loads(fp.read())
