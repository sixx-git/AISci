"""
数据库配置
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

# 延迟初始化
engine = None
SessionLocal = None
Base = declarative_base()


def init_db():
    """初始化数据库引擎"""
    global engine, SessionLocal
    
    if engine is None:
        connect_args = {}
        # SQLite 特殊配置
        if settings.DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        
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
