# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Database mixin for LLM usage telemetry and cost overrides.

Provides ``log_usage()``, ``get_usage_summary()``, ``get_usage_by_task_type()``,
and cost override CRUD methods.  Mixed into ``Database`` via
``TelemetryMixin``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class TelemetryMixin:
    """Mixin providing LLM usage telemetry DB operations."""

    # ------------------------------------------------------------------
    # Usage logging
    # ------------------------------------------------------------------

    def log_usage(self, record: dict[str, Any]) -> None:
        """Insert one usage record into ``llm_usage_log``.

        Args:
            record: Dict with keys matching ``UsageRecord.model_dump()``.
        """
        logger.debug(
            "log_usage: project=%s, task=%s, model=%s, tokens=%s",
            record.get("project_name"),
            record.get("task_type"),
            record.get("model"),
            record.get("total_tokens", 0),
        )
        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                "INSERT INTO llm_usage_log "
                "(timestamp, project_name, task_type, model, provider, "
                "prompt_tokens, completion_tokens, total_tokens, "
                "estimated_cost, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["timestamp"],
                    record["project_name"],
                    record["task_type"],
                    record["model"],
                    record["provider"],
                    record.get("prompt_tokens", 0),
                    record.get("completion_tokens", 0),
                    record.get("total_tokens", 0),
                    record.get("estimated_cost_usd", 0.0),
                    record.get("duration_ms", 0),
                ),
            )

    def get_usage_summary(
        self,
        project: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate usage records, optionally filtered by project and time.

        Returns a list of dicts with: task_type, model, call_count,
        total_prompt_tokens, total_completion_tokens, total_tokens,
        total_cost, total_duration_ms.

        Args:
            project: If set, filter to this project only.
            since: ISO timestamp — only include records after this time.
        """
        query = (
            "SELECT task_type, model, COUNT(*) as call_count, "
            "SUM(prompt_tokens) as total_prompt_tokens, "
            "SUM(completion_tokens) as total_completion_tokens, "
            "SUM(total_tokens) as total_tokens, "
            "SUM(estimated_cost) as total_cost, "
            "SUM(duration_ms) as total_duration_ms "
            "FROM llm_usage_log "
        )
        conditions: list[str] = []
        params: list[str] = []

        if project:
            conditions.append("project_name = ?")
            params.append(project)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        if conditions:
            query += "WHERE " + " AND ".join(conditions) + " "
        query += "GROUP BY task_type, model ORDER BY total_cost DESC"

        with self.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_usage_by_task_type(self, project: str) -> list[dict[str, Any]]:
        """Group usage by task_type for a specific project.

        Returns list of dicts with: task_type, call_count,
        total_tokens, total_cost.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                "SELECT task_type, COUNT(*) as call_count, "
                "SUM(total_tokens) as total_tokens, "
                "SUM(estimated_cost) as total_cost "
                "FROM llm_usage_log "
                "WHERE project_name = ? "
                "GROUP BY task_type ORDER BY total_cost DESC",
                (project,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Cost overrides
    # ------------------------------------------------------------------

    def get_cost_overrides(self) -> dict[str, tuple[float, float]]:
        """Load all user-configured cost overrides.

        Returns a dict mapping model_pattern to
        ``(input_cost_per_1k, output_cost_per_1k)`` tuples.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                "SELECT model_pattern, input_cost_per_1k, output_cost_per_1k "
                "FROM llm_cost_overrides",
            ).fetchall()
            return {
                r["model_pattern"]: (r["input_cost_per_1k"], r["output_cost_per_1k"]) for r in rows
            }

    def set_cost_override(
        self,
        model_pattern: str,
        input_cost_per_1k: float,
        output_cost_per_1k: float,
    ) -> None:
        """Upsert a cost override for a model pattern.

        Args:
            model_pattern: Model name or pattern (e.g. ``"gpt-4o"``).
            input_cost_per_1k: Cost per 1,000 input tokens (USD).
            output_cost_per_1k: Cost per 1,000 output tokens (USD).
        """
        now = datetime.now(UTC).isoformat()
        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                "INSERT OR REPLACE INTO llm_cost_overrides "
                "(model_pattern, input_cost_per_1k, output_cost_per_1k, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (model_pattern, input_cost_per_1k, output_cost_per_1k, now),
            )
        logger.debug(
            "set_cost_override: pattern=%s, input=$%.4f/1k, output=$%.4f/1k",
            model_pattern,
            input_cost_per_1k,
            output_cost_per_1k,
        )

    def delete_cost_override(self, model_pattern: str) -> None:
        """Remove a cost override, reverting to built-in pricing.

        Args:
            model_pattern: Model name or pattern to remove.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                "DELETE FROM llm_cost_overrides WHERE model_pattern = ?",
                (model_pattern,),
            )
