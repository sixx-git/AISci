"""
主动协调建议数据模型

存储 CoordinatorAgent 的主动协调建议，包括：
- Pipeline 启动前的项目就绪检查
- 阶段间的执行策略建议
- Pipeline 停滞检测与提醒
- LLM 驱动的主动建议
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.models.core import Base


class CoordinatorAdvice(Base):
    """主动协调建议表"""
    __tablename__ = "coordinator_advice"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    # 建议类型：readiness, stage_strategy, stall_warning, llm_advice
    advice_type = Column(String(50), nullable=False, index=True)
    # 关联阶段（可选）
    stage = Column(String(50), nullable=True, index=True)
    # 严重程度：info, low, medium, high
    severity = Column(String(20), nullable=False, default="info")
    # 标题和详细内容
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    # 建议的补救动作
    suggestion = Column(String(100), nullable=True)
    # 关联数据（JSON）
    extra_data = Column(JSON, nullable=True)
    # 状态：pending, acknowledged, dismissed
    status = Column(String(20), nullable=False, default="pending", index=True)
    # 来源：proactive, llm_proactive
    source = Column(String(50), nullable=False, default="proactive")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = {'comment': '主动协调建议表'}


class ProactiveContext(Base):
    """主动协调上下文（缓存项目最近一次就绪检查结果）"""
    __tablename__ = "proactive_contexts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, unique=True, index=True)

    # 上次就绪检查结果
    last_readiness_check = Column(JSON, nullable=True)
    last_readiness_at = Column(DateTime(timezone=True), nullable=True)

    # 上次阶段建议
    last_stage_suggestion = Column(JSON, nullable=True)
    last_suggestion_at = Column(DateTime(timezone=True), nullable=True)

    # Pipeline 运行状态快照
    pipeline_snapshot = Column(JSON, nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = {'comment': '主动协调上下文表'}