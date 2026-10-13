# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A function's body as a tool reads and writes it: the code inside the block, at column 0.

Reading and writing use the same span and the same indentation, so an unchanged body writes back
byte for byte and a one-line edit changes one line. A brace block's span is inside its braces; an
indented suite's span starts at the beginning of its first line.
"""

from __future__ import annotations

import os
import textwrap
import typing


def body_span(code_bytes: bytes, block: typing.Any) -> tuple[int, int]:
    """The byte span of the body inside `block`."""
    opens = [c for c in block.children if c.type == "{"]
    closes = [c for c in block.children if c.type == "}"]
    if opens and closes:
        return typing.cast("int", opens[0].end_byte), typing.cast("int", closes[-1].start_byte)
    start = typing.cast("int", block.start_byte)
    end = typing.cast("int", block.end_byte)
    line_start = code_bytes.rfind(b"\n", 0, start) + 1
    if not code_bytes[line_start:start].strip():
        return line_start, end
    return start, end


def read_body(code_bytes: bytes, span: tuple[int, int]) -> str:
    """The body's code, dedented to column 0, without leading or trailing blank lines."""
    return textwrap.dedent(code_bytes[span[0] : span[1]].decode("utf-8")).strip("\n").rstrip()


def write_body(code_bytes: bytes, span: tuple[int, int], new_code: str, margin: int) -> bytes:
    """`code_bytes` with the body at `span` replaced by `new_code`, at the body's indentation."""
    original = code_bytes[span[0] : span[1]].decode("utf-8")
    new = textwrap.dedent(new_code).strip("\n").rstrip()
    lead = original[: len(original) - len(original.lstrip(" \t\n"))]
    tail = original[len(original.rstrip(" \t\n")) :]
    if "\n" not in original and "\n" not in new:
        return code_bytes[: span[0]] + (lead + new + tail).encode("utf-8") + code_bytes[span[1] :]
    indent = _indent_of(original) if "\n" in original else " " * (margin + 4)
    head = lead[: lead.rfind("\n") + 1] if "\n" in original else "\n"
    if "\n" not in original:
        tail = "\n" + " " * margin if original != original.lstrip() or tail else ""
    lines = "\n".join(indent + line if line.strip() else "" for line in new.split("\n"))
    return code_bytes[: span[0]] + (head + lines + tail).encode("utf-8") + code_bytes[span[1] :]


def _indent_of(text: str) -> str:
    """The whitespace every non-blank line of `text` starts with."""
    margins = [line[: len(line) - len(line.lstrip())] for line in text.split("\n") if line.strip()]
    return os.path.commonprefix(margins) if margins else ""
