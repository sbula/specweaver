# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript runner implementation."""

import logging
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.loom.commons.language.typescript.parsers import extract_tsc_errors
from specweaver.core.loom.commons.qa_runner.interface import (
    ArchitectureRunResult,
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    DebugRunResult,
    LintRunResult,
    OutputEvent,
    QARunnerInterface,
    TestRunResult,
)

logger = logging.getLogger(__name__)


class TypeScriptRunner(QARunnerInterface):
    """Executes tests, compilation, and debugging for TypeScript projects."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    @property
    def language_name(self) -> str:
        """Canonical language identifier."""
        return "typescript"

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        """Run tests using standard TS runners (npm test). STUB."""
        return TestRunResult(
            total=0,
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
            duration_seconds=0.0,
            failures=[],
            coverage_pct=None,
        )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        """Run standard ESLint target. STUB."""
        return LintRunResult(
            error_count=0,
            fixable_count=0,
            fixed_count=0,
            errors=[],
        )

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        """Run standard JS complexity check. STUB."""
        return ComplexityRunResult(
            violation_count=0,
            max_complexity=max_complexity,
            violations=[],
        )

    def run_compiler(self, target: str) -> CompileRunResult:
        """Run TypeScript compiler (tsc --noEmit) and extract diagnostics."""
        npx_bin = shutil.which("npx") or "npx"
        cmd = [npx_bin, "tsc", "--noEmit"]
        if target and target != "." and target != "src/":
            # If a strict file target is provided, append it
            cmd.append(target)

        logger.debug("Running TypeScript compiler: %s", shlex.join(cmd))

        try:
            # We don't use check=True because tsc exits >0 on compilation errors
            proc = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("tsc process timed out after 120s")
            return CompileRunResult(
                error_count=1,
                warning_count=0,
                errors=[
                    CompileError(
                        file=target,
                        line=0,
                        column=0,
                        message="Timeout during compilation",
                        code="TIMEOUT",
                        is_warning=False,
                    )
                ],
            )
        except getattr(__builtins__, "FileNotFoundError", OSError):
            logger.error("TypeScript toolchain not found (tsc or npx missing)")
            return CompileRunResult(
                error_count=1,
                warning_count=0,
                errors=[
                    CompileError(
                        file=target,
                        line=0,
                        column=0,
                        message="TypeScript compiler not found in PATH.",
                        code="ENOENT",
                        is_warning=False,
                    )
                ],
            )

        errors = extract_tsc_errors(proc.stdout)

        return CompileRunResult(
            error_count=len(errors),
            warning_count=0,  # tsc doesn't easily divide warnings in standard output buffer without verbose
            errors=errors,
        )

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        """Execute a process and stream runtime outputs."""
        npx_bin = shutil.which("npx") or "npx"
        node_bin = shutil.which("node") or "node"
        cmd = (
            [npx_bin, "ts-node", entrypoint]
            if entrypoint.endswith(".ts")
            else [node_bin, entrypoint]
        )
        logger.debug("Running TypeScript debugger wrapper: %s", shlex.join(cmd))

        start_time = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return DebugRunResult(
                exit_code=124,
                duration_seconds=300.0,
                events=[OutputEvent(category="stderr", output="Timeout expired")],
            )
        except getattr(__builtins__, "FileNotFoundError", OSError):
            return DebugRunResult(
                exit_code=127,
                duration_seconds=0.0,
                events=[
                    OutputEvent(
                        category="stderr", output="Node/TypeScript runner not found in PATH"
                    )
                ],
            )

        duration = time.monotonic() - start_time

        events: list[OutputEvent] = []
        for line in proc.stdout.splitlines():
            events.append(OutputEvent(category="stdout", output=line))
        for line in proc.stderr.splitlines():
            events.append(OutputEvent(category="stderr", output=line))

        return DebugRunResult(
            exit_code=proc.returncode,
            duration_seconds=duration,
            events=events,
        )

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural checks dynamically using ESLint."""
        import json

        import yaml

        from specweaver.core.loom.commons.qa_runner.interface import ArchitectureViolation

        logger.debug(
            "TypeScriptRunner.run_architecture_check: target=%s, dal=%s", target, dal_level
        )

        target_path = self.cwd / target
        ctx_dir = target_path.parent if target_path.is_file() else target_path

        # Traverse up to find closest context.yaml
        while (
            ctx_dir != self.cwd
            and ctx_dir.parent != ctx_dir
            and not (ctx_dir / "context.yaml").exists()
        ):
            ctx_dir = ctx_dir.parent

        ctx_file = ctx_dir / "context.yaml"
        forbids = []
        if ctx_file.exists():
            try:
                data = yaml.safe_load(ctx_file.read_text(encoding="utf-8")) or {}
                forbids = data.get("forbids", [])
            except Exception as e:
                logger.warning("Failed to parse context.yaml at %s: %s", ctx_file, e)

        # Temporary config dropping
        tmp_dir = self.cwd / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        config_path = tmp_dir / ".eslint-specweaver-arch.json"

        eslint_config = {
            "root": True,
            "parser": "@typescript-eslint/parser",
            "plugins": ["@typescript-eslint"],
            "rules": {"no-restricted-imports": ["error", {"patterns": forbids}]},
        }
        config_path.write_text(json.dumps(eslint_config, indent=2), encoding="utf-8")

        npx_bin = shutil.which("npx") or "npx"
        cmd = [
            npx_bin,
            "eslint",
            "--no-eslintrc",
            "-c",
            str(config_path),
            "--format",
            "json",
            target,
        ]

        try:
            proc = subprocess.run(
                cmd, cwd=self.cwd, capture_output=True, text=True, timeout=60, check=False
            )
        except subprocess.TimeoutExpired:
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(file=target, code="Timeout", message="Jest timed out")
                ],
            )
        finally:
            config_path.unlink(missing_ok=True)

        violations = []
        if proc.stdout.strip():
            try:
                results = json.loads(proc.stdout)
                for res in results:
                    file_path = res.get("filePath", "")
                    for msg in res.get("messages", []):
                        if msg.get("ruleId") == "no-restricted-imports":
                            violations.append(
                                ArchitectureViolation(
                                    file=file_path,
                                    code="C05",
                                    message=msg.get("message", "Restricted import"),
                                )
                            )
            except json.JSONDecodeError:
                pass

        return ArchitectureRunResult(
            violation_count=len(violations),
            violations=violations,
        )
