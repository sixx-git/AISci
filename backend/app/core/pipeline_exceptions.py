"""Pipeline 控制流异常"""


class HitlGatePause(Exception):
    """Teaching HITL Gate 暂停 — 非失败，等待人工确认后继续。"""

    def __init__(self, stage_key: str = ""):
        self.stage_key = stage_key
        super().__init__(f"HITL gate paused at {stage_key}")
