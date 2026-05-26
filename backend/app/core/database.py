"""
数据库配置
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

# 延迟初始化
engine = None
SessionLocal = None

# 导入 Base 以及所有模型（必须在 create_tables 前导入，确保 SQLAlchemy 注册所有表）
from app.models.core import Base
# 触发所有模型的类注册，保证 Base.metadata.create_all() 能建全表
import app.models.project  # noqa: F401 - Project, Document, Chunk, Report, RunLog
import app.models.research  # noqa: F401 - Hypothesis, ExperimentDesign, Evidence
import app.models.pipeline  # noqa: F401 - PipelineRun, PipelineStageExecution, PromptVersion
import app.models.chat  # noqa: F401 - ChatMessage


def init_db():
    """初始化数据库引擎"""
    global engine, SessionLocal
    
    if engine is None:
        connect_args = {}
        # SQLite 特殊配置
        if settings.DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            # 自动创建数据目录
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            echo=settings.DEBUG  # 调试模式下打印 SQL
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return engine, SessionLocal


def get_db():
    """获取数据库会话"""
    # 确保数据库已初始化
    if SessionLocal is None:
        init_db()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """创建所有数据库表"""
    if engine is None:
        init_db()
    Base.metadata.create_all(bind=engine)
