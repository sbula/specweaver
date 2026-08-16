# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C13 compares the code's AST against a parsed protocol schema and reports what drifted.

Proves: A-VAL-01 FR-5

**Citation added 2026-08-16 by `TECH-051` CB-2, after reading the tests rather than counting them.**
`test_c13_fails_when_drift_detected` supplies two protocol endpoints and an AST carrying one, then
asserts `Status.FAIL` with the missing path named in the finding — which is FR-5's promise
(*"emits ERRORs on missing/mismatched signatures"*) rather than a restatement of it. The file was
already here and already passing; nothing pointed the ledger at it, so `A-VAL-01` reported FR-5 as
proven by nothing while this ran green on every commit.
"""

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c13_contract_drift import C13ContractDriftRule


def test_c13_skips_when_missing_context():
    rule = C13ContractDriftRule()
    rule.context = {}
    result = rule.check("")
    assert result.status == Status.SKIP
    assert "Missing" in result.message


def test_c13_passes_when_all_endpoints_matched():
    rule = C13ContractDriftRule()
    rule.context = {
        "protocol_schema": [{"path": "/api/v1/users", "method": "GET"}],
        "ast_payload": {"get_users": {"decorators": ["@app.get('/api/v1/users')"]}},
    }
    result = rule.check("")
    assert result.status == Status.PASS


def test_c13_fails_when_drift_detected():
    rule = C13ContractDriftRule()
    rule.context = {
        "protocol_schema": [
            {"path": "/api/v1/users", "method": "GET"},
            {"path": "/api/v1/auth", "method": "POST"},
        ],
        "ast_payload": {"get_users": {"decorators": ["@app.get('/api/v1/users')"]}},
    }
    result = rule.check("")
    assert result.status == Status.FAIL
    assert len(result.findings) == 1
    assert "/api/v1/auth" in result.findings[0].message
    assert "Contract Drift" in result.findings[0].message


def test_c13_handles_flat_string_payload_gracefully():
    """Story 1: Rule handles flat string native representation fallback natively."""
    rule = C13ContractDriftRule()
    rule.context = {
        "protocol_schema": [{"path": "/api/v1/ping", "method": "GET"}],
        "ast_payload": "def ping(): \n @route('/api/v1/ping')",
    }
    result = rule.check("")
    assert result.status == Status.PASS


def test_c13_ignores_items_without_path():
    """Story 2: Rule gracefully continues loop if endpoint natively skips defining path."""
    rule = C13ContractDriftRule()
    rule.context = {
        "protocol_schema": [
            {"method": "GET"},  # missing path
            {"path": "/valid", "method": "POST"},
        ],
        "ast_payload": " @route('/valid') ",
    }
    result = rule.check("")
    assert result.status == Status.PASS


def test_c13_verifies_deep_nested_dict():
    """Story 3: Rule verifies deep nested dictionary hierarchies."""
    rule = C13ContractDriftRule()
    rule.context = {
        "protocol_schema": [{"path": "/deep/route"}],
        "ast_payload": {"class_a": {"method_b": {"docs": ["@api('/deep/route')"]}}},
    }
    result = rule.check("")
    assert result.status == Status.PASS


def test_c13_ignores_malformed_list_strings():
    """Story 6: Rule seamlessly ignores non-object items (strings/integers)."""
    rule = C13ContractDriftRule()
    rule.context = {
        "protocol_schema": ["random_string_in_list", 42, {"path": "/api/v1/ok"}],
        "ast_payload": "@route('/api/v1/ok')",
    }
    result = rule.check("")
    assert result.status == Status.PASS
