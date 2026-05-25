"""
数据库初始化脚本
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.database import create_tables
from app.core.config import get_settings

settings = get_settings()


def init_db():
    """初始化数据库"""
    print("=" * 60)
    print("   AI Scientist - 数据库初始化")
    print("=" * 60)
    print()
    print(f"数据库: {settings.DATABASE_URL}")
    print()
    print("正在创建数据库表...")
    
    # 创建所有表
    create_tables()
    
    print()
    print("[OK] 数据库表创建成功！")
    print()
    print("已创建的表:")
    print("  - projects (项目表)")
    print("  - documents (文档表)")
    print("  - research_projects (研究项目表)")
    print("  - chat_sessions (对话会话表)")
    print("  - chat_messages (对话消息表)")
    print()
    print("=" * 60)


if __name__ == "__main__":
    init_db()
