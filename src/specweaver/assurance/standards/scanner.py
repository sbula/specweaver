# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Scanner to orchestrate file discovery and language auto-detection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.assurance.standards.languages.javascript.analyzer import JSStandardsAnalyzer
from specweaver.assurance.standards.languages.python.analyzer import PythonStandardsAnalyzer
from specweaver.assurance.standards.languages.typescript.analyzer import TSStandardsAnalyzer

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.standards.analyzer import CategoryResult, StandardsAnalyzer

logger = logging.getLogger(__name__)


class StandardsScanner:
    """Orchestrates file discovery and language auto-detection for codebase standards.

    Routes files to their respective registered analyzers based on file extension
    and aggregates the extracted results.
    """

    def __init__(self, analyzers: list[StandardsAnalyzer] | None = None):
        if analyzers is None:
            analyzers = [
                PythonStandardsAnalyzer(),
                JSStandardsAnalyzer(),
                TSStandardsAnalyzer(),
            ]
        self.analyzers = analyzers

    def _hydrate_from_defaults(
        self, built_in_defaults: dict[str, list[CategoryResult]]
    ) -> list[CategoryResult]:
        logger.debug("scan: extraction empty in best_practice mode. Hydrating from defaults.")
        results: list[CategoryResult] = []
        for lang, categories in built_in_defaults.items():
            for res in categories:
                if not res.language:
                    res.language = lang
                results.append(res)
        return results

    def scan(
        self,
        files: list[Path],
        half_life_days: float = 180.0,
        mode: str = "mimicry",
        built_in_defaults: dict[str, list[CategoryResult]] | None = None,
    ) -> list[CategoryResult]:
        """Categorize files by language and execute corresponding analyzers.

        Args:
            files: A list of paths to source files representing the system scope.
            half_life_days: Decay factor deciding the weight of old code.
            mode: Analysis mode ('mimicry' or 'best_practice').
            built_in_defaults: Dictionary map of fallback standards per language.

        Returns:
            A list of CategoryResult objects across all detected languages.
        """
        # 1. Map extensions to their associated analyzer
        ext_to_analyzer: dict[str, StandardsAnalyzer] = {}
        for analyzer in self.analyzers:
            for ext in analyzer.file_extensions():
                ext_to_analyzer[ext] = analyzer

        # 2. Group files by mapped analyzer
        analyzer_to_files: dict[StandardsAnalyzer, list[Path]] = {}
        for path in files:
            ext = path.suffix
            matched = ext_to_analyzer.get(ext)
            if matched:
                if matched not in analyzer_to_files:
                    analyzer_to_files[matched] = []
                analyzer_to_files[matched].append(path)

        # 3. Execute extract_all on each active analyzer
        results: list[CategoryResult] = []
        for analyzer, grouped_files in analyzer_to_files.items():
            logger.debug(
                "scan: running %s on %d files",
                type(analyzer).__name__,
                len(grouped_files),
            )
            lang_results = analyzer.extract_all(grouped_files, half_life_days)
            for res in lang_results:
                res.language = analyzer.language_name()
            results.extend(lang_results)

        # 4. Fallback execution for empty extractions in adaptive mode
        if not results and mode == "best_practice" and built_in_defaults:
            results = self._hydrate_from_defaults(built_in_defaults)

        logger.debug("scan: completed, %d category results", len(results))
        return results
