"""
配置模块 — 管理 DashScope API 连接和流水线参数。

用法:
    1. 复制 .env.example 为 .env，填入 DASHSCOPE_API_KEY
    2. 或在代码中通过 Config(api_key="sk-xxx") 显式传入
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# DashScope (Qwen) 兼容 OpenAI SDK，base_url 指向 DashScope 端点
# ---------------------------------------------------------------------------
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 默认模型选择
# 评分表生成需要高质量输出，建议使用更强的模型
DEFAULT_RUBRIC_MODEL = "qwen3.6-plus"       # 评分表生成
DEFAULT_SCORING_MODEL = "qwen3.6-plus"      # 自动评分
DEFAULT_EXTRACT_MODEL = "qwen3.6-plus"      # 要点提取

# 评分表生成参数（基于人工样例统计优化）
# 参考 claim_verification 样例: IA=15, SR=25, Synth=10
TARGET_INFO_ITEMS = (14, 18)       # 信息获取层目标条数范围
TARGET_REASON_ITEMS = (22, 26)     # 科学推理层目标条数范围
TARGET_SYNTH_ITEMS = (8, 12)       # 报告综合层目标条数范围
# role 比例目标（参考人工样例分布，控制 Critical 不超过 35%）
ROLE_RATIO = {"Critical": 0.20, "Mandatory": 0.55, "Standard": 0.25}


@dataclass
class Config:
    """流水线全局配置。"""

    api_key: str = ""
    base_url: str = DASHSCOPE_BASE_URL

    # 模型选择
    rubric_model: str = DEFAULT_RUBRIC_MODEL
    scoring_model: str = DEFAULT_SCORING_MODEL
    extract_model: str = DEFAULT_EXTRACT_MODEL

    # 任务元数据
    task_id: str = ""
    task_type: str = "claim_verification"    # literature_review | claim_verification | data_analysis
    subject: str = ""
    query: str = ""

    # 路径
    source_dir: str = ""       # 原始 PDF/数据文件所在目录
    output_dir: str = "./output"

    # 评分表生成控制
    target_info_items: tuple = TARGET_INFO_ITEMS
    target_reason_items: tuple = TARGET_REASON_ITEMS
    target_synth_items: tuple = TARGET_SYNTH_ITEMS
    role_ratio: dict = field(default_factory=lambda: dict(ROLE_RATIO))

    # 高级参数
    temperature: float = 0.3
    max_retries: int = 4
    timeout: int = 360
    verbose: bool = True

    def __post_init__(self):
        """自动从环境变量或 .env 文件加载 API key。"""
        if not self.api_key:
            # 尝试从 .env 文件加载（兼容 DASHSCOPE / QWEN）
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("DASHSCOPE_API_KEY=") or line.startswith("QWEN_API_KEY="):
                        self.api_key = line.split("=", 1)[1].strip().strip("'\"")
                        if self.api_key:
                            break
            # 回退到环境变量
            if not self.api_key:
                self.api_key = (
                    os.environ.get("DASHSCOPE_API_KEY", "")
                    or os.environ.get("QWEN_API_KEY", "")
                )

        if not self.api_key:
            raise ValueError(
                "未找到 DASHSCOPE_API_KEY / QWEN_API_KEY。请在 .env 文件中设置，"
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

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """从 YAML 配置文件加载。"""
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save_yaml(self, path: str):
        """保存当前配置到 YAML。"""
        import yaml
        data = {k: getattr(self, k) for k in self.__dataclass_fields__}
        # 处理不可序列化的字段
        data.pop("api_key", None)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
