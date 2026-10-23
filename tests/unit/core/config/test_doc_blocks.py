# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A generated block: its body is replaced, and nothing outside it changes.

Proves: C-EXEC-08 FR-3

| Bucket | Case |
|---|---|
| Happy | the body between the markers is replaced; the rest stays byte for byte |
| Boundary | an empty output is an empty body; CRLF line endings stay; two texts differing only inside the block are equal outside it |
| Degradation | markers missing, doubled, or end before start: refused, naming both markers; a text without markers comes back whole from `outside_blocks` |
| Hostile | an output holding the block's own marker is refused; two blocks for one step, or one block twice, refused naming the line |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.doc_policy import fill_block, outside_blocks, parse_doc_policy
from specweaver.core.config.settings_file import SettingsFileError

_START = "<!-- sw:block counts -->"
_END = "<!-- sw:end counts -->"
_README = f"# Title\n\nBefore.\n{_START}\nold 1\nold 2\n{_END}\nAfter.\n"


def test_the_body_is_replaced_and_the_rest_kept() -> None:
    filled = fill_block(_README, "counts", "10,832 tests\n")

    assert filled == f"# Title\n\nBefore.\n{_START}\n10,832 tests\n{_END}\nAfter.\n"


def test_an_empty_output_is_an_empty_body() -> None:
    assert fill_block(_README, "counts", "") == f"# Title\n\nBefore.\n{_START}\n{_END}\nAfter.\n"


def test_crlf_line_endings_stay() -> None:
    text = f"a\r\n{_START}\r\nold\r\n{_END}\r\nb\r\n"

    assert fill_block(text, "counts", "new\n") == f"a\r\n{_START}\r\nnew\r\n{_END}\r\nb\r\n"


@pytest.mark.parametrize(
    "text",
    [
        "# no markers\n",
        f"{_START}\nonly a start\n",
        f"{_START}\n{_END}\n{_START}\n{_END}\n",
        f"{_END}\nwrong order\n{_START}\n",
    ],
)
def test_wrong_markers_are_refused_naming_both(text: str) -> None:
    with pytest.raises(ValueError, match="sw:block counts") as caught:
        fill_block(text, "counts", "x\n")

    assert "sw:end counts" in str(caught.value)


@pytest.mark.parametrize("output", [f"x\n{_END}\nescaped\n", f"{_START}\n"])
def test_an_output_holding_a_marker_is_refused(output: str) -> None:
    with pytest.raises(ValueError, match="marker"):
        fill_block(_README, "counts", output)


def test_a_change_inside_the_block_is_not_outside_it() -> None:
    assert outside_blocks(_README, ["counts"]) == outside_blocks(
        fill_block(_README, "counts", "new\n"), ["counts"]
    )


def test_a_change_outside_the_block_is() -> None:
    edited = _README.replace("Before.", "Changed.")

    assert outside_blocks(_README, ["counts"]) != outside_blocks(edited, ["counts"])


def test_a_text_without_markers_comes_back_whole() -> None:
    assert outside_blocks("plain\n", ["counts"]) == "plain\n"


_TWO = """\
[[docs.block]]
file = "README.md"
name = "counts"
step = "update_counts"

[[docs.block]]
file = "{file}"
name = "{name}"
step = "{step}"
"""


@pytest.mark.parametrize(
    ("file", "name", "step", "key", "line"),
    [
        ("docs/x.md", "other", "update_counts", "docs.block.1.step", 9),
        ("README.md", "counts", "another_step", "docs.block.1.name", 8),
    ],
)
def test_a_second_block_for_one_step_or_one_place_is_refused(
    file: str, name: str, step: str, key: str, line: int
) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_doc_policy(_TWO.format(file=file, name=name, step=step), "specweaver.toml")

    assert (caught.value.key, caught.value.line) == (key, line)
