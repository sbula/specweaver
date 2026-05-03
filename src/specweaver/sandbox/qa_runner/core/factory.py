# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""QARunner Factory.

Auto-discovers the target project language based on presence of manifest files
in a given directory without communicating with explicit Database layers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.qa_runner.core.interface import QARunnerInterface

logger = logging.getLogger(__name__)


def resolve_runner(cwd: Path) -> QARunnerInterface:
    """Auto-discover the native QA pipeline runner for the target repository.

    Args:
        cwd: Target directory to sniff for manifests.

    Returns:
        The matching QARunnerInterface adapter. Defaults to PythonQARunner.
    """
    if (cwd / "package.json").exists():
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        return TypeScriptRunner(cwd=cwd)

    if (cwd / "Cargo.toml").exists():
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        return RustRunner(cwd=cwd)

    if (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        return KotlinRunner(cwd=cwd)

    if (cwd / "pom.xml").exists():
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        return JavaRunner(cwd=cwd)

    # By default, or if pyproject.toml is found
    from specweaver.sandbox.language.core.python.runner import PythonQARunner

    return PythonQARunner(cwd=cwd)
