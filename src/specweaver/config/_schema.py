# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Database schema DDL and migration constants."""

SCHEMA_V1 = """\
CREATE TABLE IF NOT EXISTS projects (
    name         TEXT PRIMARY KEY,
    root_path    TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL,
    last_used_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_profiles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    is_global         INTEGER NOT NULL DEFAULT 1,
    model             TEXT NOT NULL DEFAULT 'gemini-3-flash-preview',
    temperature       REAL NOT NULL DEFAULT 0.7,
    max_output_tokens INTEGER NOT NULL DEFAULT 4096,
    response_format   TEXT NOT NULL DEFAULT 'text'
);

CREATE TABLE IF NOT EXISTS project_llm_links (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    role         TEXT NOT NULL,
    profile_id   INTEGER NOT NULL REFERENCES llm_profiles(id),
    PRIMARY KEY (project_name, role)
);

CREATE TABLE IF NOT EXISTS validation_overrides (
    project_name   TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    rule_id        TEXT NOT NULL,
    enabled        INTEGER NOT NULL DEFAULT 1,
    warn_threshold REAL DEFAULT NULL,
    fail_threshold REAL DEFAULT NULL,
    PRIMARY KEY (project_name, rule_id)
);

CREATE TABLE IF NOT EXISTS active_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

DEFAULT_PROFILES = [
    ("system-default", 1, "gemini-3-flash-preview", 0.7, 4096, "text", 128_000, "gemini"),
    ("review", 1, "gemini-3-flash-preview", 0.3, 4096, "text", 128_000, "gemini"),
    ("draft", 1, "gemini-3-flash-preview", 0.7, 4096, "text", 128_000, "gemini"),
    ("search", 1, "gemini-3-flash-preview", 0.1, 4096, "text", 128_000, "gemini"),
]

SCHEMA_V2 = """\
ALTER TABLE llm_profiles ADD COLUMN context_limit INTEGER NOT NULL DEFAULT 128000;
"""

SCHEMA_V3 = """\
ALTER TABLE projects ADD COLUMN log_level TEXT NOT NULL DEFAULT 'DEBUG';
"""

SCHEMA_V4 = """\
ALTER TABLE projects ADD COLUMN constitution_max_size INTEGER NOT NULL DEFAULT 5120;
"""

SCHEMA_V5 = """\
ALTER TABLE projects ADD COLUMN domain_profile TEXT DEFAULT NULL;
"""

SCHEMA_V6 = """\
CREATE TABLE IF NOT EXISTS project_standards (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    scope        TEXT NOT NULL,
    language     TEXT NOT NULL,
    category     TEXT NOT NULL,
    data         TEXT NOT NULL,
    confidence   REAL NOT NULL,
    confirmed_by TEXT DEFAULT NULL,
    scanned_at   TEXT NOT NULL,
    PRIMARY KEY (project_name, scope, language, category)
);
"""

SCHEMA_V7 = """\
ALTER TABLE projects ADD COLUMN auto_bootstrap_constitution TEXT NOT NULL DEFAULT 'prompt';
"""

SCHEMA_V8 = """\
ALTER TABLE projects ADD COLUMN stitch_mode TEXT NOT NULL DEFAULT 'off';
"""

SCHEMA_V9 = """\
CREATE TABLE IF NOT EXISTS llm_usage_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    project_name      TEXT    NOT NULL,
    task_type         TEXT    NOT NULL,
    model             TEXT    NOT NULL,
    provider          TEXT    NOT NULL DEFAULT '',
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    estimated_cost    REAL    NOT NULL DEFAULT 0.0,
    duration_ms       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_project ON llm_usage_log(project_name);
CREATE INDEX IF NOT EXISTS idx_usage_task_type ON llm_usage_log(task_type);

CREATE TABLE IF NOT EXISTS llm_cost_overrides (
    model_pattern      TEXT PRIMARY KEY,
    input_cost_per_1k  REAL NOT NULL,
    output_cost_per_1k REAL NOT NULL,
    updated_at         TEXT NOT NULL
);
"""

SCHEMA_V10 = """\
ALTER TABLE llm_profiles ADD COLUMN provider TEXT NOT NULL DEFAULT 'gemini';
"""

SCHEMA_V11 = """\
CREATE TABLE IF NOT EXISTS artifact_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    parent_id   TEXT,
    run_id      TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lineage_parent ON artifact_events(parent_id);
CREATE INDEX IF NOT EXISTS idx_lineage_artifact ON artifact_events(artifact_id);

ALTER TABLE llm_usage_log ADD COLUMN run_id TEXT DEFAULT '';
"""

SCHEMA_V12 = """\
ALTER TABLE artifact_events ADD COLUMN model_id TEXT NOT NULL DEFAULT 'unknown';
"""

SCHEMA_V13 = """\
ALTER TABLE projects ADD COLUMN default_dal TEXT NOT NULL DEFAULT 'DAL_A';
"""

SCHEMA_V14 = """\
DROP TABLE IF EXISTS validation_overrides;
"""
