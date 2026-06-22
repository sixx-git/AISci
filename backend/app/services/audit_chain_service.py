"""闭环审计链持久化 — storage/audit/{run_id}.jsonl"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
CHINA_TZ = timezone(timedelta(hours=8))


class AuditChainService:
    def __init__(self, storage_root: Optional[str] = None):
        self.storage_root = storage_root or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "..",
            "storage",
            "audit",
        )
        os.makedirs(self.storage_root, exist_ok=True)

    def _audit_path(self, run_id: str) -> str:
        safe_id = (run_id or "unknown").replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_root, f"{safe_id}.jsonl")

    def append_record(
        self,
        run_id: str,
        record_type: str,
        payload: Dict[str, Any],
        *,
        project_id: Optional[str] = None,
    ) -> None:
        if not run_id:
            return
        record = {
            "record_type": record_type,
            "run_id": run_id,
            "project_id": project_id,
            "at": datetime.now(CHINA_TZ).isoformat(),
            **payload,
        }
        path = self._audit_path(run_id)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            logger.warning("审计链写入失败 run=%s: %s", run_id, exc)

    def read_chain(self, run_id: str) -> List[Dict[str, Any]]:
        path = self._audit_path(run_id)
        if not os.path.exists(path):
            return []
        records: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def export_audit_bundle(
        self,
        run_id: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """导出完整审计包：jsonl 记录 + metadata 快照。"""
        meta = meta or {}
        chain = self.read_chain(run_id)
        return {
            "run_id": run_id,
            "exported_at": datetime.now(CHINA_TZ).isoformat(),
            "record_count": len(chain),
            "quality_trend": meta.get("quality_trend") or [],
            "closed_loop_events": meta.get("closed_loop_events") or [],
            "closed_loop_decisions": meta.get("closed_loop_decisions") or [],
            "audit_records": chain,
        }


_audit_chain_service: Optional[AuditChainService] = None


def get_audit_chain_service() -> AuditChainService:
    global _audit_chain_service
    if _audit_chain_service is None:
        _audit_chain_service = AuditChainService()
    return _audit_chain_service
