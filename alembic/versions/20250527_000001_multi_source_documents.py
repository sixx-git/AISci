"""添加 Document 多来源文献库字段

Revision ID: 20250527_000001_multi_source_documents
Revises: 20250525_000001_pipeline_tables
Create Date: 2025-05-27

新增字段：
  - source_type: 文献来源类型（upload/arxiv/bibtex/google_scholar_import/manual）
  - external_id: 外部文献ID（arXiv ID / DOI）
  - pdf_url: PDF下载URL
  - library_scope: 文献库范围（base/project/personal）
  - import_status: 导入状态
  - metadata_json: 原始来源元数据JSON
  - is_personal: 是否为个人文献

旧数据默认值：
  - source_type = 'upload'
  - library_scope = 'personal'
  - import_status = 'imported'
  - is_personal = True
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250527_000001_multi_source_documents'
down_revision = '20250525_000001_pipeline_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 source_type 列（SQLite 兼容：使用 server_default 设置默认值）
    op.add_column(
        'documents',
        sa.Column('source_type', sa.String(50), nullable=True, server_default='upload',
                  comment='文献来源类型'),
    )
    op.create_index('ix_documents_source_type', 'documents', ['source_type'])

    # 添加 external_id 列
    op.add_column(
        'documents',
        sa.Column('external_id', sa.String(200), nullable=True,
                  comment='外部文献ID（arXiv ID / DOI）'),
    )
    op.create_index('ix_documents_external_id', 'documents', ['external_id'])

    # 添加 pdf_url 列
    op.add_column(
        'documents',
        sa.Column('pdf_url', sa.String(500), nullable=True,
                  comment='PDF下载URL（如arXiv PDF）'),
    )

    # 添加 library_scope 列
    op.add_column(
        'documents',
        sa.Column('library_scope', sa.String(20), nullable=True, server_default='personal',
                  comment='文献库范围'),
    )

    # 添加 import_status 列
    op.add_column(
        'documents',
        sa.Column('import_status', sa.String(50), nullable=True, server_default='imported',
                  comment='导入状态'),
    )
    op.create_index('ix_documents_import_status', 'documents', ['import_status'])

    # 添加 metadata_json 列
    op.add_column(
        'documents',
        sa.Column('metadata_json', sa.JSON(), nullable=True,
                  comment='原始来源元数据JSON'),
    )

    # 添加 is_personal 列
    op.add_column(
        'documents',
        sa.Column('is_personal', sa.Boolean(), nullable=True, server_default=sa.text('1'),
                  comment='是否为个人文献'),
    )

    # 将临时 nullable 列设为 NOT NULL（兼容 SQLite）
    with op.batch_alter_table('documents') as batch_op:
        batch_op.alter_column('source_type', nullable=False, existing_server_default='upload')
        batch_op.alter_column('library_scope', nullable=False, existing_server_default='personal')
        batch_op.alter_column('import_status', nullable=False, existing_server_default='imported')
        batch_op.alter_column('is_personal', nullable=False, existing_server_default=sa.text('1'))


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_column('is_personal')
        batch_op.drop_column('metadata_json')
        batch_op.drop_column('import_status')
        batch_op.drop_column('library_scope')
        batch_op.drop_column('pdf_url')
        batch_op.drop_column('external_id')
        batch_op.drop_column('source_type')