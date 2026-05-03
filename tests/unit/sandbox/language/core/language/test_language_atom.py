# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for LanguageAtom — engine-level language capability provider."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.language.core.atom import LanguageAtom

if TYPE_CHECKING:
    from pathlib import Path


class TestLanguageAtom:
    """Tests for the LanguageAtom."""

    def test_handles_missing_intent(self, tmp_path: Path) -> None:
        """Should fail if no intent is provided."""
        atom = LanguageAtom(cwd=tmp_path)
        result = atom.run({})

        assert result.status == AtomStatus.FAILED
        assert "intent" in result.message.lower()

    def test_handles_unknown_intent(self, tmp_path: Path) -> None:
        """Should fail if an unknown intent is provided."""
        atom = LanguageAtom(cwd=tmp_path)
        result = atom.run({"intent": "some_unknown_intent"})

        assert result.status == AtomStatus.FAILED
        assert "some_unknown_intent" in result.message

    @patch("specweaver.sandbox.language.core._detect.detect_language")
    def test_detects_valid_language(self, mock_detect: MagicMock, tmp_path: Path) -> None:
        """Should successfully detect the language and return it in exports."""
        mock_detect.return_value = "rust"
        atom = LanguageAtom(cwd=tmp_path)

        result = atom.run({"intent": "detect_language"})

        assert result.status == AtomStatus.SUCCESS
        assert "rust" in result.message
        assert result.exports["language"] == "rust"
        mock_detect.assert_called_once_with(tmp_path)

    @patch("specweaver.sandbox.language.core._detect.detect_language")
    def test_raises_for_unsupported_language_if_detect_fails(
        self, mock_detect: MagicMock, tmp_path: Path
    ) -> None:
        """Edge Case: Should propagate LanguageNotFoundError or ValueError if detect_language fails."""
        mock_detect.side_effect = ValueError("Unsupported language 'ruby'")
        atom = LanguageAtom(cwd=tmp_path)

        with pytest.raises(ValueError, match="Unsupported language 'ruby'"):
            atom.run({"intent": "detect_language"})

    def test_convert_scenario_missing_arguments(self, tmp_path: Path) -> None:
        """Should fail if stem or scenario_set is missing for convert_scenario."""
        atom = LanguageAtom(cwd=tmp_path)

        # Missing both
        result1 = atom.run({"intent": "convert_scenario"})
        assert result1.status == AtomStatus.FAILED
        assert "stem" in result1.message.lower()

        # Missing scenario_set
        result2 = atom.run({"intent": "convert_scenario", "stem": "c01"})
        assert result2.status == AtomStatus.FAILED
        assert "scenario_set" in result2.message.lower()

        # Missing stem
        result3 = atom.run({"intent": "convert_scenario", "scenario_set": MagicMock()})
        assert result3.status == AtomStatus.FAILED
        assert "stem" in result3.message.lower()

    @patch(
        "specweaver.sandbox.language.core.scenario_converter_factory.create_scenario_converter"
    )
    def test_handles_convert_scenario(self, mock_create: MagicMock, tmp_path: Path) -> None:
        """Should successfully convert scenario and return output details."""
        mock_converter = MagicMock()
        mock_converter.convert.return_value = "fn test_c01() {}"
        mock_converter.output_path.return_value = tmp_path / "tests" / "test_c01.rs"
        mock_create.return_value = mock_converter

        # Mock ScenarioSet
        mock_scenario_set = MagicMock()

        atom = LanguageAtom(cwd=tmp_path)
        result = atom.run(
            {
                "intent": "convert_scenario",
                "stem": "c01",
                "scenario_set": mock_scenario_set,
            }
        )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["content"] == "fn test_c01() {}"
        assert str(result.exports["output_path"]).endswith("test_c01.rs")

        mock_create.assert_called_once_with(tmp_path)
        mock_converter.convert.assert_called_once_with(mock_scenario_set)
        mock_converter.output_path.assert_called_once_with("c01", tmp_path)
