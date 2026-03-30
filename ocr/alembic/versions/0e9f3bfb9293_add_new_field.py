"""Add new field

Revision ID: 0e9f3bfb9293
Revises: 9e22c0a41852
Create Date: 2025-01-27 18:08:00.005484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e9f3bfb9293'
down_revision: Union[str, None] = '9e22c0a41852'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'pdfs',
        sa.Column('manual_input', sa.JSON, nullable=True)
    )

def downgrade():
    op.drop_column('pdfs', 'manual_input')
