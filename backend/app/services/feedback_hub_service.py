"""统一反馈中心 — 一处提交、多处生效"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))

VALID_SOURCES = {
    "hitl", "kg", "data_finder", "provenance", "literature", "user", "multimodal",
}
RERUN_TARGETS = {
    "literature": ["literature_mining"],
    "data_finder": ["data_acquisition"],
    "hypothesis": ["hypothesis_generation", "hypothesis_review"],
    "experiment": ["experiment_design", "small_validation"],
    "kg": ["knowledge_gap"],
    "full": ["literature_mining"],
}


class FeedbackHubService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.storage_root = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "feedback",
        )

    def _hub_path(self, project_id: str) -> str:
        directory = os.path.join(self.storage_root, project_id)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, "feedback_hub.json")

    def load_hub(self, project_id: str) -> Dict[str, Any]:
        path = self._hub_path(project_id)
        if not os.path.exists(path):
            return {"project_id": project_id, "entries": [], "global_constraints": []}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_hub(self, project_id: str, hub: Dict[str, Any]) -> str:
        path = self._hub_path(project_id)
        hub["updated_at"] = datetime.now(CHINA_TZ).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hub, f, ensure_ascii=False, indent=2, default=str)
        return path

    @staticmethod
    def _message_to_constraints(message: str, source: str, payload: Optional[Dict[str, Any]] = None) -> List[str]:
        constraints: List[str] = []
        msg = (message or "").strip()
        if msg:
            constraints.append(f"[{source}] {msg[:400]}")
        payload = payload or {}
        for key in ("correction", "expected_value", "column_name", "fact_id"):
            val = payload.get(key)
            if val:
                constraints.append(f"[{source}] {key}={val}")
        return constraints

    def submit_feedback(
        self,
        project_id: str,
        *,
        source: str,
        message: str,
        target: str = "hypothesis",
        payload: Optional[Dict[str, Any]] = None,
        trigger_rerun: bool = False,
    ) -> Dict[str, Any]:
        source = source if source in VALID_SOURCES else "user"
        hub = self.load_hub(project_id)
        constraints = self._message_to_constraints(message, source, payload)
        entry = {
            "id": str(uuid.uuid4()),
            "source": source,
            "message": message,
            "target": target,
            "payload": payload or {},
            "constraints": constraints,
            "trigger_rerun": trigger_rerun,
            "applied": False,
            "created_at": datetime.now(CHINA_TZ).isoformat(),
        }
        hub.setdefault("entries", []).append(entry)
        global_c = list(hub.get("global_constraints") or [])
        for c in constraints:
            if c not in global_c:
                global_c.append(c)
        hub["global_constraints"] = global_c[-50:]
        self.save_hub(project_id, hub)

        side_effects: Dict[str, Any] = {}

        rerun_stages = RERUN_TARGETS.get(target, []) if trigger_rerun else []
        return {
            "entry": entry,
            "global_constraints": hub["global_constraints"],
            "suggested_rerun_stages": rerun_stages,
            "side_effects": side_effects,
        }

    def get_active_constraints(self, project_id: str, *, mark_applied: bool = False) -> List[str]:
        hub = self.load_hub(project_id)
        constraints = list(hub.get("global_constraints") or [])
        if mark_applied:
            for entry in hub.get("entries") or []:
                if not entry.get("applied"):
                    entry["applied"] = True
            self.save_hub(project_id, hub)
        return constraints

    def list_entries(self, project_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        hub = self.load_hub(project_id)
        entries = list(hub.get("entries") or [])
        return entries[-limit:]


def get_feedback_hub_service(db: Optional[Session] = None) -> FeedbackHubService:
    return FeedbackHubService(db)
