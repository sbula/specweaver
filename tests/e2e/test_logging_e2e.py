from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.handlers.base import RunContext
from specweaver.telemetry_logger import get_log_path, setup_logging, teardown_logging


@pytest.mark.asyncio
async def test_full_execute_pipeline_generates_json_log_session(tmp_path: Path) -> None:
    from unittest.mock import patch

    # We will override _get_logs_dir to point to tmp_path
    with patch('specweaver.telemetry_logger._get_logs_dir', return_value=tmp_path):
        teardown_logging()
        setup_logging('test_project')

        log_file = get_log_path('test_project')

        target_logger = logging.getLogger('specweaver.core.flow')

        try:
            context = RunContext(
                project_path=tmp_path,
                spec_path=tmp_path / 'spec.md',
                config=MagicMock(),
                llm=MagicMock()
            )

            from specweaver.core.flow.engine.models import PipelineDefinition
            _ = PipelineRunner(PipelineDefinition(name="test", steps=[]), context)

            target_logger.debug('Executing DraftSpecHandler')
            target_logger.info('Draft complete')

            # Flush handlers
            for h in logging.getLogger('specweaver').handlers:
                h.flush()

            assert log_file.exists()
            lines = log_file.read_text(encoding='utf-8').strip().split('\n')

            # The first line might be the 'Logging initialised' line
            log1 = json.loads(lines[-2])
            log2 = json.loads(lines[-1])

            assert log1['levelname'] == 'DEBUG'
            assert log1['name'] == 'specweaver.core.flow'
            assert 'Executing' in log1['message']

            assert log2['levelname'] == 'INFO'
            assert log2['name'] == 'specweaver.core.flow'
            assert 'Draft complete' in log2['message']

            assert 'timestamp' in log1
            assert 'timestamp' in log2

        finally:
            teardown_logging()
