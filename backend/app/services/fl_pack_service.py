"""联邦学习 Starter Pack：加载资源、挂载到项目、本地 pilot（不接多机 runtime）。"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PACK_ROOT = Path(__file__).resolve().parents[2] / "data" / "reference" / "fl"


def fl_pack_root() -> Path:
    return _PACK_ROOT


def fl_pack_enabled() -> bool:
    try:
        from app.core.config import get_settings

        return bool(getattr(get_settings(), "AISCI_FL_PACK_ENABLED", True))
    except Exception:
        return True


def normalize_fl_setting(setting: Optional[str]) -> str:
    """归一为 hfl | vfl | both。"""
    raw = (setting or "").strip().lower().replace("-", "_")
    if raw in ("vfl", "vertical", "vertical_fl"):
        return "vfl"
    if raw in ("hfl", "horizontal", "horizontal_fl"):
        return "hfl"
    if raw in ("both", "all", "hfl+vfl"):
        return "both"
    return "both"


# 领域标签；fl_core 始终作为基础方法种子保留
FL_DOMAIN_ALIASES = {
    "core": "fl_core",
    "fl": "fl_core",
    "classic": "fl_core",
    "llm": "llm_ft",
    "llm_peft": "llm_ft",
    "fedllm": "llm_ft",
    "peft": "llm_ft",
    "大模型": "llm_ft",
    "care": "smart_care",
    "health": "smart_care",
    "healthcare": "smart_care",
    "elderly": "smart_care",
    "medical": "smart_care",
    "康养": "smart_care",
    "医疗": "smart_care",
    "traffic": "smart_transport",
    "transport": "smart_transport",
    "its": "smart_transport",
    "交通": "smart_transport",
    "finance": "finance_risk",
    "fin_risk": "finance_risk",
    "banking": "finance_risk",
    "金融": "finance_risk",
    "风控": "finance_risk",
    "edge": "edge_mobile",
    "mobile": "edge_mobile",
    "on_device": "edge_mobile",
    "终端": "edge_mobile",
    "边缘": "edge_mobile",
    "iot": "iot_industrial",
    "iiot": "iot_industrial",
    "industrial": "iot_industrial",
    "工业": "iot_industrial",
    "物联网": "iot_industrial",
    "dp": "privacy_crypto",
    "smc": "privacy_crypto",
    "mpc": "privacy_crypto",
    "differential_privacy": "privacy_crypto",
    "secure_aggregation": "privacy_crypto",
    "隐私": "privacy_crypto",
    "cv": "fl_cv",
    "vision": "fl_cv",
    "视觉": "fl_cv",
    "nlp": "fl_nlp",
    "language": "fl_nlp",
    "自然语言": "fl_nlp",
    "multilingual": "fl_multilingual",
    "multi_lingual": "fl_multilingual",
    "cross_lingual": "fl_multilingual",
    "多语言": "fl_multilingual",
    "跨语言": "fl_multilingual",
    "hetero_lora": "fl_lora_hetero",
    "heterogeneous_lora": "fl_lora_hetero",
    "lora_hetero": "fl_lora_hetero",
    "lora_heterogeneous": "fl_lora_hetero",
    "客户端lora": "fl_lora_hetero",
    "lora异构": "fl_lora_hetero",
    "blockchain": "fl_blockchain",
    "chain": "fl_blockchain",
    "区块链": "fl_blockchain",
    "rl": "fl_rl",
    "reinforcement": "fl_rl",
    "fedrl": "fl_rl",
    "强化学习": "fl_rl",
    "continual": "fl_continual",
    "incremental": "fl_continual",
    "持续学习": "fl_continual",
    "增量学习": "fl_continual",
}
ALWAYS_INCLUDE_DOMAINS = frozenset({"fl_core", ""})

DEFAULT_FL_DOMAINS = [
    "fl_core",
    "finance_risk",
    "smart_care",
    "edge_mobile",
    "iot_industrial",
    "smart_transport",
    "privacy_crypto",
    "fl_cv",
    "fl_nlp",
    "fl_multilingual",
    "fl_blockchain",
    "fl_rl",
    "fl_continual",
    "llm_ft",
    "fl_lora_hetero",
]


def normalize_fl_domain(domain: Optional[str]) -> str:
    raw = (domain or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return "fl_core"
    return FL_DOMAIN_ALIASES.get(raw, raw)


def normalize_fl_domains(domains: Optional[List[str]]) -> Optional[List[str]]:
    """None/空 = 不过滤（挂载全部领域）；否则返回归一化列表。"""
    if not domains:
        return None
    out: List[str] = []
    seen = set()
    for d in domains:
        n = normalize_fl_domain(str(d))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out or None


def _domain_matches(item_domain: Optional[str], want: Optional[List[str]]) -> bool:
    """want=None 表示全部；否则保留 fl_core + 选中领域。"""
    if want is None:
        return True
    item = normalize_fl_domain(item_domain)
    allowed = {normalize_fl_domain(d) for d in want} | ALWAYS_INCLUDE_DOMAINS
    return item in allowed


def _setting_matches(item_setting: Optional[str], want: str) -> bool:
    want_n = normalize_fl_setting(want)
    item_n = normalize_fl_setting(item_setting or "both")
    if want_n == "both" or item_n == "both":
        return True
    return item_n == want_n


class FlPackService:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else fl_pack_root()

    def available(self) -> bool:
        return (self.root / "manifest.json").is_file()

    def load_manifest(self) -> Dict[str, Any]:
        path = self.root / "manifest.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def summary(
        self, *, fl_setting: Optional[str] = None, domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        setting = normalize_fl_setting(fl_setting) if fl_setting else "both"
        dom = normalize_fl_domains(domains)
        m = self.load_manifest()
        facts = self.load_seed_facts(fl_setting=setting, domains=dom)
        scripts = self.load_scripts(fl_setting=setting)
        datasets = self.load_datasets(fl_setting=setting, domains=dom)
        return {
            "available": self.available(),
            "enabled": fl_pack_enabled(),
            "version": m.get("version"),
            "root": str(self.root),
            "fl_setting": setting,
            "domains": dom or m.get("domains") or DEFAULT_FL_DOMAINS,
            "papers": len(m.get("papers") or []),
            "seed_facts_count": len(facts),
            "datasets_count": len(datasets),
            "scripts_count": len(scripts),
            "datasets": len(datasets),
            "scripts": len(scripts),
            "runtime": m.get("runtime"),
            "mounted_label": f"FL Pack v{m.get('version') or '?'} · {setting.upper()}",
        }

    @staticmethod
    def normalize_seed_fact(raw: Dict[str, Any]) -> Dict[str, Any]:
        """对齐 ScienceFact / literature_facts 常用字段，避免下游丢弃。"""
        paper_id = str(raw.get("paper_id") or raw.get("external_id") or "seed").strip() or "seed"
        fact_id = str(raw.get("fact_id") or f"fl_seed_{paper_id}").strip()
        claim = str(raw.get("claim") or raw.get("content") or raw.get("fact_text") or "").strip()
        title = str(raw.get("title") or raw.get("source_paper_title") or "").strip()
        doc_id = str(raw.get("document_id") or f"fl_pack_doc_{paper_id}")
        chunk_id = str(raw.get("source_chunk_id") or f"fl_pack_chunk_{fact_id}")
        quote = str(raw.get("quote") or raw.get("quote_text") or claim[:240])
        relevance = raw.get("relevance_score")
        if relevance is None:
            relevance = raw.get("relevance")
        try:
            relevance_f = float(relevance) if relevance is not None else 0.85
        except Exception:
            relevance_f = 0.85
        out = {
            **raw,
            "fact_id": fact_id,
            "content": claim or title or fact_id,
            "fact_text": str(raw.get("fact_text") or claim),
            "source_chunk_id": chunk_id,
            "document_id": doc_id,
            "source_paper_title": title or None,
            "quote_text": quote,
            "relevance_score": relevance_f,
            "source": "fl_starter_pack",
            "is_fl_pack_seed": True,
            "setting": normalize_fl_setting(str(raw.get("setting") or "both")),
            "domain": normalize_fl_domain(str(raw.get("domain") or "fl_core")),
            "year": raw.get("year"),
            "external_id": raw.get("external_id"),
            "method": raw.get("method"),
        }
        return out

    def load_seed_facts(
        self, *, fl_setting: Optional[str] = None, domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        path = self.root / "papers" / "seed_facts.json"
        if not path.is_file():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        facts = data.get("facts") if isinstance(data, dict) else data
        want = normalize_fl_setting(fl_setting) if fl_setting else "both"
        want_domains = normalize_fl_domains(domains)
        out: List[Dict[str, Any]] = []
        for f in facts or []:
            if not isinstance(f, dict):
                continue
            if not _setting_matches(f.get("setting"), want):
                continue
            if not _domain_matches(f.get("domain"), want_domains):
                continue
            # 攻击/后门综述默认仅 HFL（除非标 both）
            method = str(f.get("method") or "").lower()
            if want == "vfl" and "attack" in method and normalize_fl_setting(f.get("setting")) == "hfl":
                continue
            out.append(self.normalize_seed_fact(f))
        return out

    def load_datasets(
        self, *, fl_setting: Optional[str] = None, domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        try:
            import yaml  # type: ignore
        except Exception:
            yaml = None
        want = normalize_fl_setting(fl_setting) if fl_setting else "both"
        want_domains = normalize_fl_domains(domains)
        out: List[Dict[str, Any]] = []
        for rel in (self.load_manifest().get("datasets") or []):
            path = self.root / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            item: Dict[str, Any] = {}
            if yaml is not None:
                try:
                    item = yaml.safe_load(text) or {}
                except Exception:
                    item = {}
            if not item:
                item = {"_path": str(path), "raw": text[:2000]}
                for line in text.splitlines():
                    if ":" in line and not line.strip().startswith("#"):
                        k, _, v = line.partition(":")
                        k, v = k.strip(), v.strip()
                        if k and k not in item and not k.startswith("-"):
                            item[k] = v
            if not isinstance(item, dict):
                continue
            if not _setting_matches(item.get("setting"), want):
                continue
            if not _domain_matches(item.get("domain"), want_domains):
                continue
            item["_rel"] = rel
            item["_path"] = str(path)
            out.append(item)
        return out

    def load_scripts(self, *, fl_setting: Optional[str] = None) -> List[Dict[str, Any]]:
        want = normalize_fl_setting(fl_setting) if fl_setting else "both"
        scripts = []
        for s in self.load_manifest().get("scripts") or []:
            if not isinstance(s, dict):
                continue
            if not _setting_matches(s.get("setting"), want):
                continue
            # run_fedavg 入口对 VFL 项目降权：仍可列出，但默认模板优先非 entry
            rel = s.get("path") or ""
            path = self.root / rel
            scripts.append(
                {
                    **s,
                    "id": Path(rel).stem if rel else s.get("recommended_when"),
                    "abs_path": str(path) if path.is_file() else rel,
                    "exists": path.is_file(),
                    "setting": normalize_fl_setting(s.get("setting") or "both"),
                }
            )
        return scripts

    def list_script_templates(
        self, *, fl_setting: Optional[str] = None, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """UI 可选模板：含脚本正文预览。"""
        out = []
        for s in self.load_scripts(fl_setting=fl_setting):
            rel = str(s.get("path") or "")
            if "run_fedavg_pilot" in rel:
                continue  # 服务入口，不对用户展示为模板
            path = Path(s.get("abs_path") or (self.root / rel))
            content = ""
            if path.is_file():
                content = path.read_text(encoding="utf-8")
            out.append(
                {
                    "id": s.get("id") or Path(rel).stem,
                    "path": rel,
                    "abs_path": str(path),
                    "setting": s.get("setting"),
                    "recommended_when": s.get("recommended_when") or "",
                    "exists": path.is_file(),
                    "content": content,
                    "preview": content[:600],
                }
            )
            if len(out) >= limit:
                break
        return out

    def read_script_content(self, script_id_or_path: str) -> Dict[str, Any]:
        key = (script_id_or_path or "").strip().replace("\\", "/")
        for s in self.load_scripts(fl_setting="both"):
            rel = str(s.get("path") or "").replace("\\", "/")
            stem = Path(rel).stem
            if key in {rel, stem, s.get("id"), Path(rel).name}:
                path = Path(s.get("abs_path") or (self.root / rel))
                if not path.is_file():
                    raise FileNotFoundError(f"脚本不存在: {rel}")
                return {
                    "id": stem,
                    "path": rel,
                    "abs_path": str(path),
                    "recommended_when": s.get("recommended_when"),
                    "setting": s.get("setting"),
                    "content": path.read_text(encoding="utf-8"),
                }
        raise FileNotFoundError(f"未知 FL 脚本模板: {script_id_or_path}")

    def load_failure_cases(self, *, fl_setting: Optional[str] = None) -> List[Dict[str, Any]]:
        want = normalize_fl_setting(fl_setting) if fl_setting else "both"
        out = []
        for rel in self.load_manifest().get("failure_cases") or []:
            path = self.root / rel
            if not path.is_file():
                continue
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(item, dict) and _setting_matches(item.get("setting"), want):
                out.append(item)
        return out

    def load_checklists_text(self, *, fl_setting: Optional[str] = None) -> str:
        want = normalize_fl_setting(fl_setting) if fl_setting else "both"
        parts = []
        for rel in self.load_manifest().get("checklists") or []:
            name = Path(rel).name.lower()
            if want == "hfl" and "vfl" in name:
                continue
            if want == "vfl" and "hfl" in name:
                continue
            path = self.root / rel
            if path.is_file():
                parts.append(path.read_text(encoding="utf-8"))
        return "\n\n".join(parts)

    def dataset_guidance_hints(
        self, *, fl_setting: Optional[str] = None, domains: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        hints = []
        for ds in self.load_datasets(fl_setting=fl_setting, domains=domains):
            schema = ds.get("schema") or []
            if isinstance(schema, str):
                schema = [schema]
            hints.append(
                {
                    "name": ds.get("name") or ds.get("id") or "FL dataset",
                    "dataset_name": ds.get("name") or ds.get("id"),
                    "source_platform": "FL Starter Pack",
                    "download_url": ds.get("download_url") or "",
                    "description": ds.get("description") or "",
                    "source_type": "federated_benchmark",
                    "upload_requirement": ds.get("upload_requirement") or "optional",
                    "required_columns": list(schema)[:12],
                    "setting": ds.get("setting") or "both",
                    "domain": normalize_fl_domain(str(ds.get("domain") or "fl_core")),
                    "partition": ds.get("partition") or {},
                    "pilot_subset": ds.get("pilot_subset") or {},
                }
            )
        return hints

    def scripts_context_for_llm(self, limit: int = 6, *, fl_setting: Optional[str] = None) -> str:
        lines = ["[FL Starter Pack 参考脚本 — 单机模拟，可复制到 analysis_script]"]
        for s in self.load_scripts(fl_setting=fl_setting)[:limit]:
            lines.append(
                f"- {s.get('recommended_when')}: `{s.get('abs_path') or s.get('path')}`"
                f" (setting={s.get('setting')})"
            )
        fails = self.load_failure_cases(fl_setting=fl_setting)[:3]
        if fails:
            lines.append("[常见失败/反例]")
            for f in fails:
                lines.append(f"- {f.get('id')}: {f.get('summary')}")
        return "\n".join(lines)

    def build_project_config_blob(
        self, *, fl_setting: Optional[str] = None, domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        setting = normalize_fl_setting(fl_setting or "both")
        dom = normalize_fl_domains(domains)
        facts = self.load_seed_facts(fl_setting=setting, domains=dom)
        scripts = self.load_scripts(fl_setting=setting)
        datasets = self.dataset_guidance_hints(fl_setting=setting, domains=dom)
        return {
            "enabled": True,
            "version": (self.load_manifest() or {}).get("version"),
            "pack_root": str(self.root),
            "fl_setting": setting,
            "domains": dom or (self.load_manifest() or {}).get("domains") or DEFAULT_FL_DOMAINS,
            "seed_facts": facts,
            "seed_facts_count": len(facts),
            "dataset_hints": datasets,
            "datasets_count": len(datasets),
            "scripts": [
                {
                    "id": s.get("id"),
                    "path": s.get("path"),
                    "abs_path": s.get("abs_path"),
                    "setting": s.get("setting"),
                    "recommended_when": s.get("recommended_when"),
                    "exists": s.get("exists"),
                }
                for s in scripts
            ],
            "scripts_count": len(scripts),
            "script_templates": self.list_script_templates(fl_setting=setting, limit=3),
            "failure_cases": self.load_failure_cases(fl_setting=setting),
            "checklists_excerpt": self.load_checklists_text(fl_setting=setting)[:4000],
            "runtime": "local_simulation_only",
            "summary": self.summary(fl_setting=setting, domains=dom),
        }

    def mount_to_project_config(
        self,
        existing: Optional[Dict[str, Any]] = None,
        *,
        fl_setting: Optional[str] = None,
        domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        cfg = dict(existing or {})
        setting = normalize_fl_setting(fl_setting or cfg.get("fl_setting") or "both")
        dom = normalize_fl_domains(domains if domains is not None else cfg.get("fl_domains"))
        cfg["fl_setting"] = setting
        if dom is not None:
            cfg["fl_domains"] = dom
        cfg["fl_pack"] = self.build_project_config_blob(fl_setting=setting, domains=dom)
        cfg["fl_pack_mounted"] = True
        return cfg

    @staticmethod
    def get_seed_facts_from_project_config(config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(config, dict):
            return []
        pack = config.get("fl_pack") or {}
        facts = pack.get("seed_facts") or []
        return [f for f in facts if isinstance(f, dict)]

    @staticmethod
    def get_fl_setting_from_config(config: Optional[Dict[str, Any]]) -> str:
        if not isinstance(config, dict):
            return "both"
        return normalize_fl_setting(
            config.get("fl_setting") or (config.get("fl_pack") or {}).get("fl_setting")
        )

    @staticmethod
    def infer_fl_context_from_columns(
        columns: Optional[List[str]],
        *,
        project_mode: str = "general",
    ) -> Dict[str, Any]:
        """由列名规则填充轻量 fl_context（不跑仿真）。"""
        from app.core.project_modes import empty_fl_context

        ctx = empty_fl_context()
        cols = [str(c).strip() for c in (columns or []) if c]
        lower = {c.lower().replace(" ", "_"): c for c in cols}
        ctx["project_mode"] = project_mode
        ctx["detected_fields"] = cols

        client_keys = [lower[k] for k in ("client_id", "client", "user_id") if k in lower]
        party_keys = [lower[k] for k in ("party_id", "party") if k in lower]
        align_keys = [
            lower[k]
            for k in ("entity_id", "aligned_id", "sample_id", "subject_id")
            if k in lower
        ]
        metric_keys = [
            lower[k]
            for k in (
                "global_accuracy",
                "local_accuracy",
                "communication_rounds",
                "communication_cost_mb",
                "aligned_sample_rate",
                "privacy_budget",
            )
            if k in lower
        ]
        ctx["client_fields"] = client_keys
        ctx["party_fields"] = party_keys
        ctx["alignment_keys"] = align_keys
        ctx["metrics_fields"] = metric_keys
        ctx["metrics_candidates"] = metric_keys

        if party_keys or (align_keys and not client_keys):
            ctx["fl_setting"] = "vertical_fl"
            ctx["federated_setting"] = "vertical"
            ctx["parties"] = party_keys or ["feature_party", "label_party"]
            ctx["feature_parties"] = party_keys[:1] or ["feature_party"]
            ctx["label_party"] = "label_party"
        elif client_keys:
            ctx["fl_setting"] = "horizontal_fl"
            ctx["federated_setting"] = "horizontal"
        elif project_mode == "federated_learning":
            ctx["fl_setting"] = "unknown"
            ctx["federated_setting"] = "unknown"
        return ctx

    def run_local_fedavg_pilot(self, *, timeout_sec: int = 60) -> Dict[str, Any]:
        """Phase4：本地 FedAvg pilot，返回 metrics dict。"""
        entry = self.root / "scripts" / "run_fedavg_pilot.py"
        direct = self.root / "scripts" / "hfl_fedavg_pilot.py"
        script = entry if entry.is_file() else direct
        if not script.is_file():
            return {"success": False, "error": "fedavg script missing"}
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(script.parent),
                check=False,
            )
            raw = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            metrics: Dict[str, Any] = {}
            for line in reversed(raw.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        metrics = json.loads(line)
                        break
                    except Exception:
                        continue
            if not metrics and (script.parent / "_last_fedavg_metrics.json").is_file():
                metrics = json.loads(
                    (script.parent / "_last_fedavg_metrics.json").read_text(encoding="utf-8")
                )
            return {
                "success": bool(metrics) and proc.returncode == 0,
                "execution_mode": "local_fedavg_pilot",
                "metrics": metrics,
                "stdout_preview": raw[:800],
                "returncode": proc.returncode,
            }
        except Exception as exc:
            logger.warning("[FL Pack] FedAvg pilot failed: %s", exc)
            return {"success": False, "error": str(exc), "execution_mode": "local_fedavg_pilot"}

    def maybe_attach_vfl_gate(
        self,
        fl_context: Dict[str, Any],
        datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from app.core.iterative_science import check_vfl_alignment_gate

        return check_vfl_alignment_gate(fl_context or {}, datasets)

    def build_seed_citation_map(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_doc: Dict[str, Dict[str, Any]] = {}
        for f in facts:
            if not isinstance(f, dict):
                continue
            doc_id = str(f.get("document_id") or "")
            if not doc_id:
                continue
            entry = by_doc.setdefault(
                doc_id,
                {
                    "document_id": doc_id,
                    "paper_title": f.get("source_paper_title") or f.get("title"),
                    "title": f.get("source_paper_title") or f.get("title"),
                    "year": f.get("year"),
                    "external_id": f.get("external_id"),
                    "source_type": "fl_starter_pack",
                    "fact_ids": [],
                    "chunk_ids": [],
                },
            )
            fid = f.get("fact_id")
            cid = f.get("source_chunk_id")
            if fid and fid not in entry["fact_ids"]:
                entry["fact_ids"].append(fid)
            if cid and cid not in entry["chunk_ids"]:
                entry["chunk_ids"].append(cid)
        return list(by_doc.values())


_svc: Optional[FlPackService] = None


def get_fl_pack_service() -> FlPackService:
    global _svc
    if _svc is None:
        _svc = FlPackService()
    return _svc
