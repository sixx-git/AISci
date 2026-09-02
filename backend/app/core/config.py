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
    
    # 数据库配置（Meoo 云库优先读 SUPABASE_DB_URL，见 cloud_db.resolve_database_url）
    DATABASE_URL: str = "sqlite:///./data/aiscientist.db"
    # SQLite 场景下是否同步到 Supabase Storage（Meoo FREE 无 Postgres 直连时）
    AISCI_CLOUD_DB_SYNC: bool = True
    # 周期性把本地 SQLite 回写到 Storage 的间隔（秒）；默认 3 小时
    AISCI_CLOUD_DB_SYNC_INTERVAL_SEC: int = 10800
    
    # 千问 API 配置
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen3.6-plus"
    # 已废弃：与 QWEN_MODEL 合并，仅保留以兼容旧 .env
    QWEN_VL_MODEL: str = "qwen3.6-plus"
    # 强制 IPv4 访问百炼（部分网络 IPv6 SSL 会 UNEXPECTED_EOF）
    QWEN_FORCE_IPV4: bool = True
    
    # Mock LLM 模式：无需真实 QWEN_API_KEY 即可跑通 Pipeline
    USE_MOCK_LLM: bool = False

    # 迭代实验：默认启用 shaxiang 引擎（失败自动回退服务端 mock）
    AISCI_USE_SHAXIANG: bool = True

    # 联邦学习 Starter Pack（资源包挂载；非多机 runtime）
    AISCI_FL_PACK_ENABLED: bool = True
    AISCI_FL_LOCAL_PILOT_ENABLED: bool = True  # Phase4: 报告合成时可跑本地 FedAvg pilot
    # 联邦仿真后端（仅 federated_learning 模式；与通用沙箱隔离）
    AISCI_FL_SIM_ENABLED: bool = True
    AISCI_FL_SIM_DEFAULT_BACKEND: str = "local_pack"  # local_pack | flower | fedml
    AISCI_FL_FLOWER_ENABLED: bool = True
    AISCI_FL_FEDML_ENABLED: bool = True  # FedML 兼容仿真；可选 pip install fedml
    
    # 向量存储配置（主路径：Zvec 嵌入式向量库，按 project_id 分 Collection）
    # Chat 专用 Zvec Collection（与会话级临时文档 RAG 相关）
    VECTOR_STORE_PATH: str = "./storage/chat_vectors"
    VECTOR_INDEXES_PATH: str = "./storage/vector_indexes"
    VECTOR_BACKEND: str = "zvec"
    # Hugging Face 镜像（国内默认 hf-mirror，留空则走官方 huggingface.co）
    HF_ENDPOINT: str = "https://hf-mirror.com"
    # embedding 后端：sentence_transformers（本地）| qwen（DashScope API，复用 QWEN_API_KEY）
    EMBEDDING_BACKEND: str = "sentence_transformers"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    # 千问 embedding 向量维度（text-embedding-v3/v4 支持 1024/768/512 等；0=使用模型默认）
    EMBEDDING_DIMENSION: int = 0
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
    
    # 文献自动入库（Pipeline 文献挖掘阶段 — LLM 推荐模式）
    LITERATURE_IMPORT_MAX: int = 16
    LITERATURE_RECOMMEND_MAX: int = 12
    LITERATURE_MIN_VERIFIED: int = 4
    LITERATURE_SUPPLEMENT_API: bool = True
    LITERATURE_IMPORT_UNVERIFIED: bool = False
    # unverified 但有摘要时仍允许入库（摘要级证据 / 引用），默认开启
    LITERATURE_IMPORT_UNVERIFIED_WITH_ABSTRACT: bool = True
    # 自动 discovery 默认不下载 PDF（优先摘要建索引），避免串行 60s 超时拖到近 10 分钟
    LITERATURE_DISCOVERY_DOWNLOAD_PDF: bool = False
    # 已有可入库候选（含「unverified+摘要」）达到该数则跳过 API 补搜
    LITERATURE_SKIP_SUPPLEMENT_WHEN_IMPORTABLE: int = 1

    # 文献相关性门控（PaperQA 风格：论文门控 + chunk RCS；关闭则回退旧行为）
    LIT_RELEVANCE_GATE_ENABLED: bool = True
    LIT_PAPER_SCORE_CUTOFF: int = 6  # 论文 0–10，>= 才入库
    LIT_CHUNK_SCORE_CUTOFF: int = 5  # chunk RCS 0–10，>= 才进 facts 抽取
    LIT_RETRIEVE_CANDIDATE_K: int = 20  # 向量检索候选数（再经 RCS 截断）
    LIT_RCS_BATCH_SIZE: int = 12  # RCS 批量 LLM 每批 chunk 数（约 1～2 批覆盖候选）

    # 红蓝对抗后假设演化（Co-Scientist simplify/out_of_box；仅候选池，默认不覆盖主假设）
    HYPOTHESIS_EVOLUTION_ENABLED: bool = True
    HYPOTHESIS_EVOLUTION_TOP_K: int = 5
    HYPOTHESIS_EVOLUTION_STRATEGIES: str = "simplify,out_of_box"

    # 跨会话实验记忆（InternAgent 风格；独立 mem_store，不读写 iterative_experiments 投影）
    EXPERIMENT_MEMORY_SAVE_ENABLED: bool = True
    EXPERIMENT_MEMORY_RETRIEVE_ENABLED: bool = True
    EXPERIMENT_MEMORY_DIR: str = "./storage/experiment_memory"
    EXPERIMENT_MEMORY_TOP_K: int = 5
    EXPERIMENT_MEMORY_ALPHA: float = 0.5  # 1=关键词, 0=语义
    EXPERIMENT_MEMORY_AGGREGATION: str = "best"  # best | avg | last
    EXPERIMENT_MEMORY_IMPROVE_THRESHOLD: float = 0.05

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
        # 允许 .env 中存在 Meoo SUPABASE_*/MEOO_* 等未声明字段
        extra = "ignore"


@lru_cache()
def get_settings():
    # 将 backend/.env / 根 .env 注入 os.environ，供 cloud_db 等直接读取
    try:
        from dotenv import load_dotenv

        backend_root = Path(__file__).resolve().parents[2]
        load_dotenv(backend_root / ".env", override=False)
        load_dotenv(backend_root.parent / ".env", override=False)
    except Exception:
        pass

    # Meoo：有 SUPABASE_DB_URL 时覆盖 DATABASE_URL
    supabase_db = (os.environ.get("SUPABASE_DB_URL") or "").strip()
    if supabase_db:
        if supabase_db.startswith("postgres://"):
            supabase_db = "postgresql+psycopg2://" + supabase_db[len("postgres://") :]
        elif supabase_db.startswith("postgresql://") and "+psycopg" not in supabase_db:
            supabase_db = "postgresql+psycopg2://" + supabase_db[len("postgresql://") :]
        os.environ["DATABASE_URL"] = supabase_db

    settings = Settings()
    endpoint = (settings.HF_ENDPOINT or "").strip().rstrip("/")
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    return settings
