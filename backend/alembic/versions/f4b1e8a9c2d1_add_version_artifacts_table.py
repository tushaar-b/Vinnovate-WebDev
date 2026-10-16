"""add version_artifacts table

Revision ID: f4b1e8a9c2d1
Revises: e3a1f940b12c
Create Date: 2026-10-16 19:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'f4b1e8a9c2d1'
down_revision: Union[str, Sequence[str], None] = 'e3a1f940b12c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'version_artifacts',
        sa.Column('version_id', UUID(as_uuid=True), sa.ForeignKey('versions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('screenshot_bytes', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('version_artifacts')
