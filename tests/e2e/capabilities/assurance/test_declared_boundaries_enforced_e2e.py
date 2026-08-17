# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The whole boundary chain in one run: what a project declares is what gets enforced against it.

Proves: INT-US-01-SF02 P-7

`C-EXEC-01` and `C-EXEC-03` are cited link by link and this journey was the last row of
`INT-US-01-SF02`'s inventory left open. Every link had a test; the chain did not, and the gap was not
cosmetic:

- `test_tach_sync_e2e.py` runs `sw scan` on a **compliant** project and checks the generated
  `tach.toml` passes `tach check`. A generator that emitted boundaries nobody could violate would pass
  it.
- `test_architecture_pipeline.py` proves a violation becomes a C05 `FAIL` — against a **hand-written**
  `tach.toml` the test authors itself.

So the two halves were each proven against a different artefact. If `sync_tach_toml` emitted a
`tach.toml` that did not express the `context.yaml` boundaries, both tests would still be green: one
never checks a violation, the other never uses the generated file.

This test refuses to author `tach.toml`. The project declares its boundaries in `context.yaml`, `sw
scan` derives the config, and the violation is then judged **through that derived file** by the
production validation path. The assertion that matters is the one in the middle: the file must forbid
the thing the project's own declaration forbids, before the check is asked about it.

Filed under `assurance` because the journey's outcome is an assurance verdict. Its middle links belong
to `workspace` (topology, sync) and `sandbox` (the runner), so no single capability folder is the
honest home — the story owns it, and `ADR-004` clause 3 says so.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
_TACH = shutil.which("tach")
pytestmark = pytest.mark.skipif(_GIT is None or _TACH is None, reason="git and tach required")

#: `core` is pure logic and consumes nothing; `api` may consume `core`. So `core` importing `api` is
#: forbidden by the project's own declaration — and by nothing else in this test.
_CORE_CONTEXT = "name: src.core\nlevel: module\narchetype: pure-logic\nconsumes: []\n"
_API_CONTEXT = "name: src.api\nlevel: module\narchetype: orchestrator\nconsumes: [src.core]\n"

#: The violation. `core` reaching upward into `api` inverts the declared dependency direction.
_VIOLATION = "import src.api\n\n\ndef inverted() -> None:\n    pass\n"


