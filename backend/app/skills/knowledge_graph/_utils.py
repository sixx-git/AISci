"""知识图谱共享工具"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

ENTITY_ALIASES = {
    "fedavg": "FedAvg",
    "federated averaging": "FedAvg",
    "federated_averaging": "FedAvg",
    "fedprox": "FedProx",
    "scaffold": "SCAFFOLD",
    "fedmd": "FedMD",
    "feddf": "FedDF",
    "splitnn": "SplitNN",
    "non-iid": "Non-IID",
    "non_iid": "Non-IID",
}

METHOD_PATTERNS = [
    r"\b(FedAvg|FedProx|SCAFFOLD|FedMD|FedDF|SplitNN|FedNova|FedPer|pFedMe|Ditto|FedBN|HeteroFL)\b",
    r"\b(CNN|ResNet|Transformer|GNN|Graph Neural Network|Random Forest|SVM|XGBoost)\b",
]

DATASET_PATTERNS = [
    r"\b(CIFAR-10|CIFAR10|MNIST|ImageNet|FEMNIST|LEAF|Shakespeare|COCO|SQuAD)\b",
]

METRIC_PATTERNS = [
    r"\b(accuracy|f1[- ]?score|AUC|RMSE|MAE|global accuracy|communication cost|client drift)\b",
]


def new_node_id(prefix: str = "n") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def new_edge_id(prefix: str = "e") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def normalize_label(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    key = re.sub(r"\s+", " ", t.lower())
    return ENTITY_ALIASES.get(key, ENTITY_ALIASES.get(key.replace(" ", "_"), t))


def extract_by_patterns(text: str, patterns: List[str]) -> List[str]:
    found: List[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            label = normalize_label(m.group(1) if m.lastindex else m.group(0))
            if label and label not in found:
                found.append(label)
    return found


def merge_nodes(existing: Dict[str, Dict], node: Dict[str, Any]) -> Dict[str, Any]:
    label_key = f"{node.get('type')}::{normalize_label(node.get('label', '')).lower()}"
    if label_key in existing:
        en = existing[label_key]
        for sid in node.get("source_ids", []):
            if sid not in en.get("source_ids", []):
                en.setdefault("source_ids", []).append(sid)
        en["confidence"] = max(en.get("confidence", 0), node.get("confidence", 0))
        return en
    existing[label_key] = node
    return node
