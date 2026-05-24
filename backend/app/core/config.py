from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "AI Scientist"
    DEBUG: bool = True
    VERSION: str = "0.1.0"
    
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    
    DATABASE_URL: str = "mysql+pymysql://user:password@localhost:3306/aiscientist"
    
    QWEN_API_KEY: str = ""
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-max"
    
    FAISS_INDEX_PATH: str = "./storage/faiss_index"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
