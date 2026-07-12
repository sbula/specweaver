# TECH-005: Database Table Prefix Harmonization

## Goal
Refactor all existing database tables in the monolithic SQLite database to use a strict domain-prefix naming convention (e.g., `workspace_projects`, `llm_profiles`, `flow_artifact_events`).

## Background
During the architectural audit of B-INTL-09 (Agent Memory Bank), we established the pattern of prefixing domain tables with `memory_` (e.g., `memory_tasks`, `memory_epics`). This clearly demarcates domain boundaries at the schema level and prevents naming collisions with generic terms like "tasks" or "projects".

However, existing tables in the codebase lack this convention:
- `projects` -> should be `workspace_projects`
- `active_state` -> should be `workspace_active_state`
- `project_standards` -> should be `workspace_project_standards`
- `artifact_events` -> should be `flow_artifact_events`
- `llm_usage_log`, `llm_profiles`, `project_llm_links` -> already have LLM-related prefixes, but should be verified for consistency.

## Scope
1. Rename all existing tables to include their bounded context prefix based on their domain (`workspace`, `flow`, `llm`, `infrastructure`).
2. Generate Alembic migrations for the table renames.
3. Update all SQLAlchemy `__tablename__` directives and string-based `ForeignKey` references across the codebase.
4. Refactor any raw SQL queries or hardcoded table names in tests or repositories.
5. Ensure zero data loss during the migration (SQLite supports `ALTER TABLE RENAME TO`).
