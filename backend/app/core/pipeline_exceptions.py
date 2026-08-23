"""Pipeline 控制流异常"""


class HitlGatePause(Exception):
    """Teaching HITL Gate 暂停 — 非失败，等待人工确认后继续。"""

    def __init__(self, stage_key: str = ""):
        self.stage_key = stage_key
        super().__init__(f"HITL gate paused at {stage_key}")


class UserPause(Exception):
    """用户手动暂停 — 非失败，当前阶段结束后生效，可续跑。"""

    def __init__(self, stage_key: str = ""):
        self.stage_key = stage_key
        super().__init__(f"User pause after {stage_key}")


class SingleStageRerunComplete(Exception):
    """仅重跑单个阶段完成 — 保留上游与下游（父 run）结果。"""

    def __init__(self, stage_key: str = ""):
        self.stage_key = stage_key
        super().__init__(f"Single stage rerun completed at {stage_key}")


class LiteratureNotFoundError(Exception):
    """文献挖掘未找到可用文献 — 终止后续 Pipeline 阶段。"""

    def __init__(self, message: str = "未找到相关文献，工作流已停止"):
        self.message = message
        super().__init__(message)
