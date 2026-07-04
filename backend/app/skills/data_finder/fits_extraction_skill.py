"""天文 FITS 文件抽取 — JWST/MUSE 等光谱立方与表格扩展。"""
from __future__ import annotations

import csv
import gzip
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.skills.base import BaseSkill, SkillResult
from app.skills.data_finder._utils import new_id
from app.skills.data_finder.file_format_registry import detect_file_format, is_fits_format

DEFAULT_MAX_ROWS = 10_000
HEADER_KEYS = (
    "TELESCOP", "INSTRUME", "FILTER", "GRATING", "DETECTOR",
    "OBJECT", "RA_TARG", "DEC_TARG", "WAVELMIN", "WAVELMAX",
    "NAXIS1", "NAXIS2", "NAXIS3", "BUNIT", "DATE-OBS",
)


def _open_fits_path(file_path: str, filename: str):
    try:
        from astropy.io import fits
    except ImportError as exc:
        raise ValueError("解析 FITS 需要安装 astropy：pip install astropy") from exc

    def _needs_scaled_load(path: str) -> bool:
        with fits.open(path, memmap=True, lazy_load_hdus=True) as peek:
            for hdu in peek:
                hdr = getattr(hdu, "header", None)
                if hdr is not None and any(k in hdr for k in ("BZERO", "BSCALE", "BLANK")):
                    return True
        return False

    def _open(path: str):
        use_memmap = not _needs_scaled_load(path)
        try:
            return fits.open(path, memmap=use_memmap)
        except ValueError as exc:
            if "memmap" in str(exc).lower() or "BZERO" in str(exc) or "BSCALE" in str(exc):
                return fits.open(path, memmap=False)
            raise

    fmt = detect_file_format(filename or os.path.basename(file_path))
    if fmt == "fits_gz" or (file_path.lower().endswith(".gz") and is_fits_format(filename)):
        with gzip.open(file_path, "rb") as gz_in:
            tmp_path = file_path + ".decompressed.fits"
            with open(tmp_path, "wb") as out:
                shutil.copyfileobj(gz_in, out)
            try:
                return _open(tmp_path), tmp_path
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
    return _open(file_path), None


def _hdu_catalog_row(idx: int, hdu) -> Dict[str, Any]:
    name = (hdu.name or f"HDU_{idx}").strip() or f"HDU_{idx}"
    shape = getattr(hdu, "shape", None)
    dtype_label = ""
    if getattr(hdu, "columns", None):
        dtype_label = "BINTABLE"
    elif hasattr(hdu, "header") and "BITPIX" in hdu.header:
        dtype_label = f"BITPIX={hdu.header['BITPIX']}"
    return {
        "hdu_index": idx,
        "hdu_name": name,
        "data_shape": str(shape) if shape else "",
        "data_dtype": dtype_label,
        "is_table": bool(getattr(hdu, "columns", None)),
    }


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _header_summary(hdu) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key in HEADER_KEYS:
        if key in hdu.header:
            out[key.lower()] = str(hdu.header[key])[:120]
    return out


def _write_csv(
    rows: List[Dict[str, Any]],
    columns: List[str],
    *,
    source_title: str,
    output_dir: str,
    caption: str,
    extraction_method: str,
) -> Dict[str, Any]:
    table_id = new_id("tbl")
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, f"{table_id}.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in columns})
    return {
        "table_id": table_id,
        "source_title": source_title,
        "caption": caption,
        "csv_path": csv_path,
        "columns": columns,
        "row_count": len(rows),
        "quality_score": min(1.0, 0.55 + 0.05 * min(len(columns), 8)),
        "extraction_method": extraction_method,
        "source_type": "fits_file",
    }


def _table_from_bintable(hdu, name: str, max_rows: int) -> Optional[Dict[str, Any]]:
    data = hdu.data
    if data is None or not getattr(hdu, "columns", None):
        return None
    colnames = list(hdu.columns.names)
    if not colnames:
        return None
    rows: List[Dict[str, Any]] = []
    n = min(len(data), max_rows)
    for i in range(n):
        row = {}
        for col in colnames:
            val = data[col][i]
            if isinstance(val, (bytes, np.bytes_)):
                row[col] = val.decode("utf-8", errors="replace")
            elif isinstance(val, np.generic):
                row[col] = val.item() if val.shape == () else str(val)
            else:
                row[col] = val
        rows.append(row)
    return {"columns": colnames, "rows": rows, "caption": f"FITS BINTABLE {name}"}


def _table_from_image_2d(arr: np.ndarray, name: str, max_rows: int) -> Dict[str, Any]:
    arr = np.asarray(arr, dtype=float)
    finite = np.isfinite(arr)
    if not finite.any():
        raise ValueError(f"FITS 扩展 {name} 无有效数值")
    ny, nx = arr.shape
    step = max(1, int(np.ceil((ny * nx) / max_rows)))
    rows: List[Dict[str, Any]] = []
    for y in range(0, ny, max(1, int(np.sqrt(step)))):
        for x in range(0, nx, max(1, int(np.sqrt(step)))):
            val = _safe_float(arr[y, x])
            if val is None:
                continue
            rows.append({"y": y, "x": x, "value": val})
            if len(rows) >= max_rows:
                break
        if len(rows) >= max_rows:
            break
    return {
        "columns": ["y", "x", "value"],
        "rows": rows,
        "caption": f"FITS 2D 采样 {name} ({ny}x{nx})",
    }


def _table_from_cube_3d(arr: np.ndarray, name: str, max_rows: int) -> Dict[str, Any]:
    """3D 光谱立方：逐波长/切片统计（适用于 JWST s3d 等）。"""
    arr = np.asarray(arr, dtype=float)
    if arr.ndim != 3:
        raise ValueError("期望 3D 数据立方")
    nz, ny, nx = arr.shape
    return _cube_slice_stats(nz, ny, nx, name, max_rows, lambda z: arr[z])


