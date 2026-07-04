"""数据文件格式注册表 — 上传扩展名与解析路由。"""
from __future__ import annotations

import os
from typing import Optional, Set, Tuple

TABULAR_EXTENSIONS: Set[str] = {
    ".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".jsonl",
}

CHEMISTRY_EXTENSIONS: Set[str] = {
    ".sdf", ".mol", ".smi", ".smiles",
}

COMPRESSED_CHEMISTRY_SUFFIXES: Tuple[str, ...] = (
    ".sdf.gz", ".mol.gz", ".smi.gz", ".smiles.gz",
)

COMPRESSED_TABULAR_SUFFIXES: Tuple[str, ...] = (
    ".csv.gz", ".tsv.gz", ".json.gz", ".jsonl.gz",
)

ARCHIVE_EXTENSIONS: Set[str] = {".zip"}

FITS_EXTENSIONS: Set[str] = {".fits", ".fit", ".fts"}

COMPRESSED_FITS_SUFFIXES: Tuple[str, ...] = (
    ".fits.gz", ".fit.gz", ".fts.gz",
)

PARSEABLE_EXTENSIONS: Set[str] = (
    TABULAR_EXTENSIONS | CHEMISTRY_EXTENSIONS | ARCHIVE_EXTENSIONS | FITS_EXTENSIONS
)


def detect_file_format(filename: str) -> str:
    """返回格式标识，用于选择解析 Skill。"""
    name = (filename or "").lower().strip()
    for suffix in COMPRESSED_CHEMISTRY_SUFFIXES:
        if name.endswith(suffix):
            return suffix.replace(".", "_").strip("_")  # sdf_gz
    for suffix in COMPRESSED_FITS_SUFFIXES:
        if name.endswith(suffix):
            return "fits_gz"
    for suffix in COMPRESSED_TABULAR_SUFFIXES:
        if name.endswith(suffix):
            return suffix.replace(".", "_").strip("_")
    ext = os.path.splitext(name)[1]
    if ext in CHEMISTRY_EXTENSIONS:
        return ext.lstrip(".")
    if ext in TABULAR_EXTENSIONS:
        return "tabular"
    if ext == ".zip":
        return "zip"
    if ext in FITS_EXTENSIONS:
        return "fits"
    if ext == ".gz":
        return "gz_unknown"
    return "unknown"


def is_fits_format(filename: str) -> bool:
    fmt = detect_file_format(filename)
    return fmt in {"fits", "fits_gz"}


def is_chemistry_format(filename: str) -> bool:
    fmt = detect_file_format(filename)
    return fmt in {
        "sdf", "mol", "smi", "smiles",
        "sdf_gz", "mol_gz", "smi_gz", "smiles_gz",
    }


def is_allowed_upload_filename(filename: str) -> bool:
    name = (filename or "").lower().strip()
    if not name:
        return False
    for suffix in COMPRESSED_CHEMISTRY_SUFFIXES + COMPRESSED_TABULAR_SUFFIXES + COMPRESSED_FITS_SUFFIXES:
        if name.endswith(suffix):
            return True
    ext = os.path.splitext(name)[1]
    return ext in (PARSEABLE_EXTENSIONS | {".gz"})


def file_extension_for_upload(filename: str) -> str:
    """用于校验的主扩展名（含复合后缀）。"""
    name = (filename or "").lower().strip()
    for suffix in COMPRESSED_CHEMISTRY_SUFFIXES + COMPRESSED_TABULAR_SUFFIXES + COMPRESSED_FITS_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return os.path.splitext(name)[1].lower()


def collect_parseable_files(root_dir: str) -> list[str]:
    """递归收集目录内可解析文件。"""
    found: list[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if is_allowed_upload_filename(name) and detect_file_format(name) != "gz_unknown":
                found.append(full)

    def _priority(path: str) -> tuple:
        fmt = detect_file_format(os.path.basename(path))
        order = {
            "tabular": 0, "csv": 0, "tsv": 0, "json": 1, "jsonl": 2,
            "fits": 2, "fits_gz": 2,
            "sdf": 3, "sdf_gz": 3, "mol": 4, "mol_gz": 4,
            "smi": 5, "smiles": 5, "smi_gz": 5,
        }
        base = order.get(fmt, 50)
        try:
            size = -os.path.getsize(path)
        except OSError:
            size = 0
        return (base, size)

    found.sort(key=_priority)
    return found
