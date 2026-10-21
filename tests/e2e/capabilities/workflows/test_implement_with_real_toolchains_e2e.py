# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw implement` with the real pytest, Maven, Gradle, npm and cargo — only the model is doubled.

Proves: D-INTL-08 FR-9
Proves: D-INTL-08 NFR-3

US-3 P-5, the real half. Each sample in `tests/fixtures/toolchain/` is copied, prepared the way a
user would (`npm install`, a first Maven or Gradle build), and implemented. The model answers with
correct code and tests for the sample's package; the language's real tools compile, lint and test
them. The `toolchain` tier is outside the default run and runs nightly (`scripts/toolchain.py`).

| Bucket | Case |
|---|---|
| Happy | each language: the run ends well and its real test run counts a passing test |
| Boundary | Rust's sample has only `src/main.rs`: the real `cargo test` reaches the module through the created `src/lib.rs` |
| Degradation | a missing tool or an unreachable package registry skips the language, saying which |
| Hostile | not applicable — the samples are the repo's own; hostile inputs are proven by the unit tiers |
"""

from __future__ import annotations

import functools
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

runner = CliRunner()
pytestmark = [pytest.mark.e2e, pytest.mark.toolchain]

SAMPLES = Path(__file__).resolve().parents[3] / "fixtures" / "toolchain"


@dataclass(frozen=True)
class _Sample:
    language: str
    tools: tuple[str, ...]
    registries: tuple[str, ...]
    prepare: tuple[str, ...]
    code: str
    tests: str


_JAVA_CODE = """package com.example;

/** Greets by name. */
public final class Greeter {
    private Greeter() {
    }

    /** The greeting for {@code name}. */
    public static String greet(final String name) {
        return "Hello, " + name;
    }
}"""

_JAVA_TESTS = """package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class GreeterTest {
    @Test
    void greetsByName() {
        assertEquals("Hello, Ada", Greeter.greet("Ada"));
    }
}"""

_SAMPLES = {
    "python": _Sample(
        "python",
        ("python",),
        (),
        (),
        'def greet(name: str) -> str:\n    return f"Hello, {name}"',
        "from greeter import greet\n\n\ndef test_greets_by_name() -> None:\n"
        '    assert greet("Ada") == "Hello, Ada"',
    ),
    "rust": _Sample(
        "rust",
        ("cargo",),
        (),
        (),
        'pub fn greet(name: &str) -> String {\n    format!("Hello, {name}")\n}',
        "use greet::greeter::greet;\n\n#[test]\nfn greets_by_name() {\n"
        '    assert_eq!(greet("Ada"), "Hello, Ada");\n}',
    ),
    "java": _Sample(
        "java",
        ("mvn", "java"),
        ("repo.maven.apache.org",),
        ("mvn", "-q", "test-compile", "pmd:pmd"),
        _JAVA_CODE,
        _JAVA_TESTS,
    ),
    "kotlin": _Sample(
        "kotlin",
        ("java",),
        ("services.gradle.org", "plugins.gradle.org", "repo.maven.apache.org"),
        ("./gradlew", "-q", "testClasses", "detekt"),
        'package com.example\n\nfun greet(name: String): String = "Hello, $name"',
        "package com.example\n\nimport kotlin.test.Test\nimport kotlin.test.assertEquals\n\n"
        "class GreeterTest {\n    @Test\n    fun greetsByName() {\n"
        '        assertEquals("Hello, Ada", greet("Ada"))\n    }\n}',
    ),
    "typescript": _Sample(
        "typescript",
        ("npm", "npx", "node"),
        ("registry.npmjs.org",),
        ("npm", "install", "--no-audit", "--no-fund"),
        "export function greet(name: string): string {\n  return `Hello, ${name}`;\n}",
        'import { describe, expect, it } from "vitest";\n\nimport { greet } from "../src/greeter";\n\n'
        'describe("greet", () => {\n  it("greets by name", () => {\n'
        '    expect(greet("Ada")).toBe("Hello, Ada");\n  });\n});',
    ),
}


@functools.cache
def _reachable(host: str) -> bool:
    try:
        socket.create_connection((host, 443), timeout=3).close()
    except OSError:  # expected: the machine has no route to the registry
        return False
    return True


def _require(sample: _Sample) -> None:
    missing = [tool for tool in sample.tools if shutil.which(tool) is None]
    if missing:
        pytest.skip(f"toolchain not installed: {', '.join(missing)}")
    unreachable = [host for host in sample.registries if not _reachable(host)]
    if unreachable:
        pytest.skip(f"package registry unreachable: {', '.join(unreachable)}")


class _Model:
    """Answers with the sample's code or tests, fenced, by the role it is given."""

    provider_name = "scripted"

    def __init__(self, sample: _Sample) -> None:
        self._sample = sample

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        role = messages[0].content if len(messages) > 1 else ""
        body = self._sample.tests if "test generator" in role else self._sample.code
        return LLMResponse(text=f"```{self._sample.language}\n{body}\n```", model="test-model")


def _project(tmp_path: Path, sample: _Sample) -> Path:
    project = tmp_path / "proj"
    shutil.copytree(SAMPLES / sample.language, project)
    assert runner.invoke(app, ["init", "greet", "--path", str(project)]).exit_code == 0
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    if sample.prepare:
        prepared = subprocess.run(
            list(sample.prepare), cwd=project, capture_output=True, text=True, timeout=1800
        )
        assert prepared.returncode == 0, prepared.stdout[-2000:] + prepared.stderr[-2000:]
    return project


@pytest.mark.usefixtures("_mock_db")
@pytest.mark.parametrize("language", list(_SAMPLES))
def test_sw_implement_with_the_real_toolchain(tmp_path: Path, language: str) -> None:
    sample = _SAMPLES[language]
    _require(sample)
    project = _project(tmp_path, sample)

    with doubled_llm(_Model(sample)):
        result = runner.invoke(
            app,
            ["implement", str(project / "specs" / "greeter_spec.md"), "--project", str(project)],
        )

    assert result.exit_code == 0, result.output
    counts = re.search(r"tests: (\d+) passed, (\d+) failed", result.output)
    assert counts is not None, result.output
    assert int(counts.group(1)) >= 1 and int(counts.group(2)) == 0, result.output
    assert shows(result.output, "lint:")
    if language == "rust":
        assert "pub mod greeter;" in (project / "src" / "lib.rs").read_text(encoding="utf-8")