def _table_from_cube_hdu(hdu, name: str, max_rows: int) -> Dict[str, Any]:
    """按切片读取 3D HDU，避免在目录阶段预加载整立方。"""
    shape = getattr(hdu, "shape", None)
    if not shape or len(shape) != 3:
        raise ValueError("期望 3D 数据立方")
    nz, ny, nx = shape
    data = hdu.data
    if data is None:
        raise ValueError(f"FITS 扩展 {name} 无数据")

    def _slice(z: int) -> np.ndarray:
        return np.asarray(data[z], dtype=float)

    return _cube_slice_stats(nz, ny, nx, name, max_rows, _slice)


def _cube_slice_stats(
    nz: int,
    ny: int,
    nx: int,
    name: str,
    max_rows: int,
    slice_fn,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for z in range(min(nz, max_rows)):
        slice_arr = slice_fn(z)
        finite = slice_arr[np.isfinite(slice_arr)]
        if finite.size == 0:
            continue
        rows.append({
            "slice_index": z,
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "median": float(np.median(finite)),
            "spatial_y": ny // 2,
            "spatial_x": nx // 2,
            "center_pixel_value": _safe_float(slice_arr[ny // 2, nx // 2]),
        })
    return {
        "columns": [
            "slice_index", "mean", "std", "min", "max", "median",
            "spatial_y", "spatial_x", "center_pixel_value",
        ],
        "rows": rows,
        "caption": f"FITS 3D 立方切片统计 {name} ({nz}x{ny}x{nx})",
    }


_PREFERRED_DATA_HDUS = ("SCI", "DATA", "FLUX", "INTENSITY")


def extract_fits_tables(
    file_path: str,
    *,
    source_title: str,
    output_dir: str,
    filename: Optional[str] = None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> List[Dict[str, Any]]:
    fname = filename or os.path.basename(file_path)
    hdul, tmp_path = _open_fits_path(file_path, fname)
    tables: List[Dict[str, Any]] = []
    try:
        catalog_rows: List[Dict[str, Any]] = [
            _hdu_catalog_row(idx, hdu) for idx, hdu in enumerate(hdul)
        ]

        meta = _header_summary(hdul[0])
        if meta:
            for row in catalog_rows:
                row.update(meta)

        tables.append(_write_csv(
            catalog_rows,
            list(catalog_rows[0].keys()) if catalog_rows else ["hdu_index"],
            source_title=source_title,
            output_dir=output_dir,
            caption=f"FITS HDU 目录 ({fname})",
            extraction_method="fits_catalog",
        ))

        data_hdu_indices = list(range(len(hdul)))
        data_hdu_indices.sort(
            key=lambda i: (
                0 if (hdul[i].name or "").strip().upper() in _PREFERRED_DATA_HDUS else 1,
                i,
            ),
        )
        for idx in data_hdu_indices:
            hdu = hdul[idx]
            name = (hdu.name or f"HDU_{idx}").strip() or f"HDU_{idx}"
            parsed: Optional[Dict[str, Any]] = None
            try:
                if getattr(hdu, "columns", None) and hdu.data is not None:
                    parsed = _table_from_bintable(hdu, name, max_rows)
                elif getattr(hdu, "shape", None):
                    shape = hdu.shape
                    if len(shape) == 3:
                        parsed = _table_from_cube_hdu(hdu, name, max_rows)
                    elif len(shape) == 2 and hdu.data is not None:
                        parsed = _table_from_image_2d(np.asarray(hdu.data), name, max_rows)
                    elif len(shape) == 1 and hdu.data is not None:
                        arr = np.asarray(hdu.data)
                        n = min(arr.size, max_rows)
                        parsed = {
                            "columns": ["index", "value"],
                            "rows": [{"index": i, "value": _safe_float(arr[i])} for i in range(n)],
                            "caption": f"FITS 1D {name}",
                        }
            except Exception:
                continue

            if parsed and parsed.get("rows"):
                tables.append(_write_csv(
                    parsed["rows"],
                    parsed["columns"],
                    source_title=source_title,
                    output_dir=output_dir,
                    caption=parsed["caption"],
                    extraction_method="fits_data",
                ))
                break
        data_tables = [t for t in tables if t.get("extraction_method") == "fits_data"]
        if data_tables:
            return [data_tables[0], tables[0]] if tables else data_tables
    finally:
        hdul.close()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return tables


class FitsExtractionSkill(BaseSkill):
    name = "FitsExtraction"
    description = "从 FITS 文件导出 HDU 目录与可分析 CSV（含 3D 光谱立方切片统计）"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        file_path = input_data.get("file_path", "")
        source_title = input_data.get("source_title", "")
        output_dir = input_data.get("output_dir", "")
        filename = input_data.get("filename") or os.path.basename(file_path or "")
        max_rows = int(input_data.get("max_rows") or DEFAULT_MAX_ROWS)

        if not file_path or not os.path.exists(file_path):
            result.add_error("FITS 文件不存在")
            result.data = {"tables": []}
            return result

        if not is_fits_format(filename):
            result.add_error("非 FITS 格式")
            result.data = {"tables": []}
            return result

        try:
            tables = extract_fits_tables(
                file_path,
                source_title=source_title,
                output_dir=output_dir,
                filename=filename,
                max_rows=max_rows,
            )
        except Exception as exc:
            result.add_error(str(exc))
            result.data = {"tables": [], "errors": [str(exc)]}
            return result

        result.data = {"tables": tables}
        if not tables:
            result.add_warning("未能从 FITS 解析出可用表格")
        return result
