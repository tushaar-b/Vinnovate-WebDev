"""add email channel and nullable monitor_id

Revision ID: e3a1f940b12c
Revises: 9d75e771f785
Create Date: 2026-10-15 02:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'e3a1f940b12c'
down_revision: Union[str, Sequence[str], None] = '9d75e771f785'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'EMAIL' value to channel_type_enum
    op.execute("ALTER TYPE channel_type_enum ADD VALUE IF NOT EXISTS 'EMAIL';")
    # Make monitor_id nullable on notification_channels to allow global notification channels
    op.alter_column('notification_channels', 'monitor_id', existing_type=UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.alter_column('notification_channels', 'monitor_id', existing_type=UUID(as_uuid=True), nullable=False)
