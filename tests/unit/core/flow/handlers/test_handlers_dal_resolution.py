# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for DAL resolution within pipeline handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.handlers.base import RunContext

# ---------------------------------------------------------------------------
# DAL Constraint Resolution
# ---------------------------------------------------------------------------


class TestValidationDALResolution:
    """Tests for the _resolve_merged_settings helper."""

    @pytest.mark.asyncio
    @patch("specweaver.core.config.dal_resolver.DALResolver.resolve")
    async def test_dal_resolution_merges_matrix(
        self, mock_resolve: MagicMock, tmp_path: Path
    ) -> None:
        from specweaver.commons.enums.dal import DALLevel
        from specweaver.core.config.settings import (
            DALImpactMatrix,
            LLMSettings,
            RuleOverride,
            SpecWeaverSettings,
            ValidationSettings,
        )
        from specweaver.core.flow.handlers.validation import _resolve_merged_settings

        base_val = ValidationSettings(overrides={"S01": RuleOverride(rule_id="S01", enabled=False)})
        dal_val = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", enabled=True, fail_threshold=10.0)}
        )
        matrix = DALImpactMatrix(matrix={DALLevel.DAL_A: dal_val})

        llm = LLMSettings(model="gemini", provider="gemini", api_key="")
        settings = SpecWeaverSettings(llm=llm, validation=base_val, dal_matrix=matrix)

        spec = tmp_path / "test.md"
        spec.touch()
        ctx = RunContext(project_path=tmp_path, spec_path=spec, settings=settings)

        mock_resolve.return_value = "DAL_A"

        merged = _resolve_merged_settings(ctx, spec)

        assert merged is not ctx.settings
        assert merged.validation.get_override("S01").enabled is True
        assert merged.validation.get_override("S01").fail_threshold == 10.0

    @patch("specweaver.workspace.store.WorkspaceRepository")
    @patch("specweaver.core.config.dal_resolver.DALResolver.resolve")
    def test_dal_resolution_fallback_to_db(
        self, mock_resolve: MagicMock, mock_repo_class: MagicMock, tmp_path: Path
    ) -> None:
        from unittest.mock import MagicMock

        from specweaver.commons.enums.dal import DALLevel
        from specweaver.core.config.settings import (
            DALImpactMatrix,
            LLMSettings,
            RuleOverride,
            SpecWeaverSettings,
            ValidationSettings,
        )
        from specweaver.core.flow.handlers.validation import _resolve_merged_settings

        base_val = ValidationSettings()
        dal_val = ValidationSettings(overrides={"C02": RuleOverride(rule_id="C02", enabled=False)})
        matrix = DALImpactMatrix(matrix={DALLevel.DAL_B: dal_val})

        llm = LLMSettings(model="g", provider="g", api_key="")
        settings = SpecWeaverSettings(llm=llm, validation=base_val, dal_matrix=matrix)

        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def mock_scope():
            yield MagicMock()

        mock_db = MagicMock()
        mock_db.async_session_scope = mock_scope
        mock_repo = AsyncMock()
        mock_repo.get_default_dal.return_value = "DAL_B"
        mock_repo_class.return_value = mock_repo

        spec = tmp_path / "test.md"
        spec.touch()
        ctx = RunContext(project_path=tmp_path, spec_path=spec, settings=settings, db=mock_db)

        mock_resolve.return_value = None  # No contextual DAL found

        merged = _resolve_merged_settings(ctx, spec)

        mock_repo.get_default_dal.assert_called_once_with(tmp_path.name)
        assert merged.validation.get_override("C02").enabled is False

    @patch("specweaver.workspace.store.WorkspaceRepository")
    @patch("specweaver.core.config.dal_resolver.DALResolver.resolve")
    def test_dal_resolution_invalid_db_string_ignored(
        self, mock_resolve: MagicMock, mock_repo_class: MagicMock, tmp_path: Path
    ) -> None:
        from unittest.mock import MagicMock

        from specweaver.commons.enums.dal import DALLevel
        from specweaver.core.config.settings import (
            DALImpactMatrix,
            LLMSettings,
            SpecWeaverSettings,
            ValidationSettings,
        )
        from specweaver.core.flow.handlers.validation import _resolve_merged_settings

        base_val = ValidationSettings()
        matrix = DALImpactMatrix(matrix={DALLevel.DAL_B: ValidationSettings()})
        settings = SpecWeaverSettings(
            llm=LLMSettings(model="g", provider="g", api_key=""),
            validation=base_val,
            dal_matrix=matrix,
        )

        mock_db = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get_default_dal.return_value = "INVALID_DAL_STRING"
        mock_repo_class.return_value = mock_repo

        ctx = RunContext(
            project_path=tmp_path, spec_path=tmp_path / "test.md", settings=settings, db=mock_db
        )
        mock_resolve.return_value = None

        merged = _resolve_merged_settings(ctx, tmp_path / "test.md")

        # Should gracefully catch ValueError during DALLevel mapping on Line 44, returning default settings
        assert merged is ctx.settings

    @patch("specweaver.workspace.store.WorkspaceRepository")
    @patch("specweaver.core.config.dal_resolver.DALResolver.resolve")
    def test_dal_resolution_catches_db_exception(
        self, mock_resolve: MagicMock, mock_repo_class: MagicMock, tmp_path: Path
    ) -> None:
        from unittest.mock import MagicMock

        from specweaver.core.config.settings import (
            LLMSettings,
            SpecWeaverSettings,
            ValidationSettings,
        )
        from specweaver.core.flow.handlers.validation import _resolve_merged_settings

        base_val = ValidationSettings()
        settings = SpecWeaverSettings(
            llm=LLMSettings(model="g", provider="g", api_key=""), validation=base_val
        )

        mock_db = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get_default_dal.side_effect = Exception("DB Connection Lost")
        mock_repo_class.return_value = mock_repo

        ctx = RunContext(
            project_path=tmp_path, spec_path=tmp_path / "test.md", settings=settings, db=mock_db
        )
        mock_resolve.return_value = None

        merged = _resolve_merged_settings(ctx, tmp_path / "test.md")

        # Should catch DB Exception explicitly, leaving DAL as None, returning original settings
        assert merged is ctx.settings

    @pytest.mark.asyncio
    @patch("specweaver.core.config.dal_resolver.DALResolver.resolve")
    async def test_dal_resolution_deep_merges_nested_extra_params(
        self, mock_resolve: MagicMock, tmp_path: Path
    ) -> None:
        from specweaver.commons.enums.dal import DALLevel
        from specweaver.core.config.settings import (
            DALImpactMatrix,
            LLMSettings,
            RuleOverride,
            SpecWeaverSettings,
            ValidationSettings,
        )
        from specweaver.core.flow.handlers.validation import _resolve_merged_settings

        # Base settings has extra_params for S01
        base_val = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01", enabled=True, extra_params={"base": 1.0, "keep_me": 2.0}
                )
            }
        )

        # DAL Matrix overrides the fail threshold and adds/overwrites a key in extra_params, but SHOULD preserve "keep_me" thanks to deep_merge_dict
        dal_val = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01",
                    enabled=True,
                    fail_threshold=5.0,
                    extra_params={"base": 5.0, "add_me": 3.0},
                )
            }
        )
        matrix = DALImpactMatrix(matrix={DALLevel.DAL_A: dal_val})

        settings = SpecWeaverSettings(
            llm=LLMSettings(model="g", provider="g", api_key=""),
            validation=base_val,
            dal_matrix=matrix,
        )
        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "test.md", settings=settings)
        mock_resolve.return_value = "DAL_A"

        merged = _resolve_merged_settings(ctx, tmp_path / "test.md")

        s01_override = merged.validation.get_override("S01")
        assert s01_override.fail_threshold == 5.0
        # Check deep merge on extra_params
        assert s01_override.extra_params == {"base": 5.0, "keep_me": 2.0, "add_me": 3.0}
