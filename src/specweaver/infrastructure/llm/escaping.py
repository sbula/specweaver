# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Utilities for sanitizing untrusted inputs against prompt/XML injections."""

from __future__ import annotations

import json
import xml.sax.saxutils
from enum import StrEnum


class EscapingStrategy(StrEnum):
    """Supported input escaping strategies to prevent tag breakouts in prompts."""

    RAW = "raw"
    XML = "xml"
    CDATA = "cdata"
    JSON = "json"


def escape_xml_text(text: str) -> str:
    """Escape XML special characters in a text block context.

    Escapes &, <, and >.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got type: {type(text).__name__}")
    return xml.sax.saxutils.escape(text, {">": "&gt;"})


def escape_xml_attribute(value: str) -> str:
    """Escape XML special characters in an attribute context.

    Escapes &, <, >, double quotes ("), and single quotes (').
    """
    if not isinstance(value, str):
        raise TypeError(f"Expected str, got type: {type(value).__name__}")
    return xml.sax.saxutils.escape(value, {
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
    })


def escape_cdata(text: str) -> str:
    """Escape and wrap text in a CDATA block.

    Replaces any instances of the CDATA breakout sequence `]]>` with `]]]]><![CDATA[>`
    to ensure nested CDATA blocks cannot terminate the containing tag block.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got type: {type(text).__name__}")
    mitigated = text.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{mitigated}]]>"


def escape_json(text: str) -> str:
    """Serialize the raw text as a JSON string to prevent syntax breakouts."""
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got type: {type(text).__name__}")
    return json.dumps(text)


def apply_escaping(text: str, strategy: EscapingStrategy | str) -> str:
    """Apply the chosen escaping strategy to the input text."""
    try:
        strat = EscapingStrategy(strategy)
    except ValueError:
        raise ValueError(f"Unknown escaping strategy: {strategy}") from None

    if strat == EscapingStrategy.RAW:
        return text
    elif strat == EscapingStrategy.XML:
        return escape_xml_text(text)
    elif strat == EscapingStrategy.CDATA:
        return escape_cdata(text)
    elif strat == EscapingStrategy.JSON:
        return escape_json(text)
    else:
        raise ValueError(f"Unknown escaping strategy: {strat}")

