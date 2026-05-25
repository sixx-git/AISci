"""
使用 SQLite 初始化数据库表
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 确保能找到 app
sys.path.insert(0, os.path.dirname(__file__))

from app.models import Base, Project, Document, PipelineRun, PipelineStageExecution, PromptVersion

if __name__ == "__main__":
    print("正在使用 SQLite 初始化数据库...")
    
    # 使用 SQLite 数据库
    db_path = os.path.join(os.path.dirname(__file__), "test.db")
    DATABASE_URL = f"sqlite:///{db_path}"
    print(f"数据库路径: {db_path}")
    
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    print("所有数据库表创建成功！")
    
    # 测试查询
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # 检查表是否创建成功
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"创建的表: {tables}")
    
    db.close()
    print("初始化完成！")
