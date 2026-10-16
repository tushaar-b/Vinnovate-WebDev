"""add judge session fields to monitors

Revision ID: b3c8f1e2a4d5
Revises: f4b1e8a9c2d1
Create Date: 2026-10-16 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3c8f1e2a4d5'
down_revision: Union[str, Sequence[str], None] = 'f4b1e8a9c2d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('monitors', sa.Column('judge_session_id', sa.String(length=64), nullable=True))
    op.add_column('monitors', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('monitors', sa.Column('manual_checks_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('monitors', sa.Column('manual_checks_window_start', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_monitors_judge_session_id', 'monitors', ['judge_session_id'])


def downgrade() -> None:
    op.drop_index('ix_monitors_judge_session_id', table_name='monitors')
    op.drop_column('monitors', 'manual_checks_window_start')
    op.drop_column('monitors', 'manual_checks_count')
    op.drop_column('monitors', 'expires_at')
    op.drop_column('monitors', 'judge_session_id')
