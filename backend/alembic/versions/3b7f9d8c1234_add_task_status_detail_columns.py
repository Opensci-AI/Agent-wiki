"""add_task_status_detail_columns

Revision ID: 3b7f9d8c1234
Revises: 2a238eb97fb5
Create Date: 2026-04-11 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3b7f9d8c1234'
down_revision: Union[str, None] = '2a238eb97fb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status_detail and current_step columns to tasks table
    op.add_column('tasks', sa.Column('status_detail', sa.String(length=500), nullable=True))
    op.add_column('tasks', sa.Column('current_step', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'current_step')
    op.drop_column('tasks', 'status_detail')
