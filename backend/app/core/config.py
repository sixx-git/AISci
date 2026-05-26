from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # 应用基础配置
    APP_NAME: str = "AI Scientist"
    DEBUG: bool = True
    VERSION: str = "0.1.0"
    
    # 后端服务配置
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./data/aiscientist.db"
    
    # 千问 API 配置
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-max"
    
    # 向量存储配置
    VECTOR_STORE_PATH: str = "./storage/faiss_index"
    VECTOR_INDEXES_PATH: str = "./storage/vector_indexes"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    
    # 文件上传配置
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE: int = 52428800
    ALLOWED_EXTENSIONS: str = "txt,pdf,docx,md,csv"
    
    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()
