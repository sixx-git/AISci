from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
from pathlib import Path
import os


def _resolve_env_file() -> str:
    """
    按优先级查找 .env 文件:
    1. backend/.env（推荐位置，与 uvicorn 启动目录一致）
    2. 项目根目录 .env（兼容旧版）
    3. 环境变量 AISCI_ENV_FILE 直接指定
    """
    import os

    env_from_env = os.environ.get("AISCI_ENV_FILE")
    if env_from_env and Path(env_from_env).exists():
        return env_from_env

    backend_root = Path(__file__).resolve().parent.parent.parent
    backend_env = backend_root / ".env"
    if backend_env.exists():
        return str(backend_env)

    project_root = backend_root.parent
    project_env = project_root / ".env"
    if project_env.exists():
        return str(project_env)

    return str(backend_env)


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
    QWEN_MODEL: str = "qwen3.7-max"
    # 已废弃：与 QWEN_MODEL 合并，仅保留以兼容旧 .env
    QWEN_VL_MODEL: str = "qwen3.7-max"
    
    # Mock LLM 模式：无需真实 QWEN_API_KEY 即可跑通 Pipeline
    USE_MOCK_LLM: bool = False
    
    # 向量存储配置（主路径：Zvec 嵌入式向量库，按 project_id 分 Collection）
    # Chat 专用 Zvec Collection（与会话级临时文档 RAG 相关）
    VECTOR_STORE_PATH: str = "./storage/chat_vectors"
    VECTOR_INDEXES_PATH: str = "./storage/vector_indexes"
    VECTOR_BACKEND: str = "zvec"
    # Hugging Face 镜像（国内默认 hf-mirror，留空则走官方 huggingface.co）
    HF_ENDPOINT: str = "https://hf-mirror.com"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    
    # 文件上传配置
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    UPLOAD_CHUNK_SIZE: int = 8 * 1024 * 1024  # 8MB 流式写盘块大小
    LARGE_FILE_THRESHOLD_BYTES: int = 50 * 1024 * 1024  # 超过则跳过 pandas 全表 analyze
    LARGE_FILE_NO_COPY_BYTES: int = 50 * 1024 * 1024  # 沙箱超过则引用原路径，不 copy2
    DATA_PROBE_SAMPLE_ROWS: int = 1000  # DuckDB/采样探查行数
    SANDBOX_TIMEOUT_T0_SEC: int = 120
    SANDBOX_TIMEOUT_T1_SEC: int = 300
    SANDBOX_TIMEOUT_T2_SEC: int = 600
    ALLOWED_EXTENSIONS: str = "txt,pdf,docx,md,csv"
    
    # arXiv 配置
    ARXIV_TIMEOUT: int = 15
    ARXIV_MAX_RETRIES: int = 2
    ARXIV_ENABLE_FALLBACK: bool = True
    ARXIV_FALLBACK_DATA_PATH: str = "./data/arxiv_fallback.json"
    ARXIV_HTTP_PROXY: str = ""
    ARXIV_HTTPS_PROXY: str = ""
    
    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    
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
        env_file = _resolve_env_file()
        case_sensitive = True


@lru_cache()
def get_settings():
    settings = Settings()
    endpoint = (settings.HF_ENDPOINT or "").strip().rstrip("/")
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    return settings
