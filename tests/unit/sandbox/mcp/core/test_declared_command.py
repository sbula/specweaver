# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One reading of a server's `command` and `args`, for both MCP readers; it never writes the config.

Proves: TECH-088 FR-14

A string `command` is one word; a command with arguments is a list (the user, 2026-11-08). A
spaced string is refused with the list form named, never split, and never read as characters.

| Bucket | Case |
|---|---|
| Happy | `command: docker` plus `args`; a list `command`; tuples from a frozen config give a new list |
| Boundary | no `args`; empty `args`; the config is the same after the call |
| Degradation | a missing, empty or blank `command` is refused with the server's name |
| Hostile | `command: "python server.py"` is refused naming `use command: [python, server.py]`; a `str` or `bytes` `args`, a `bytes` or mapping `command`, and a non-string item are refused |
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.commons.frozen import freeze
from specweaver.sandbox.mcp.core.atom import declared_command


def test_a_one_word_command_and_its_args() -> None:
    assert declared_command("db", {"command": "docker", "args": ["run", "-i"]}) == [
        "docker",
        "run",
        "-i",
    ]


def test_a_list_command() -> None:
    assert declared_command("db", {"command": ["python", "server.py"]}) == ["python", "server.py"]


def test_a_frozen_config_gives_a_new_list_and_stays_as_it_was() -> None:
    config = freeze({"command": ["python"], "args": ["server.py"]})

    first = declared_command("db", config)
    second = declared_command("db", config)

    assert first == second == ["python", "server.py"]
    assert first is not second
    assert config["args"] == ("server.py",)


def test_a_plain_config_is_not_written() -> None:
    config: dict[str, Any] = {"command": ["python"], "args": ["server.py"]}

    declared_command("db", config).append("x")

    assert config == {"command": ["python"], "args": ["server.py"]}


@pytest.mark.parametrize("args", [None, [], ()])
def test_no_args(args: object) -> None:
    config: dict[str, Any] = (
        {"command": "docker"} if args is None else {"command": "docker", "args": args}
    )

    assert declared_command("db", config) == ["docker"]


@pytest.mark.parametrize("command", [None, "", "   ", [], ()])
def test_no_command_is_refused(command: object) -> None:
    config = {} if command is None else {"command": command}

    with pytest.raises(ValueError, match="MCP server 'db' has no command"):
        declared_command("db", config)


def test_a_spaced_string_command_is_refused_naming_the_list_form() -> None:
    with pytest.raises(ValueError, match=r"use command: \[python, server\.py\]"):
        declared_command("db", {"command": "python server.py"})


@pytest.mark.parametrize(
    "config",
    [
        {"command": b"docker"},
        {"command": {"a": 1}},
        {"command": 7},
        {"command": ["docker", 7]},
        {"command": ["docker", b"run"]},
    ],
)
def test_a_command_that_is_not_words_is_refused(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="command must be one word or a list of words"):
        declared_command("db", config)


@pytest.mark.parametrize("args", ["run -i", b"run", 7, {"a": 1}, ["run", 7]])
def test_args_that_are_not_a_list_of_words_are_refused(args: object) -> None:
    with pytest.raises(ValueError, match="args must be a list of words"):
        declared_command("db", {"command": "docker", "args": args})
