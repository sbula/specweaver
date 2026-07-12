"""TECH_005_rename_tables

Revision ID: af60fd3509a2
Revises: 1092f73fcd39
Create Date: 2026-07-12 13:11:56.459456

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'af60fd3509a2'
down_revision: str | Sequence[str] | None = '1092f73fcd39'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('projects', 'workspace_projects')
    op.rename_table('active_state', 'workspace_active_state')
    op.rename_table('project_standards', 'workspace_project_standards')
    op.rename_table('artifact_events', 'flow_artifact_events')
    op.rename_table('project_llm_links', 'llm_project_links')

    op.drop_index(op.f('ix_artifact_events_artifact_id'), table_name='flow_artifact_events')
    op.drop_index(op.f('ix_artifact_events_parent_id'), table_name='flow_artifact_events')
    op.create_index(op.f('ix_flow_artifact_events_artifact_id'), 'flow_artifact_events', ['artifact_id'], unique=False)
    op.create_index(op.f('ix_flow_artifact_events_parent_id'), 'flow_artifact_events', ['parent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_flow_artifact_events_artifact_id'), table_name='flow_artifact_events')
    op.drop_index(op.f('ix_flow_artifact_events_parent_id'), table_name='flow_artifact_events')

    op.rename_table('workspace_projects', 'projects')
    op.rename_table('workspace_active_state', 'active_state')
    op.rename_table('workspace_project_standards', 'project_standards')
    op.rename_table('flow_artifact_events', 'artifact_events')
    op.rename_table('llm_project_links', 'project_llm_links')

    op.create_index(op.f('ix_artifact_events_artifact_id'), 'artifact_events', ['artifact_id'], unique=False)
    op.create_index(op.f('ix_artifact_events_parent_id'), 'artifact_events', ['parent_id'], unique=False)
