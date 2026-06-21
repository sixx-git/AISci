"""多源数据查找共享工具"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Set


LINK_PATTERNS = {
    "github": re.compile(r"https?://(?:www\.)?github\.com/[\w\-./]+", re.I),
    "zenodo": re.compile(r"https?://(?:www\.)?zenodo\.org/[\w\-./]+", re.I),
    "figshare": re.compile(r"https?://(?:www\.)?figshare\.com/[\w\-./]+", re.I),
    "dryad": re.compile(r"https?://(?:datadryad\.org|dryad\.org)/[\w\-./]+", re.I),
    "kaggle": re.compile(r"https?://(?:www\.)?kaggle\.com/[\w\-./]+", re.I),
    "huggingface": re.compile(r"https?://(?:www\.)?huggingface\.co/datasets/[\w\-./]+", re.I),
    "generic_http": re.compile(r"https?://[\w\-./?=&%+#]+", re.I),
}

DATA_KEYWORDS = [
    "data availability", "supplementary material", "dataset", "benchmark",
    "appendix", "table", "figure", "code availability", "source code",
    "数据可用", "补充材料", "数据集", "基准",
]

TABLE_CAPTION_RE = re.compile(
    r"(?:Table|TABLE|表)\s*(\d+)[:\.]?\s*(.{0,200})",
    re.I,
)
FIGURE_CAPTION_RE = re.compile(
    r"(?:Figure|Fig\.|FIGURE|图)\s*(\d+)[:\.]?\s*(.{0,200})",
    re.I,
)

GENERAL_STANDARD_COLUMNS = [
    "accuracy", "f1_score", "auc", "rmse", "mae",
    "dataset_name", "method", "metric", "value",
]

FL_STANDARD_COLUMNS = [
    "method", "dataset_name", "num_clients", "client_id", "non_iid_type",
    "non_iid_degree", "participation_rate", "communication_rounds",
    "communication_cost_mb", "global_accuracy", "local_accuracy", "f1_score",
    "auc", "client_drift", "convergence_round", "privacy_budget", "aligned_sample_rate",
]


def new_id(prefix: str = "df") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def normalize_col(name: str) -> str:
    return re.sub(r"\s+", "_", (name or "").strip().lower().replace("-", "_"))


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls = set()
    for pattern in LINK_PATTERNS.values():
        urls.update(pattern.findall(text))
    return sorted(urls)


def detect_tables_in_text(text: str) -> List[Dict[str, Any]]:
    found = []
    for m in TABLE_CAPTION_RE.finditer(text or ""):
        found.append({"table_number": m.group(1), "caption": m.group(2).strip()})
    return found


def detect_figures_in_text(text: str) -> List[Dict[str, Any]]:
    found = []
    for m in FIGURE_CAPTION_RE.finditer(text or ""):
        found.append({"figure_number": m.group(1), "caption": m.group(2).strip()})
    return found


def match_column_mapping(columns: Iterable[str], standard: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    norm_cols = {normalize_col(c): c for c in columns}
    used_orig: Set[str] = set()

    for std in standard:
        nc = normalize_col(std)
        if nc in norm_cols:
            orig = norm_cols[nc]
            mapping[orig] = std
            used_orig.add(orig)

    for std in standard:
        nc = normalize_col(std)
        for col_norm, col_orig in norm_cols.items():
            if col_orig in used_orig:
                continue
            if col_norm == nc or col_norm.endswith(f"_{nc}") or col_norm.startswith(f"{nc}_"):
                mapping[col_orig] = std
                used_orig.add(col_orig)
                break

    return mapping
