"""Add agent memory bank tables

Revision ID: 1092f73fcd39
Revises: 037b85034bb0
Create Date: 2026-05-05 20:26:27.449907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import specweaver.core.config.database

# revision identifiers, used by Alembic.
revision: str = '1092f73fcd39'
down_revision: Union[str, Sequence[str], None] = '037b85034bb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('memory_epics',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_name', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'CLOSED', name='epicstatus'), nullable=False),
    sa.Column('created_at', specweaver.core.config.database.StrictISODateTime(), nullable=False),
    sa.Column('updated_at', specweaver.core.config.database.StrictISODateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_name'], ['projects.name'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('memory_tasks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_name', sa.String(), nullable=False),
    sa.Column('epic_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'DONE', 'BLOCKED', 'UPSTREAM_BLOCKED', 'ARCHIVED', name='taskstatus'), nullable=False),
    sa.Column('assigned_worker_id', sa.String(), nullable=True),
    sa.Column('locked_at', specweaver.core.config.database.StrictISODateTime(), nullable=True),
    sa.Column('last_heartbeat_at', specweaver.core.config.database.StrictISODateTime(), nullable=True),
    sa.Column('handover_context', sa.String(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('attempt_count', sa.Integer(), nullable=False),
    sa.Column('created_at', specweaver.core.config.database.StrictISODateTime(), nullable=False),
    sa.Column('updated_at', specweaver.core.config.database.StrictISODateTime(), nullable=False),
    sa.CheckConstraint('attempt_count >= 0', name='chk_attempts_non_negative'),
    sa.CheckConstraint('length(handover_context) <= 8192', name='chk_handover_length'),
    sa.CheckConstraint('version >= 1', name='chk_version_positive'),
    sa.ForeignKeyConstraint(['epic_id'], ['memory_epics.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_name'], ['projects.name'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('memory_tasks', schema=None) as batch_op:
        batch_op.create_index('idx_task_epic', ['epic_id'], unique=False)
        batch_op.create_index('idx_task_heartbeat', ['status', 'last_heartbeat_at'], unique=False)
        batch_op.create_index('idx_task_status_project', ['status', 'project_name'], unique=False)
        batch_op.create_index('idx_task_worker', ['assigned_worker_id'], unique=False)

    op.create_table('memory_defects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'RESOLVED', name='defectstatus'), nullable=False),
    sa.Column('created_at', specweaver.core.config.database.StrictISODateTime(), nullable=False),
    sa.Column('resolved_at', specweaver.core.config.database.StrictISODateTime(), nullable=True),
    sa.CheckConstraint('length(description) <= 8192', name='chk_defect_desc_length'),
    sa.ForeignKeyConstraint(['task_id'], ['memory_tasks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('memory_defects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_memory_defects_task_id'), ['task_id'], unique=False)

    op.create_table('memory_state_transitions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.Uuid(), nullable=False),
    sa.Column('from_status', sa.Enum('PENDING', 'IN_PROGRESS', 'DONE', 'BLOCKED', 'UPSTREAM_BLOCKED', 'ARCHIVED', name='taskstatus'), nullable=False),
    sa.Column('to_status', sa.Enum('PENDING', 'IN_PROGRESS', 'DONE', 'BLOCKED', 'UPSTREAM_BLOCKED', 'ARCHIVED', name='taskstatus'), nullable=False),
    sa.Column('reason', sa.Enum('ACQUIRED', 'RELEASED', 'COMPLETED', 'ZOMBIE_TIMEOUT', 'CIRCUIT_BREAKER', 'MANUAL_UNBLOCK', 'PR_REJECTION', 'UPSTREAM_BLOCKED', 'UPSTREAM_CLEARED', 'AGENT_FAILURE', 'ABANDONED', 'ARCHIVED', name='transitionreason'), nullable=False),
    sa.Column('worker_id', sa.String(), nullable=True),
    sa.Column('timestamp', specweaver.core.config.database.StrictISODateTime(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['memory_tasks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('memory_state_transitions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_memory_state_transitions_task_id'), ['task_id'], unique=False)

    op.create_table('memory_task_dependencies',
    sa.Column('parent_task_id', sa.Uuid(), nullable=False),
    sa.Column('child_task_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('parent_task_id != child_task_id', name='chk_no_self_dependency'),
    sa.ForeignKeyConstraint(['child_task_id'], ['memory_tasks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_task_id'], ['memory_tasks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('parent_task_id', 'child_task_id')
    )
    with op.batch_alter_table('memory_task_dependencies', schema=None) as batch_op:
        batch_op.create_index('idx_dep_child', ['child_task_id'], unique=False)
        batch_op.create_index('idx_dep_parent', ['parent_task_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('memory_task_dependencies', schema=None) as batch_op:
        batch_op.drop_index('idx_dep_parent')
        batch_op.drop_index('idx_dep_child')
    op.drop_table('memory_task_dependencies')

    with op.batch_alter_table('memory_state_transitions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_memory_state_transitions_task_id'))
    op.drop_table('memory_state_transitions')

    with op.batch_alter_table('memory_defects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_memory_defects_task_id'))
    op.drop_table('memory_defects')

    with op.batch_alter_table('memory_tasks', schema=None) as batch_op:
        batch_op.drop_index('idx_task_worker')
        batch_op.drop_index('idx_task_status_project')
        batch_op.drop_index('idx_task_heartbeat')
        batch_op.drop_index('idx_task_epic')
    op.drop_table('memory_tasks')

    op.drop_table('memory_epics')
