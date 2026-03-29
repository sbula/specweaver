# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration test for SpecWeaver logging routing."""

from __future__ import annotations

import json
import logging

import pytest
from rich.console import Console

from specweaver.logging import setup_logging, teardown_logging


@pytest.fixture(autouse=True)
def clean_logging():
    """Ensure logging state is clean before and after each test."""
    teardown_logging()
    yield
    teardown_logging()


def test_logging_routing_and_format(tmp_path, monkeypatch, capsys):
    """End-to-End test verifying logs correctly route to file (JSON) and console (Rich)."""
    # 1. Setup mock directories
    _logs = tmp_path / "logs"
    monkeypatch.setattr("specweaver.config.paths.logs_dir", lambda: _logs)
    
    # 2. Force Rich to not use colors and not paginate so capsys can capture deterministic output
    monkeypatch.setattr("rich.console.Console.is_terminal", property(lambda self: False))
    monkeypatch.setattr("rich.console.Console.color_system", property(lambda self: None))

    setup_logging("integration_test")
    logger = logging.getLogger("specweaver.business_logic")

    # 3. Fire all logging levels
    logger.debug("Test debug message")
    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message")

    try:
        _ = 1 / 0
    except ZeroDivisionError:
        logger.exception("Test exception message")

    # Force teardown to close file handlers so we can read the file safely on Windows
    teardown_logging()

    # 4. Assert File Output (All 5 levels, JSON schema, tracebacks present)
    log_file = _logs / "integration_test" / "specweaver.log"
    assert log_file.exists()

    lines = log_file.read_text("utf-8").strip().splitlines()
    assert len(lines) == 6

    parsed = [json.loads(line) for line in lines]
    levels = [p["levelname"] for p in parsed]
    messages = [p["message"] for p in parsed]

    assert levels == ["DEBUG", "DEBUG", "INFO", "WARNING", "ERROR", "ERROR"]
    assert "Logging initialised" in messages[0]
    assert messages[1:] == [
        "Test debug message",
        "Test info message",
        "Test warning message",
        "Test error message",
        "Test exception message",
    ]

    # Verify JSON structure contains expected tags
    for i, p in enumerate(parsed):
        assert "timestamp" in p
        assert "name" in p
        if i == 0:
            assert p["name"] == "specweaver"
        else:
            assert p["name"] == "specweaver.business_logic"

    # Verify JSON traceback exists only on the exception line
    for i, p in enumerate(parsed):
        if i == 5:
            assert "exc_info" in p
            assert "ZeroDivisionError" in p["exc_info"]
        else:
            assert "exc_info" not in p

    # 5. Assert Console Output (Warnings+, No JSON, Tracebacks present)
    captured = capsys.readouterr()
    out_err = captured.out + captured.err

    # WARNING+ should be printed
    assert "Test warning message" in out_err
    assert "Test error message" in out_err
    assert "Test exception message" in out_err

    # DEBUG and INFO should be silenced on console
    assert "Test debug message" not in out_err
    assert "Test info message" not in out_err

    # Traceback should be rendered
    assert "ZeroDivisionError" in out_err
