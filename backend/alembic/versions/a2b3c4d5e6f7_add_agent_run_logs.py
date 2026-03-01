"""add agent_run_logs

Revision ID: a2b3c4d5e6f7
Revises: 8166fe3f5797
Create Date: 2026-02-28 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '8166fe3f5797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_run_logs',
    sa.Column('id', UUID(as_uuid=True), nullable=False),
    sa.Column('agent_run_id', UUID(as_uuid=True), nullable=False),
    sa.Column('step', sa.Integer(), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('action_type', sa.String(length=100), nullable=True),
    sa.Column('action_params', JSONB(), nullable=True),
    sa.Column('thought', sa.Text(), nullable=True),
    sa.Column('evaluation', sa.Text(), nullable=True),
    sa.Column('memory', sa.Text(), nullable=True),
    sa.Column('extracted_content', sa.Text(), nullable=True),
    sa.Column('success', sa.Boolean(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('step_start_time', sa.Float(), nullable=True),
    sa.Column('step_end_time', sa.Float(), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_run_logs_agent_run_id'), 'agent_run_logs', ['agent_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_run_logs_agent_run_id'), table_name='agent_run_logs')
    op.drop_table('agent_run_logs')
