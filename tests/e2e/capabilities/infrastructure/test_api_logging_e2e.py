from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app
from specweaver.telemetry_logger import get_log_path, setup_logging, teardown_logging

if TYPE_CHECKING:
    from pathlib import Path

@pytest.mark.asyncio
async def test_api_execution_writes_json_telemetry(tmp_path: Path) -> None:
    from unittest.mock import patch

    with patch('specweaver.telemetry_logger._get_logs_dir', return_value=tmp_path):
        teardown_logging()
        setup_logging('test_project')
        log_file = get_log_path('test_project')

        db = Database(tmp_path / "test.db")
        app = create_app(db=db)
        client = TestClient(app)

        try:
            # Hit the health check endpoint
            response = client.get("/healthz")
            assert response.status_code == 200

            # Flush logging
            for h in logging.getLogger('specweaver').handlers:
                h.flush()

            # JSON Telemetry Written
            assert log_file.exists()
            content = log_file.read_text(encoding='utf-8')

            # Look for the log
            found_app_init = False
            found_health_exec = False

            for line in content.strip().split('\n'):
                try:
                    record = json.loads(line)
                    msg = record.get('message', '')
                    if 'Initializing create_app' in msg:
                        found_app_init = True
                    if record.get('levelname') == 'DEBUG' and 'Executing healthz API endpoint' in msg:
                        found_health_exec = True
                except json.JSONDecodeError:
                    continue

            assert found_app_init, "App initialization log not found in telemetry"
            assert found_health_exec, "Health API execution DEBUG log not found in telemetry"

        finally:
            teardown_logging()
