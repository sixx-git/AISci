"""
配置模块 -- 管理 DashScope API 连接和流水线参数。
数据分析报告评分表生成器专用版本。

用法:
    1. 复制 .env.example 为 .env，填入 DASHSCOPE_API_KEY
    2. 或在代码中通过 Config(api_key="sk-xxx") 显式传入
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# DashScope (Qwen) 兼容 OpenAI SDK，base_url 指向 DashScope 端点
# ---------------------------------------------------------------------------
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 默认模型选择
DEFAULT_RUBRIC_MODEL = "qwen3.7-max"       # 评分表生成
DEFAULT_SCORING_MODEL = "qwen3.7-max"      # 自动评分
DEFAULT_EXTRACT_MODEL = "qwen3.7-max"      # 要点提取


@dataclass
class Config:
    """流水线全局配置 -- 数据分析专用。"""

    api_key: str = ""
    base_url: str = DASHSCOPE_BASE_URL

    # 模型选择
    rubric_model: str = DEFAULT_RUBRIC_MODEL
    scoring_model: str = DEFAULT_SCORING_MODEL
    extract_model: str = DEFAULT_EXTRACT_MODEL

    # 任务元数据（task_type 固定为 data_analysis）
    task_id: str = ""
    task_type: str = "data_analysis"
    subject: str = ""
    query: str = ""

    # 路径
    source_dir: str = ""       # 原始数据文件所在目录
    output_dir: str = "./output"

    # 高级参数
    temperature: float = 0.3
    max_retries: int = 3
    timeout: int = 120
    verbose: bool = True

    def __post_init__(self):
        """自动从环境变量或 .env 文件加载 API key。"""
        if not self.api_key:
            # 尝试从 .env 文件加载
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("DASHSCOPE_API_KEY="):
                        self.api_key = line.split("=", 1)[1].strip().strip("'\"")
                        break
            # 回退到环境变量
            if not self.api_key:
                self.api_key = os.environ.get("DASHSCOPE_API_KEY", "")

        if not self.api_key:
            raise ValueError(
                "未找到 DASHSCOPE_API_KEY。请在 .env 文件中设置，"
                "或通过 Config(api_key='sk-xxx') 传入。"
            )

    def get_client(self):
        """返回 OpenAI 兼容客户端实例。"""
        from openai import OpenAI
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def to_task_meta(self) -> dict:
        """生成 task.json 的元数据部分。"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "subject": self.subject,
            "query": self.query,
        }
