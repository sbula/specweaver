-- specweaver.db as the release before TECH-090 made it (bootstrap_database at 58632d7a).

-- Frozen 2026-11-07 for TECH-090 FR-6; never regenerate it from current code.

CREATE TABLE flow_artifact_events (
	id INTEGER NOT NULL, 
	artifact_id VARCHAR NOT NULL, 
	parent_id VARCHAR, 
	run_id VARCHAR NOT NULL, 
	event_type VARCHAR NOT NULL, 
	timestamp VARCHAR NOT NULL, 
	model_id VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE llm_offering (
	id INTEGER NOT NULL, 
	model VARCHAR NOT NULL, 
	host VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (model, host)
);

CREATE TABLE llm_price (
	id INTEGER NOT NULL, 
	offering_id INTEGER NOT NULL, 
	token_kind VARCHAR NOT NULL, 
	usd_per_million FLOAT NOT NULL, 
	valid_from DATE NOT NULL, 
	source VARCHAR NOT NULL, 
	rule_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(offering_id) REFERENCES llm_offering (id), 
	FOREIGN KEY(rule_id) REFERENCES llm_price_rule (id)
);

CREATE TABLE llm_price_refresh (
	id INTEGER NOT NULL, 
	checked_at VARCHAR NOT NULL, 
	etag VARCHAR, 
	offerings VARCHAR NOT NULL, 
	reached_at VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE llm_price_rule (
	id INTEGER NOT NULL, 
	min_prefix_tokens INTEGER, 
	max_age_seconds INTEGER, 
	min_prompt_tokens INTEGER, 
	requires VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE llm_prompt_start (
	server VARCHAR NOT NULL, 
	model VARCHAR NOT NULL, 
	start_hash VARCHAR NOT NULL, 
	last_sent VARCHAR NOT NULL, 
	PRIMARY KEY (server, model, start_hash)
);

CREATE TABLE llm_step_outcome (
	run_id VARCHAR NOT NULL, 
	step_name VARCHAR NOT NULL, 
	outcome VARCHAR NOT NULL, 
	PRIMARY KEY (run_id, step_name)
);

CREATE TABLE llm_usage_log (
	id INTEGER NOT NULL, 
	timestamp VARCHAR NOT NULL, 
	project_name VARCHAR NOT NULL, 
	task_type VARCHAR NOT NULL, 
	model VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	prompt_tokens INTEGER NOT NULL, 
	completion_tokens INTEGER NOT NULL, 
	total_tokens INTEGER NOT NULL, 
	estimated_cost FLOAT, 
	duration_ms INTEGER NOT NULL, 
	run_id VARCHAR, 
	server VARCHAR, 
	dal_level VARCHAR, 
	step_name VARCHAR, 
	call_status VARCHAR DEFAULT 'ok' NOT NULL, 
	cached_read_tokens INTEGER, 
	cache_write_tokens INTEGER, 
	local BOOLEAN, 
	PRIMARY KEY (id)
);

CREATE TABLE llm_usage_price (
	id INTEGER NOT NULL, 
	usage_id INTEGER NOT NULL, 
	token_kind VARCHAR NOT NULL, 
	usd_per_million FLOAT NOT NULL, 
	source VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usage_id) REFERENCES llm_usage_log (id)
);

CREATE TABLE memory_defects (
	id INTEGER NOT NULL, 
	task_id CHAR(32) NOT NULL, 
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	status VARCHAR(8) NOT NULL, 
	created_at VARCHAR NOT NULL, 
	resolved_at VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_defect_desc_length CHECK (length(description) <= 8192), 
	FOREIGN KEY(task_id) REFERENCES memory_tasks (id) ON DELETE CASCADE
);

CREATE TABLE memory_epics (
	id CHAR(32) NOT NULL, 
	project_name VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	status VARCHAR(6) NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_name) REFERENCES workspace_projects (name) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE memory_state_transitions (
	id INTEGER NOT NULL, 
	task_id CHAR(32) NOT NULL, 
	from_status VARCHAR(16) NOT NULL, 
	to_status VARCHAR(16) NOT NULL, 
	reason VARCHAR(16) NOT NULL, 
	worker_id VARCHAR, 
	timestamp VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(task_id) REFERENCES memory_tasks (id) ON DELETE CASCADE
);

CREATE TABLE memory_task_dependencies (
	parent_task_id CHAR(32) NOT NULL, 
	child_task_id CHAR(32) NOT NULL, 
	PRIMARY KEY (parent_task_id, child_task_id), 
	CONSTRAINT chk_no_self_dependency CHECK (parent_task_id != child_task_id), 
	FOREIGN KEY(parent_task_id) REFERENCES memory_tasks (id) ON DELETE CASCADE, 
	FOREIGN KEY(child_task_id) REFERENCES memory_tasks (id) ON DELETE CASCADE
);

CREATE TABLE memory_tasks (
	id CHAR(32) NOT NULL, 
	project_name VARCHAR NOT NULL, 
	epic_id CHAR(32), 
	title VARCHAR NOT NULL, 
	description VARCHAR, 
	status VARCHAR(16) NOT NULL, 
	assigned_worker_id VARCHAR, 
	locked_at VARCHAR, 
	last_heartbeat_at VARCHAR, 
	handover_context VARCHAR, 
	version INTEGER NOT NULL, 
	attempt_count INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_handover_length CHECK (length(handover_context) <= 8192), 
	CONSTRAINT chk_version_positive CHECK (version >= 1), 
	CONSTRAINT chk_attempts_non_negative CHECK (attempt_count >= 0), 
	FOREIGN KEY(project_name) REFERENCES workspace_projects (name) ON DELETE CASCADE ON UPDATE CASCADE, 
	FOREIGN KEY(epic_id) REFERENCES memory_epics (id) ON DELETE SET NULL
);

CREATE TABLE specweaver_migrations (name TEXT PRIMARY KEY);

CREATE TABLE workspace_active_state (
	"key" VARCHAR NOT NULL, 
	value VARCHAR NOT NULL, 
	PRIMARY KEY ("key")
);

CREATE TABLE workspace_project_standards (
	project_name VARCHAR NOT NULL, 
	scope VARCHAR NOT NULL, 
	language VARCHAR NOT NULL, 
	category VARCHAR NOT NULL, 
	data VARCHAR NOT NULL, 
	confidence FLOAT NOT NULL, 
	confirmed_by VARCHAR, 
	scanned_at VARCHAR NOT NULL, 
	PRIMARY KEY (project_name, scope, language, category), 
	FOREIGN KEY(project_name) REFERENCES workspace_projects (name) ON DELETE CASCADE
);

CREATE TABLE workspace_projects (
	name VARCHAR NOT NULL, 
	root_path VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	last_used_at VARCHAR NOT NULL, 
	log_level VARCHAR NOT NULL, 
	console_log_level VARCHAR DEFAULT 'WARNING' NOT NULL, 
	constitution_max_size INTEGER NOT NULL, 
	domain_profile VARCHAR, 
	auto_bootstrap_constitution VARCHAR NOT NULL, 
	stitch_mode VARCHAR NOT NULL, 
	default_dal VARCHAR NOT NULL, 
	PRIMARY KEY (name), 
	UNIQUE (root_path)
);

CREATE INDEX idx_dep_child ON memory_task_dependencies (child_task_id);

CREATE INDEX idx_dep_parent ON memory_task_dependencies (parent_task_id);

CREATE INDEX idx_task_epic ON memory_tasks (epic_id);

CREATE INDEX idx_task_heartbeat ON memory_tasks (status, last_heartbeat_at);

CREATE INDEX idx_task_status_project ON memory_tasks (status, project_name);

CREATE INDEX idx_task_worker ON memory_tasks (assigned_worker_id);

CREATE INDEX ix_flow_artifact_events_artifact_id ON flow_artifact_events (artifact_id);

CREATE INDEX ix_flow_artifact_events_parent_id ON flow_artifact_events (parent_id);

CREATE INDEX ix_llm_price_offering_id ON llm_price (offering_id);

CREATE INDEX ix_llm_prompt_start_last_sent ON llm_prompt_start (last_sent);

CREATE INDEX ix_llm_usage_history ON llm_usage_log (task_type, model, dal_level);

CREATE INDEX ix_llm_usage_log_project_name ON llm_usage_log (project_name);

CREATE INDEX ix_llm_usage_log_task_type ON llm_usage_log (task_type);

CREATE INDEX ix_llm_usage_price_usage_id ON llm_usage_price (usage_id);

CREATE INDEX ix_memory_defects_task_id ON memory_defects (task_id);

CREATE INDEX ix_memory_state_transitions_task_id ON memory_state_transitions (task_id);

CREATE UNIQUE INDEX ux_llm_price_once ON llm_price (offering_id, token_kind, IFNULL(rule_id, 0), valid_from);
