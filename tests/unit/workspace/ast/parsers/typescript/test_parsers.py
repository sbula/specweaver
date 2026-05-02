# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for TypeScript parsing logic."""

from specweaver.workspace.ast.parsers.typescript.parsers import extract_tsc_errors


class TestTypeScriptParsers:
    def test_extract_tsc_errors(self) -> None:
        tsc_output = (
            "src/main.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.\n"
            "lib/utils.ts(45,1): error TS1005: ',' expected.\n"
            "Other compilation error info without standard format.\n"
        )
        errors = extract_tsc_errors(tsc_output)

        assert len(errors) == 2

        err1 = errors[0]
        assert err1.file == "src/main.ts"
        assert err1.line == 12
        assert err1.column == 5
        assert err1.message == "Type 'string' is not assignable to type 'number'."
        assert err1.code == "TS2322"
        assert not err1.is_warning

        err2 = errors[1]
        assert err2.file == "lib/utils.ts"
        assert err2.line == 45
        assert err2.column == 1
