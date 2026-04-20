from pathlib import Path

from specweaver.core.flow.handlers.base import RunContext


def test_run_context_accepts_analyzer_factory():
    dummy_factory = object()
    context = RunContext(
        project_path=Path('/tmp/proj'),
        spec_path=Path('/tmp/proj/spec.md'),
        analyzer_factory=dummy_factory
    )
    assert context.analyzer_factory is dummy_factory
