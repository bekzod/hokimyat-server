"""Rename pdfs table to documents and remove unused columns

Revision ID: a1b2c3d4e5f6
Revises: 9e22c0a41852
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '1e8b7a2f1d54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('pdfs', 'employee_id')
    op.drop_column('pdfs', 'employment_id')
    op.drop_column('pdfs', 'doc_type')
    op.rename_table('pdfs', 'documents')
    op.drop_index('ix_pdfs_file_hash', table_name='documents')
    op.create_index(op.f('ix_documents_file_hash'), 'documents', ['file_hash'], unique=True)
    op.execute('ALTER TYPE pdfstatus RENAME TO documentstatus')


def downgrade() -> None:
    op.execute('ALTER TYPE documentstatus RENAME TO pdfstatus')
    op.drop_index(op.f('ix_documents_file_hash'), table_name='documents')
    op.create_index('ix_pdfs_file_hash', 'documents', ['file_hash'], unique=True)
    op.rename_table('documents', 'pdfs')
    op.add_column('pdfs', op.Column('doc_type', op.Text(), nullable=True))
    op.add_column('pdfs', op.Column('employment_id', op.Integer(), nullable=True))
    op.add_column('pdfs', op.Column('employee_id', op.Integer(), nullable=True))
