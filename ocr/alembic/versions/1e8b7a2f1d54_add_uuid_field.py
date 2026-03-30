"""Add uuid field

Revision ID: 1e8b7a2f1d54
Revises: 0e9f3bfb9293
Create Date: 2025-03-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision: str = '1e8b7a2f1d54'
down_revision: Union[str, None] = '0e9f3bfb9293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pdfs', sa.Column('uuid', sa.String(), nullable=True))
    op.create_index(op.f('ix_pdfs_uuid'), 'pdfs', ['uuid'], unique=True)

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT file_hash FROM pdfs WHERE uuid IS NULL")).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE pdfs SET uuid = :uuid WHERE file_hash = :file_hash"),
            {"uuid": str(uuid.uuid4()), "file_hash": row.file_hash},
        )


def downgrade() -> None:
    op.drop_index(op.f('ix_pdfs_uuid'), table_name='pdfs')
    op.drop_column('pdfs', 'uuid')

