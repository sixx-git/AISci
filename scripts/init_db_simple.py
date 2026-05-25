"""
简化版数据库初始化脚本
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.core.database import create_tables, init_db
from app.core.config import get_settings


def main():
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
    print("    数据库引擎初始化成功")
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
        'reports',
        'run_logs',
    ]
    
    print()
    print("已创建的表:")
    for table in sorted(tables):
        is_expected = "  OK" if table in expected_tables else "  ?"
        print(f"    {is_expected} {table}")
    
    print()
    print("[3/3] 验证表结构...")
    all_ok = True
    for expected_table in expected_tables:
        if expected_table not in tables:
            print(f"    缺少表: {expected_table}")
            all_ok = False
        else:
            columns = [col['name'] for col in inspector.get_columns(expected_table)]
            print(f"    OK {expected_table} ({len(columns)} 列)")
    
    print()
    if all_ok:
        print("=" * 70)
        print("   数据库初始化成功！")
        print("=" * 70)
    else:
        print("=" * 70)
        print("   数据库初始化完成，但有一些问题")
        print("=" * 70)
    
    print()
    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
