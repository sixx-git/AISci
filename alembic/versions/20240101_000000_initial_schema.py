"""初始数据库架构

Revision ID: 20240101_000000_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240101_000000_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建项目表
    op.create_table(
        'projects',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('research_topic', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_projects_id', 'id'),
        sa.Index('ix_projects_name', 'name'),
        sa.Index('ix_projects_status', 'status'),
        sa.Index('ix_projects_created_at', 'created_at'),
    )
    
    # 创建文档表
    op.create_table(
        'documents',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('authors', sa.Text(), nullable=True),
        sa.Column('abstract', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('publication_date', sa.DateTime(), nullable=True),
        sa.Column('journal', sa.String(200), nullable=True),
        sa.Column('volume', sa.String(50), nullable=True),
        sa.Column('issue', sa.String(50), nullable=True),
        sa.Column('pages', sa.String(50), nullable=True),
        sa.Column('doi', sa.String(200), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('doc_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='uploaded'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('custom_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.Index('ix_documents_id', 'id'),
        sa.Index('ix_documents_project_id', 'project_id'),
        sa.Index('ix_documents_title', 'title'),
        sa.Index('ix_documents_doi', 'doi'),
        sa.Index('ix_documents_status', 'status'),
        sa.Index('ix_documents_created_at', 'created_at'),
    )
    
    # 创建文献切片表
    op.create_table(
        'chunks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('document_id', sa.String(36), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_preview', sa.String(500), nullable=True),
        sa.Column('start_offset', sa.Integer(), nullable=True),
        sa.Column('end_offset', sa.Integer(), nullable=True),
        sa.Column('start_page', sa.Integer(), nullable=True),
        sa.Column('end_page', sa.Integer(), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('vector', sa.JSON(), nullable=True),
        sa.Column('dimension', sa.Integer(), nullable=True),
        sa.Column('chunk_type', sa.String(50), nullable=True, server_default='text'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('tokens_count', sa.Integer(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.Index('ix_chunks_id', 'id'),
        sa.Index('ix_chunks_project_id', 'project_id'),
        sa.Index('ix_chunks_document_id', 'document_id'),
        sa.Index('ix_chunks_status', 'status'),
        sa.Index('ix_chunks_created_at', 'created_at'),
    )
    
    # 创建科学假设表
    op.create_table(
        'hypotheses',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True, server_default='0.5'),
        sa.Column('novelty_score', sa.Float(), nullable=True),
        sa.Column('feasibility_score', sa.Float(), nullable=True),
        sa.Column('source_documents', sa.Text(), nullable=True),
        sa.Column('source_chunks', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('parent_id', sa.String(36), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('counterarguments', sa.Text(), nullable=True),
        sa.Column('experiment_suggestions', sa.Text(), nullable=True),
        sa.Column('generated_by', sa.String(100), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.Index('ix_hypotheses_id', 'id'),
        sa.Index('ix_hypotheses_project_id', 'project_id'),
        sa.Index('ix_hypotheses_status', 'status'),
        sa.Index('ix_hypotheses_created_at', 'created_at'),
    )
    
    # 创建实验设计表
    op.create_table(
        'experiment_designs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('hypothesis_id', sa.String(36), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('design_type', sa.String(100), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('procedure', sa.Text(), nullable=True),
        sa.Column('materials', sa.Text(), nullable=True),
        sa.Column('equipment', sa.Text(), nullable=True),
        sa.Column('data_collection', sa.Text(), nullable=True),
        sa.Column('measurement_methods', sa.Text(), nullable=True),
        sa.Column('statistical_methods', sa.Text(), nullable=True),
        sa.Column('expected_results', sa.Text(), nullable=True),
        sa.Column('success_criteria', sa.Text(), nullable=True),
        sa.Column('time_estimate', sa.String(100), nullable=True),
        sa.Column('budget_estimate', sa.Text(), nullable=True),
        sa.Column('resources_needed', sa.Text(), nullable=True),
        sa.Column('potential_pitfalls', sa.Text(), nullable=True),
        sa.Column('contingency_plans', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('generated_by', sa.String(100), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['hypothesis_id'], ['hypotheses.id'], ondelete='SET NULL'),
        sa.Index('ix_experiment_designs_id', 'id'),
        sa.Index('ix_experiment_designs_project_id', 'project_id'),
        sa.Index('ix_experiment_designs_hypothesis_id', 'hypothesis_id'),
        sa.Index('ix_experiment_designs_status', 'status'),
        sa.Index('ix_experiment_designs_created_at', 'created_at'),
    )
    
    # 创建报告表
    op.create_table(
        'reports',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('authors', sa.Text(), nullable=True),
        sa.Column('introduction', sa.Text(), nullable=True),
        sa.Column('literature_review', sa.Text(), nullable=True),
        sa.Column('methodology', sa.Text(), nullable=True),
        sa.Column('results', sa.Text(), nullable=True),
        sa.Column('discussion', sa.Text(), nullable=True),
        sa.Column('conclusion', sa.Text(), nullable=True),
        sa.Column('future_work', sa.Text(), nullable=True),
        sa.Column('references', sa.Text(), nullable=True),
        sa.Column('full_content', sa.Text(), nullable=True),
        sa.Column('attachments', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('language', sa.String(20), nullable=True, server_default='zh-CN'),
        sa.Column('generated_by', sa.String(100), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.Index('ix_reports_id', 'id'),
        sa.Index('ix_reports_project_id', 'project_id'),
        sa.Index('ix_reports_status', 'status'),
        sa.Index('ix_reports_created_at', 'created_at'),
    )
    
    # 创建运行日志表
    op.create_table(
        'run_logs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('level', sa.String(20), nullable=False, server_default='info'),
        sa.Column('category', sa.String(50), nullable=False, server_default='system'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('document_id', sa.String(36), nullable=True),
        sa.Column('hypothesis_id', sa.String(36), nullable=True),
        sa.Column('experiment_design_id', sa.String(36), nullable=True),
        sa.Column('report_id', sa.String(36), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_stacktrace', sa.Text(), nullable=True),
        sa.Column('user_id', sa.String(100), nullable=True),
        sa.Column('user_action', sa.String(100), nullable=True),
        sa.Column('component', sa.String(100), nullable=True),
        sa.Column('module', sa.String(100), nullable=True),
        sa.Column('function', sa.String(100), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.Index('ix_run_logs_id', 'id'),
        sa.Index('ix_run_logs_project_id', 'project_id'),
        sa.Index('ix_run_logs_level', 'level'),
        sa.Index('ix_run_logs_category', 'category'),
        sa.Index('ix_run_logs_created_at', 'created_at'),
    )


def downgrade() -> None:
    op.drop_table('run_logs')
    op.drop_table('reports')
    op.drop_table('experiment_designs')
    op.drop_table('hypotheses')
    op.drop_table('chunks')
    op.drop_table('documents')
    op.drop_table('projects')
