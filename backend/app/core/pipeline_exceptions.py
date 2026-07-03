"""Pipeline 控制流异常"""


class HitlGatePause(Exception):
    """Teaching HITL Gate 暂停 — 非失败，等待人工确认后继续。"""

    def __init__(self, stage_key: str = ""):
        self.stage_key = stage_key
        super().__init__(f"HITL gate paused at {stage_key}")


class DataUploadPause(Exception):
    """一键报告模式 — 外部数据需用户下载上传后暂停。"""

    def __init__(self, pending_count: int = 0):
        self.pending_count = pending_count
        super().__init__(f"Data upload required ({pending_count} pending)")


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
