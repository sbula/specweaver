# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript runner implementation."""

import logging
import shlex
import shutil
from pathlib import Path

from specweaver.commons.enums.dal import DALLevel
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.toolchain import (
    did_not_run,
    failed_architecture,
    failed_compile,
)
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    ArchitectureViolation,
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    DebugRunResult,
    LintRunResult,
    OutputEvent,
    QARunnerInterface,
    TestRunResult,
)
from specweaver.workspace.ast.parsers.typescript.parsers import extract_tsc_errors

logger = logging.getLogger(__name__)


def _restricted_import_violations(stdout: str) -> list[ArchitectureViolation]:
    """Boundary violations in an ESLint JSON report.

    Only `no-restricted-imports` counts: that is the rule the generated config uses to encode
    `C05`'s layer boundaries, and every other finding belongs to `run_linter`.
    """
    import json

    if not stdout.strip():
        return []

    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    return [
        ArchitectureViolation(
            file=entry.get("filePath", ""),
            code="C05",
            message=message.get("message", "Restricted import"),
        )
        for entry in report
        for message in entry.get("messages", [])
        if message.get("ruleId") == "no-restricted-imports"
    ]


class TypeScriptRunner(QARunnerInterface):
    """Executes tests, compilation, and debugging for TypeScript projects."""

    def __init__(self, cwd: Path, executor: SubprocessExecutor | None = None) -> None:
        self._cwd = cwd
        self._executor = executor or SubprocessExecutor(cwd=cwd)

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
            result = self._executor.execute(
                cmd,
                timeout_seconds=120,
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

        reason = did_not_run(result, "tsc")
        if reason:
            return failed_compile(reason)

        if result.timed_out:
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

        errors = extract_tsc_errors(result.stdout)

        return CompileRunResult(
            error_count=len(errors),
            warning_count=0,  # tsc doesn't easily divide warnings in standard output buffer without verbose
            errors=errors,
        )

    def _node_strips_types(self, node_bin: str) -> bool:
        """Whether this Node runs a `.ts` file directly, without a transpiling wrapper.

        Node gained type stripping behind a flag in 22.6 and on by default in 23.6, so on a current
        runtime no wrapper is needed at all. Probed by version rather than by running a scratch
        file: this is called per debug run, and spawning a probe process to decide how to spawn a
        process is a cost with no payoff.
        """
        try:
            probe = self._executor.execute([node_bin, "--version"], timeout_seconds=10)
        except OSError:
            # No node at all. Answering "no" hands the caller back to its own fallback and its own
            # error handling; raising from a capability probe would replace a reported exit code
            # with a traceback from a question nobody asked.
            return False
        if probe.exit_code != 0:
            return False
        try:
            major, minor = (int(part) for part in probe.stdout.strip().lstrip("v").split(".")[:2])
        except ValueError:
            return False
        return (major, minor) >= (23, 6)

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        """Execute a process and stream runtime outputs."""
        npx_bin = shutil.which("npx") or "npx"
        node_bin = shutil.which("node") or "node"
        if entrypoint.endswith(".ts"):
            # Three ways to run TypeScript, in descending order of reliability.
            #
            # `tsx` first — maintained, fast, and independent of the installed compiler version.
            #
            # Then Node itself. 23.6+ strips types natively, which needs no package at all and so
            # cannot be broken by a dependency resolution.
            #
            # `ts-node` last, and only as a fallback for older runtimes. Its final release (10.9.2,
            # 2023) reads `ts.sys` from the TypeScript compiler API, which TypeScript 7 no longer
            # exposes — so `npm install typescript ts-node` on a current registry produces a pair
            # that cannot work: `TypeError: Cannot read properties of undefined (reading
            # 'fileExists')`. Measured, with TypeScript 7.0.2 and Node 24.
            tsx_bin = shutil.which("tsx")
            if tsx_bin:
                cmd = [tsx_bin, entrypoint]
            elif self._node_strips_types(node_bin):
                cmd = [node_bin, entrypoint]
            else:
                cmd = [npx_bin, "ts-node", entrypoint]
        else:
            cmd = [node_bin, entrypoint]
        logger.debug("Running TypeScript debugger wrapper: %s", shlex.join(cmd))

        try:
            result = self._executor.execute(
                cmd,
                timeout_seconds=300,
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

        if result.timed_out:
            return DebugRunResult(
                exit_code=124,
                duration_seconds=result.duration_seconds,
                events=[OutputEvent(category="stderr", output="Timeout expired")],
            )

        events: list[OutputEvent] = []
        for line in result.stdout.splitlines():
            events.append(OutputEvent(category="stdout", output=line))
        for line in result.stderr.splitlines():
            events.append(OutputEvent(category="stderr", output=line))

        return DebugRunResult(
            exit_code=result.exit_code,
            duration_seconds=result.duration_seconds,
            events=events,
        )

    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural checks dynamically using ESLint."""
        import yaml

        from specweaver.commons import json
        from specweaver.sandbox.qa_runner.core.interface import ArchitectureViolation

        logger.debug(
            "TypeScriptRunner.run_architecture_check: target=%s, dal=%s", target, dal_level
        )

        target_path = self._cwd / target
        ctx_dir = target_path.parent if target_path.is_file() else target_path

        # Traverse up to find closest context.yaml
        while (
            ctx_dir != self._cwd
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
        tmp_dir = self._cwd / ".tmp"
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
            result = self._executor.execute(cmd, timeout_seconds=60)
        finally:
            config_path.unlink(missing_ok=True)

        reason = did_not_run(result, "the TypeScript architecture checker")
        if reason:
            return failed_architecture(reason)

        if result.timed_out:
            return ArchitectureRunResult(
                violation_count=1,
                violations=[
                    ArchitectureViolation(file=target, code="Timeout", message="Jest timed out")
                ],
            )

        violations = _restricted_import_violations(result.stdout)

        return ArchitectureRunResult(
            violation_count=len(violations),
            violations=violations,
        )