def _cli(
    env: dict[str, str], *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the real `sw` CLI in a subprocess, as a developer would."""
    cmd = [
        sys.executable,
        "-c",
        "from specweaver.interfaces.cli.main import app; app(prog_name='sw')",
        *args,
    ]
    result = subprocess.run(
        cmd, env=env, cwd=None if cwd is None else str(cwd), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise AssertionError(
            f"sw {' '.join(args)} exited {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


@pytest.fixture
def declared_project(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A git project that declares its boundaries and then breaks them."""
    project = tmp_path / "declared-boundaries"
    project.mkdir()

    core = project / "src" / "core"
    core.mkdir(parents=True)
    (core / "__init__.py").write_text("", encoding="utf-8")
    (core / "logic.py").write_text("def pure() -> None:\n    pass\n", encoding="utf-8")
    (core / "context.yaml").write_text(_CORE_CONTEXT, encoding="utf-8")

    api = project / "src" / "api"
    api.mkdir(parents=True)
    (api / "__init__.py").write_text("", encoding="utf-8")
    (api / "main.py").write_text("import src.core\n", encoding="utf-8")
    (api / "context.yaml").write_text(_API_CONTEXT, encoding="utf-8")

    (project / "CONSTITUTION.md").write_text("# Project Constitution\n", encoding="utf-8")

    assert _GIT is not None
    for args in (
        ("init",),
        ("config", "user.email", "t@t"),
        ("config", "user.name", "t"),
    ):
        subprocess.run([_GIT, *args], cwd=str(project), check=True, capture_output=True)

    env = os.environ.copy()
    env["SPECWEAVER_DATA_DIR"] = str(tmp_path / "appdata")
    env["PYTHONIOENCODING"] = "utf-8"

    _cli(env, "init", "declared-boundaries", "--path", str(project))
    return project, env


def test_declared_boundaries_become_the_config_that_catches_the_violation(
    declared_project: tuple[Path, dict[str, str]],
) -> None:
    """context.yaml -> topology -> generated tach.toml -> a C05 finding, with nothing hand-authored."""
    project, env = declared_project

    # The chain must start from nothing: no boundary config exists until SpecWeaver derives one.
    assert not (project / "tach.toml").exists(), "the test must not pre-author the boundary config"

    # The violation is planted before the scan, so the generated config is derived from the
    # DECLARATION and not from the code that breaks it.
    (project / "src" / "core" / "bad_impl.py").write_text(_VIOLATION, encoding="utf-8")

    # 1. Map and emit: `sw scan` builds the topology from context.yaml and syncs it out.
    scan = _cli(env, "scan", cwd=project)
    assert "Tach Sync" in scan.stdout + scan.stderr, (
        f"scan did not reach the tach sync step: {scan.stdout}\n{scan.stderr}"
    )

    tach_toml = project / "tach.toml"
    assert tach_toml.exists(), "sw scan did not emit a boundary config"
    generated = tach_toml.read_text(encoding="utf-8")

    # 2. The link the two existing tests both skip: the emitted config must express the declared
    # boundary. `core` consumes nothing, so its `depends_on` must not grant it `api`. Without this
    # assertion a generator that emitted permissive boundaries would still satisfy the check below —
    # by making the violation legal rather than by catching it.
    assert "src.core" in generated and "src.api" in generated, (
        f"the emitted config does not name the declared modules:\n{generated}"
    )
    core_block = generated.split('path = "src.core"', 1)[1].split("[[modules]]", 1)[0]
    assert "src.api" not in core_block, (
        f"the emitted config lets src.core depend on src.api, which its context.yaml forbids:\n"
        f"{core_block}"
    )

    # 3. Enforce: the production validation path, judging the file against the config just generated.
    from specweaver.assurance.validation.models import Status
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
    from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow

    target = project / "src" / "core" / "bad_impl.py"
    results = execute_validation_flow(
        load_pipeline_yaml("validation_code_default"),
        target.read_text(encoding="utf-8"),
        spec_path=target,
        project_root=project,
    )

    c05 = next(r for r in results if r.rule_id == "C05")
    assert c05.status == Status.FAIL, (
        f"the violation was not caught through the generated config: {c05.message}"
    )
    assert "architectural violation" in c05.message.lower(), c05.message


def test_the_same_chain_passes_a_project_that_respects_its_declaration(
    declared_project: tuple[Path, dict[str, str]],
) -> None:
    """The control, and the test above is worth nothing without it.

    `FAIL` on a violating file only means the chain caught something if the identical chain returns
    `PASS` on a compliant one. Otherwise a C05 that fails unconditionally — or a generated config so
    malformed that tach errors on every file — would satisfy the assertion above and look like proof.

    Same fixture, same `sw scan`, same production validation path. The only difference is that nothing
    inverts the declared direction.
    """
    project, env = declared_project

    _cli(env, "scan", cwd=project)
    assert (project / "tach.toml").exists()

    from specweaver.assurance.validation.models import Status
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
    from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow

    # `api` importing `core` is exactly what its context.yaml declares it consumes.
    target = project / "src" / "api" / "main.py"
    results = execute_validation_flow(
        load_pipeline_yaml("validation_code_default"),
        target.read_text(encoding="utf-8"),
        spec_path=target,
        project_root=project,
    )

    c05 = next(r for r in results if r.rule_id == "C05")
    # PASS specifically, not merely "not FAIL": a SKIP would also clear that weaker bar, and a SKIP is
    # what an unhydrated QA context produces — i.e. the chain never running at all.
    assert c05.status == Status.PASS, (
        f"expected a clean architecture verdict, got {c05.status}: {c05.message}"
    )
