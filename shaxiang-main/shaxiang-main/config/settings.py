from dataclasses import dataclass, field
from dotenv import load_dotenv
import os
from pathlib import Path

# 项目根目录（基于此文件位置）
_PROJECT_ROOT = Path(__file__).parent.parent

@dataclass
class LLMConfig:
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    model: str = "qwen-plus"
    temperature: float = 0.3
    max_tokens: int = 4096

@dataclass
class StorageConfig:
    db_path: str = str(_PROJECT_ROOT / "data" / "experiments.db")

@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

def load_config() -> AppConfig:
    """从项目根目录的 .env 文件加载配置，项目 .env 优先于系统环境变量"""
    env_file = _PROJECT_ROOT / ".env"
    load_dotenv(env_file, override=True)
    
    # db_path: 如果是相对路径则基于项目根目录解析为绝对路径
    db_path = os.getenv("DB_PATH", "data/experiments.db")
    if not os.path.isabs(db_path):
        db_path = str(_PROJECT_ROOT / db_path)

    return AppConfig(
        llm=LLMConfig(
            base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "qwen-plus"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        ),
        storage=StorageConfig(db_path=db_path),
    )
