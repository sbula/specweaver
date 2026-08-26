# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Finding the description attached to a declaration, and reading it plainly.

**Free functions, not methods**, for the same reason the visibility rules are: the answer is a
function of one AST node. Making them methods gave `check_class_health` a new LCOM4 component in
four parsers, and the metric was right — the rule is a separate concern.

**Attachment is a position AND a line gap.** `prev_sibling` alone is not enough: measured
2026-08-26, a Go comment three blank lines above a function is still its previous sibling. Without
the gap check, every file's licence header becomes the description of its first declaration, and
every test about a *present* description still passes. godoc, rustdoc and javadoc all require
immediate adjacency; this is their rule, not an invented threshold.
"""

from __future__ import annotations

import typing

#: Stripped from the front of a line, repeatedly, longest first so `/**` never leaves a stray `*`.
_LEADING_MARKERS = ("///", "//!", "//", "/**", "/*", "#")


def _clean_line(line: str) -> str:
    """One comment line with its markers removed and its content untouched.

    Order matters and is not arbitrary: the trailing `*/` goes **before** the leading `*`, or a
    line that is only `*/` would be read as a continuation star and leave a bare `/`.
    """
    text = line.strip()
    changed = True
    while changed:
        changed = False
        for marker in _LEADING_MARKERS:
            if text.startswith(marker):
                text = text[len(marker) :].lstrip()
                changed = True
                break
    if text.endswith("*/"):
        text = text[:-2].rstrip()
    if text.startswith("*"):
        text = text[1:].lstrip()
    return text


def strip_markers(raw: str) -> str:
    """A comment's text, without the punctuation that says it is a comment.

    Only **leading** markers go. A description reading `Multiply a*b, then a/b.` keeps both
    characters — a greedy strip eats content, and the damage is invisible unless something looks
    for it.
    """
    return "\n".join(_clean_line(line) for line in raw.splitlines()).strip()


def _anchor(name_node: typing.Any) -> typing.Any | None:
    """The node a doc comment would sit above: the outermost ancestor starting on the same row.

    A declaration is wrapped differently in every grammar, and the wrapper is what the comment
    precedes. Measured 2026-08-26, for the SAME claim "the doc above this type":

    | | inner node | wrapper the comment precedes |
    |---|---|---|
    | TypeScript | `class_declaration` | `export_statement` |
    | Go | `type_spec` | `type_declaration` |
    | C, C++ | `struct_specifier` | *(none — it is already outermost)* |

    A fixed per-language depth cannot express that: C needs one extra level for a **function**
    (`function_declarator` inside `function_definition`) and none for a **struct**. The wrapper
    always opens on the same row as what it wraps, so climbing while that holds finds it in every
    case and stops before reaching the file.

    This replaced a `_DOC_DEPTH` class attribute, which passed every method-level test in this file
    and failed four of the five type-level ones the moment they were written.
    """
    node = name_node.parent if name_node is not None else None
    if node is None:
        return None
    while node.parent is not None and node.parent.start_point[0] == node.start_point[0]:
        node = node.parent
    return node


def _last_content_row(node: typing.Any, raw: str) -> int:
    """The row this comment's text actually ends on.

    Not simply `end_point[0]`: grammars disagree about whether a line comment owns its trailing
    newline. Rust's `line_comment` does, so its `end_point` already sits on the following row,
    while Go's and Java's do not. Measured 2026-08-26 — a Rust doc comment on row 2 reports
    `end_point=(3, 0)` for a declaration starting on row 3.

    Normalising here keeps the adjacency rule a single strict statement: the comment ends on the
    row immediately above the declaration. Allowing a gap of "0 or 1" instead would have hidden
    the grammar difference behind a looser rule that also admits a trailing inline comment.
    """
    row = int(node.end_point[0])
    return row - 1 if raw.endswith("\n") else row


def sibling_doc(name_node: typing.Any) -> str:
    """The description written immediately above this declaration, or `""`.

    Consecutive comment siblings are collected, because `///` and `//` doc blocks arrive as one
    node per line — taking only the nearest would return a doc block's last line and give no sign
    the rest was dropped.
    """
    anchor = _anchor(name_node)
    if anchor is None:
        return ""

    collected: list[str] = []
    below = anchor
    sibling = anchor.prev_sibling
    while sibling is not None and "comment" in sibling.type:
        raw = typing.cast("bytes", sibling.text or b"").decode("utf-8")
        if _last_content_row(sibling, raw) + 1 != below.start_point[0]:
            break  # a blank line between them: a note about something else, not a description
        # `rstrip` for the same grammar difference `_last_content_row` normalises: a Rust
        # `line_comment` owns its trailing newline, so joining two of them would insert a
        # blank line the source never had. Newlines INSIDE a block comment are kept.
        collected.append(raw.rstrip("\n"))
        below = sibling
        sibling = sibling.prev_sibling

    return strip_markers("\n".join(reversed(collected)))


def docstring_doc(name_node: typing.Any) -> str:
    """Python's description, which is not a comment at all.

    A docstring is the first statement **inside** the body, so no walk above the declaration ever
    finds it. Python is the one language whose description is not a comment at all.
    """
    declaration = name_node.parent if name_node is not None else None
    if declaration is None:
        return ""
    body = next((c for c in declaration.children if c.type == "block"), None)
    if body is None or not body.children:
        return ""
    first = body.children[0]
    if first.type != "expression_statement" or not first.children:
        return ""
    literal = first.children[0]
    if literal.type != "string":
        return ""
    text = typing.cast("bytes", literal.text or b"").decode("utf-8")
    for quote in ('"""', "'''", '"', "'"):
        if text.startswith(quote) and text.endswith(quote) and len(text) >= 2 * len(quote):
            return text[len(quote) : -len(quote)].strip()
    return text.strip()
