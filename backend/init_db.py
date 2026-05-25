"""
初始化数据库表
"""
from app.core.database import create_tables, init_db
from app.models.pipeline import PipelineRun, PipelineStageExecution, PromptVersion
from app.models import *

if __name__ == "__main__":
    print("正在初始化数据库...")
    init_db()
    create_tables()
    print("数据库表创建成功！")
