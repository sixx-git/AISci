"""添加 Pipeline 相关表

Revision ID: 20250525_000001_pipeline_tables
Revises: 20240101_000000_initial_schema
Create Date: 2025-05-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250525_000001_pipeline_tables'
down_revision = '20240101_000000_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 Prompt 版本表
    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('creator', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('avg_token_count', sa.Integer(), nullable=True),
        sa.Column('avg_execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('default_parameters', sa.JSON(), nullable=True),
        sa.Column('parent_version_id', sa.String(36), nullable=True),
        sa.Column('change_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_prompt_versions_id', 'id'),
        sa.Index('ix_prompt_versions_name', 'name'),
        sa.Index('ix_prompt_versions_stage', 'stage'),
        sa.Index('ix_prompt_versions_status', 'status'),
        sa.Index('ix_prompt_versions_parent_version_id', 'parent_version_id'),
        sa.Index('ix_prompt_versions_created_at', 'created_at'),
    )
    
    # 创建 Pipeline 运行表
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('run_id', sa.String(36), nullable=False),
        sa.Column('research_question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('prompt_versions_used', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('final_report_id', sa.String(36), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_stacktrace', sa.Text(), nullable=True),
        sa.Column('failed_stage', sa.String(50), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('model_versions', sa.JSON(), nullable=True),
        sa.Column('software_version', sa.String(100), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['final_report_id'], ['reports.id'], ondelete='SET NULL'),
        sa.Index('ix_pipeline_runs_id', 'id'),
        sa.Index('ix_pipeline_runs_project_id', 'project_id'),
        sa.Index('ix_pipeline_runs_run_id', 'run_id'),
        sa.Index('ix_pipeline_runs_status', 'status'),
        sa.Index('ix_pipeline_runs_final_report_id', 'final_report_id'),
        sa.Index('ix_pipeline_runs_created_at', 'created_at'),
    )
    
    # 创建 Pipeline 阶段执行表
    op.create_table(
        'pipeline_stage_executions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('pipeline_run_id', sa.String(36), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('stage_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('model_parameters', sa.JSON(), nullable=True),
        sa.Column('prompt_used', sa.Text(), nullable=True),
        sa.Column('prompt_version_id', sa.String(36), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_stacktrace', sa.Text(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('cost_estimate', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_version_id'], ['prompt_versions.id'], ondelete='SET NULL'),
        sa.Index('ix_pipeline_stage_executions_id', 'id'),
        sa.Index('ix_pipeline_stage_executions_pipeline_run_id', 'pipeline_run_id'),
        sa.Index('ix_pipeline_stage_executions_stage', 'stage'),
        sa.Index('ix_pipeline_stage_executions_status', 'status'),
        sa.Index('ix_pipeline_stage_executions_prompt_version_id', 'prompt_version_id'),
        sa.Index('ix_pipeline_stage_executions_created_at', 'created_at'),
    )


def downgrade() -> None:
    op.drop_table('pipeline_stage_executions')
    op.drop_table('pipeline_runs')
    op.drop_table('prompt_versions')
