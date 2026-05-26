"""
数据库初始化脚本
初始化 AI Scientist 数据库并创建所有表
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.core.database import create_tables, init_db
from app.core.config import get_settings
from app.models import (
    Project,
    Document,
    Chunk,
    Hypothesis,
    ExperimentDesign,
    Evidence,
    Report,
    RunLog,
)


def init_database():
    """初始化数据库"""
    settings = get_settings()
    
    print("=" * 70)
    print("   AI Scientist - 数据库初始化")
    print("=" * 70)
    print()
    print(f"数据库 URL: {settings.DATABASE_URL}")
    print()
    
    # 初始化数据库引擎
    print("[1/3] 初始化数据库引擎...")
    engine, _ = init_db()
    print("    [OK] 数据库引擎初始化成功")
    print()
    
    # 创建所有表
    print("[2/3] 创建数据库表...")
    create_tables()
    
    # 检查表是否创建成功
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    expected_tables = [
        'projects',
        'documents',
        'chunks',
        'hypotheses',
        'experiment_designs',
        'evidences',
        'reports',
        'run_logs',
        'pipeline_runs',
        'pipeline_stage_executions',
        'prompt_versions',
        'chat_sessions',
        'chat_messages',
        'research_projects',
        'small_validations',
    ]
    
    print()
    print("已创建的表:")
    for table in sorted(tables):
        is_expected = "[OK]" if table in expected_tables else "?"
        print(f"    {is_expected} {table}")
    
    print()
    print("[3/3] 验证表结构...")
    all_ok = True
    for expected_table in expected_tables:
        if expected_table not in tables:
            print(f"    [MISS] 缺少表: {expected_table}")
            all_ok = False
        else:
            columns = [col['name'] for col in inspector.get_columns(expected_table)]
            print(f"    [OK] {expected_table} ({len(columns)} 列)")
    
    print()
    if all_ok:
        print("=" * 70)
        print("   [OK] 数据库初始化成功！")
        print("=" * 70)
    else:
        print("=" * 70)
        print("   [MISS] 数据库初始化完成，但有一些问题")
        print("=" * 70)
    
    print()
    return all_ok


def create_sample_data():
    """创建示例数据"""
    from app.core.database import SessionLocal
    from datetime import datetime
    
    print()
    print("=" * 70)
    print("   创建示例数据")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # 创建示例项目
        sample_project = Project(
            name="AI 研究示例项目",
            description="这是一个用于演示的 AI 研究项目",
            research_topic="探索机器学习在医疗领域的应用",
            keywords="机器学习,医疗,AI",
            status="draft",
            created_by="system",
        )
        db.add(sample_project)
        db.flush()
        
        # 创建示例文档
        sample_document = Document(
            project_id=sample_project.id,
            filename="sample_paper.pdf",
            file_path="./storage/documents/sample_paper.pdf",
            file_type="pdf",
            file_size=1024000,
            title="机器学习在医疗诊断中的应用",
            authors="张三,李四,王五",
            abstract="本文探讨了机器学习在医疗诊断中的最新应用...",
            doc_type="research_paper",
            status="uploaded",
        )
        db.add(sample_document)
        db.flush()
        
        # 创建示例日志
        sample_log = RunLog(
            project_id=sample_project.id,
            level="info",
            category="system",
            message="示例项目已创建",
            success=True,
        )
        db.add(sample_log)
        
        db.commit()
        
        print("[OK] 示例数据创建成功！")
        print(f"  - 项目 ID: {sample_project.id}")
        print(f"  - 文档 ID: {sample_document.id}")
        print()
        
    except Exception as e:
        db.rollback()
        print(f"[MISS] 创建示例数据失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Scientist 数据库初始化工具")
    parser.add_argument("--with-sample", action="store_true", help="同时创建示例数据")
    
    args = parser.parse_args()
    
    success = init_database()
    
    if success and args.with_sample:
        create_sample_data()
    
    sys.exit(0 if success else 1)
