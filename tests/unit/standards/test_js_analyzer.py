# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for JSStandardsAnalyzer."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from specweaver.standards.languages.javascript.analyzer import JSStandardsAnalyzer


@pytest.fixture()
def analyzer() -> JSStandardsAnalyzer:
    return JSStandardsAnalyzer()


class TestJSAnalyzerInterface:
    def test_language_name(self, analyzer: JSStandardsAnalyzer) -> None:
        assert analyzer.language_name() == "javascript"

    def test_file_extensions(self, analyzer: JSStandardsAnalyzer) -> None:
        assert analyzer.file_extensions() == {".js", ".jsx", ".cjs", ".mjs"}

    def test_supported_categories(self, analyzer: JSStandardsAnalyzer) -> None:
        cats = analyzer.supported_categories()
        assert "naming" in cats
        assert "error_handling" in cats
        assert "jsdoc" in cats
        assert "test_patterns" in cats
        assert "import_patterns" in cats
        assert "async_patterns" in cats


class TestJSNamingExtraction:
    def test_detects_camel_case_functions(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "code.js"
        f.write_text(textwrap.dedent("""\
            function getUser() {}
            const setName = () => {};
            const process_data = function() {};
        """))
        results = analyzer.extract_all([f], 180)
        naming = next(r for r in results if r.category == "naming")
        assert naming.dominant.get("function_style") == "camelCase"
        assert naming.sample_size == 3

    def test_detects_pascal_case_classes(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "models.js"
        f.write_text(textwrap.dedent("""\
            class UserProfile {}
            class DatabaseConnection {}
            class my_weird_class {}
        """))
        results = analyzer.extract_all([f], 180)
        naming = next(r for r in results if r.category == "naming")
        assert naming.dominant.get("class_style") == "PascalCase"
        assert naming.sample_size == 3


class TestJSErrorHandlingExtraction:
    def test_detects_bare_catch(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "handlers.js"
        f.write_text(textwrap.dedent("""\
            try {
                doSomething();
            } catch (e) {
                console.error(e);
            }
        """))
        results = analyzer.extract_all([f], 180)
        err = next(r for r in results if r.category == "error_handling")
        assert err.dominant.get("exception_style") == "bare"

    def test_detects_specific_catch(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "handlers.js"
        f.write_text(textwrap.dedent("""\
            try {
                doSomething();
            } catch (e) {
                if (e instanceof TypeError) {
                    // handle
                } else if (e.name === 'CustomError') {
                    // handle
                }
            }
        """))
        results = analyzer.extract_all([f], 180)
        err = next(r for r in results if r.category == "error_handling")
        assert err.dominant.get("exception_style") == "specific"


class TestJSDocExtraction:
    def test_detects_jsdoc_presence(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "doc.js"
        f.write_text(textwrap.dedent("""\
            /**
             * Greets a user.
             * @param {string} name
             */
            function greet(name) { return name; }

            function noDoc() {}
        """))
        results = analyzer.extract_all([f], 180)
        docs = next(r for r in results if r.category == "jsdoc")
        assert docs.dominant.get("coverage") == "high"


class TestJSImportPatterns:
    def test_detects_es6_modules(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "imports.js"
        f.write_text(textwrap.dedent("""\
            import { something } from 'module';
            import os from 'os';
        """))
        results = analyzer.extract_all([f], 180)
        imports = next(r for r in results if r.category == "import_patterns")
        assert imports.dominant.get("style") == "es6"

    def test_detects_commonjs(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "req.js"
        f.write_text(textwrap.dedent("""\
            const fs = require('fs');
            const path = require('path');
        """))
        results = analyzer.extract_all([f], 180)
        imports = next(r for r in results if r.category == "import_patterns")
        assert imports.dominant.get("style") == "commonjs"


class TestJSAsyncPatterns:
    def test_detects_async_await(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "async.js"
        f.write_text(textwrap.dedent("""\
            async function fetchData() {
                const res = await fetch(url);
            }
        """))
        results = analyzer.extract_all([f], 180)
        async_pat = next(r for r in results if r.category == "async_patterns")
        assert async_pat.dominant.get("style") == "async/await"

    def test_detects_promises(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "prom.js"
        f.write_text(textwrap.dedent("""\
            function fetchData() {
                return fetch(url).then(res => res.json()).catch(err => console.error(err));
            }
        """))
        results = analyzer.extract_all([f], 180)
        async_pat = next(r for r in results if r.category == "async_patterns")
        assert async_pat.dominant.get("style") == "promises"


class TestJSTestPatterns:
    def test_detects_jest(
        self, analyzer: JSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "app.test.js"
        f.write_text(textwrap.dedent("""\
            describe('app', () => {
                it('should work', () => {
                    expect(1).toBe(1);
                });
            });
        """))
        results = analyzer.extract_all([f], 180)
        tests = next(r for r in results if r.category == "test_patterns")
        assert tests.dominant.get("framework") == "jest/mocha"
