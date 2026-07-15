"""
数据集格式自动识别模块 (DatasetProfiler)

支持:
- tabular: CSV/TXT 传感器与表格数据（原逻辑）
- image / audio: 媒体目录 + manifest，或 ImageFolder 风格（类别子目录）
"""
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd

from llm.client import LLMClient
from executors.dataset_profile import (
    DatasetProfile, FilenameParser, PathParser, SensorMerge,
)

logger = logging.getLogger(__name__)

TABULAR_EXTS = {".txt", ".csv", ".tsv", ".dat"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
MANIFEST_NAMES = {
    "labels.csv", "label.csv", "metadata.csv", "meta.csv",
    "train.csv", "val.csv", "test.csv", "annotations.csv",
    "labels.tsv", "metadata.tsv", "labels.json", "metadata.json",
}

PROFILE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "数据集名称"},
        "description": {"type": "string", "description": "简短描述"},
        "modality": {
            "type": "string",
            "description": "数据模态: tabular | image | audio | mixed",
        },
        "scan_pattern": {"type": "string", "description": "glob 扫描模式，如 '**/*.jpg' 或 '**/*.txt'"},
        "file_extensions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "文件扩展名，如 ['.jpg'] 或 ['.txt']",
        },
        "media_extensions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "媒体扩展名（image/audio）；tabular 可留空",
        },
        "manifest_pattern": {
            "type": "string",
            "description": "标签清单 glob，如 '**/labels.csv'；ImageFolder 无清单则留空",
        },
        "path_column": {
            "type": "string",
            "description": "manifest 中文件路径列名，默认 file_path",
        },
        "delimiter": {"type": "string", "description": "表格分隔符；媒体数据集可填 ','"},
        "has_header": {"type": "boolean", "description": "manifest/表格第一行是否为列名"},
        "column_names": {"type": "array", "items": {"type": "string"}},
        "comment_prefix": {"type": "string"},
        "skip_rows": {"type": "integer"},
        "filename_pattern": {"type": "string"},
        "filename_fields": {"type": "array", "items": {"type": "string"}},
        "path_components": {"type": "array", "items": {"type": "integer"}},
        "path_field_names": {"type": "array", "items": {"type": "string"}},
        "sensor_merge_enabled": {"type": "boolean"},
        "sensor_merge_key": {"type": "string"},
        "sensor_merge_columns": {"type": "array", "items": {"type": "string"}},
        "label_column": {"type": "string", "description": "标签列名；ImageFolder 常用 label"},
        "custom_rules": {"type": "object"},
    },
    "required": ["name", "description", "modality", "scan_pattern"],
}


class DatasetProfiler:
    """AI 驱动的数据集格式识别器（含多模态）"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_profile(
        self,
        directory_path: str,
        hypothesis_hint: str = "",
        max_sample_files: int = 5,
        max_lines_per_file: int = 20,
    ) -> DatasetProfile:
        root_dir = Path(directory_path)
        if not root_dir.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")

        tree_summary = self._sample_tree(root_dir)
        inventory = self._inventory_media(root_dir)
        file_samples = self._sample_files(root_dir, max_sample_files, max_lines_per_file, inventory)

        probe_results = []
        for sample in file_samples:
            abs_path = root_dir / sample["path"]
            probe = self._probe_file(str(abs_path), sample.get("kind", "tabular"))
            probe_results.append({"file": sample["path"], **probe})

        prompt = self._build_prompt(
            directory_path=str(root_dir),
            tree_summary=tree_summary,
            file_samples=file_samples,
            probe_results=probe_results,
            hypothesis_hint=hypothesis_hint,
            inventory=inventory,
        )

        raw_dict = self.llm.generate_structured(
            prompt=prompt,
            system_prompt=self._system_prompt(),
            output_schema=PROFILE_OUTPUT_SCHEMA,
            temperature=0.2,
        )

        profile = self._dict_to_profile(raw_dict, inventory)
        logger.info(
            "自动识别数据集格式: %s (modality=%s)",
            profile.name,
            profile.modality,
        )
        return profile

    # ==================== 采样与探测 ====================

    def _sample_tree(self, root_dir: Path, max_depth: int = 4) -> str:
        lines = []
        for item in sorted(root_dir.iterdir(), key=lambda p: p.name)[:40]:
            if item.is_dir():
                sub_items = list(item.iterdir())[:8]
                sub_names = [f"{s.name}/" if s.is_dir() else s.name for s in sub_items]
                if len(list(item.iterdir())) > 8:
                    sub_names.append("...")
                lines.append(f"  {item.name}/  ->  {', '.join(sub_names)}")
            else:
                lines.append(f"  {item.name}")
        return "\n".join(lines)

    def _inventory_media(self, root_dir: Path) -> dict:
        """统计目录中表格/图片/音频及 manifest 候选。"""
        counts = Counter()
        manifests = []
        examples = {"tabular": [], "image": [], "audio": []}

        for p in root_dir.rglob("*"):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            name_l = p.name.lower()
            if name_l in MANIFEST_NAMES or (
                ext in {".csv", ".tsv", ".json"} and any(
                    k in name_l for k in ("label", "meta", "annot", "train", "val", "test")
                )
            ):
                manifests.append(str(p.relative_to(root_dir)))
            if ext in TABULAR_EXTS:
                counts["tabular"] += 1
                if len(examples["tabular"]) < 3:
                    examples["tabular"].append(str(p.relative_to(root_dir)))
            elif ext in IMAGE_EXTS:
                counts["image"] += 1
                if len(examples["image"]) < 3:
                    examples["image"].append(str(p.relative_to(root_dir)))
            elif ext in AUDIO_EXTS:
                counts["audio"] += 1
                if len(examples["audio"]) < 3:
                    examples["audio"].append(str(p.relative_to(root_dir)))

        guessed = "tabular"
        if counts["image"] > counts["tabular"] and counts["image"] >= counts["audio"]:
            guessed = "image"
        elif counts["audio"] > counts["tabular"] and counts["audio"] >= counts["image"]:
            guessed = "audio"
        elif counts["image"] and counts["audio"]:
            guessed = "mixed"

        return {
            "counts": dict(counts),
            "manifests": manifests[:10],
            "examples": examples,
            "guessed_modality": guessed,
        }

    def _sample_files(
        self,
        root_dir: Path,
        max_files: int,
        max_lines: int,
        inventory: dict,
    ) -> list[dict]:
        samples: list[dict] = []

        # 优先采样 manifest（文本）
        for rel in inventory.get("manifests") or []:
            if len(samples) >= max_files:
                break
            p = root_dir / rel
            text = self._read_text_head(p, max_lines)
            if text is not None:
                samples.append({"path": rel, "content": text, "kind": "manifest"})

        # 再采样表格或媒体元信息
        guessed = inventory.get("guessed_modality") or "tabular"
        if guessed in ("image", "audio", "mixed"):
            media_kind = "image" if guessed == "image" else ("audio" if guessed == "audio" else "image")
            exts = IMAGE_EXTS if media_kind == "image" else AUDIO_EXTS
            if guessed == "mixed":
                exts = IMAGE_EXTS | AUDIO_EXTS
            media_files = [
                p for p in root_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in exts
            ]
            for p in self._diverse_select(media_files, root_dir, max(1, max_files - len(samples))):
                meta = self._probe_media(p, root_dir)
                samples.append({
                    "path": str(p.relative_to(root_dir)),
                    "content": meta.get("summary", ""),
                    "kind": meta.get("kind", "media"),
                })
        else:
            candidates = []
            for ext in TABULAR_EXTS:
                candidates.extend(root_dir.rglob(f"*{ext}"))
            exclude_names = {
                "readme", "license", "description", "datadescribe",
                ".pdf", ".md", "activity_labels", "features", "features_info",
            }
            candidates = [
                p for p in candidates
                if not any(ex in p.name.lower() for ex in exclude_names)
            ]
            for p in self._diverse_select(candidates, root_dir, max(1, max_files - len(samples))):
                text = self._read_text_head(p, max_lines)
                if text is not None:
                    samples.append({
                        "path": str(p.relative_to(root_dir)),
                        "content": text,
                        "kind": "tabular",
                    })

        if not samples and not any((inventory.get("counts") or {}).values()):
            raise ValueError(f"在 {root_dir} 中未找到表格或媒体数据文件")
        if not samples:
            # 仅有媒体计数但未取到样例时，用 inventory 摘要顶上
            samples.append({
                "path": "(inventory)",
                "content": str(inventory),
                "kind": "inventory",
            })
        return samples

    def _diverse_select(self, candidates: list[Path], root_dir: Path, max_files: int) -> list[Path]:
        if not candidates or max_files <= 0:
            return []
        dir_groups = defaultdict(list)
        for p in candidates:
            rel = p.relative_to(root_dir)
            parts = rel.parts[:2] if len(rel.parts) > 1 else rel.parts[:1]
            group_key = "/".join(parts[:-1]) if parts else "root"
            dir_groups[group_key].append(p)
        selected = []
        for group in sorted(dir_groups.keys()):
            if dir_groups[group]:
                selected.append(dir_groups[group][0])
            if len(selected) >= max_files:
                break
        if len(selected) < max_files:
            for group in sorted(dir_groups.keys()):
                files = [f for f in dir_groups[group] if f not in selected]
                if files:
                    selected.append(files[0])
                if len(selected) >= max_files:
                    break
        return selected

    @staticmethod
    def _read_text_head(path: Path, max_lines: int) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip("\n"))
            return "\n".join(lines)
        except Exception as e:
            logger.warning("读取样本失败 %s: %s", path, e)
            return None

    def _probe_media(self, path: Path, root_dir: Path) -> dict:
        ext = path.suffix.lower()
        kind = "image" if ext in IMAGE_EXTS else "audio"
        info = {
            "kind": kind,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
            "summary": f"media={kind} ext={ext} size_kb={round(path.stat().st_size / 1024, 1)}",
        }
        if kind == "image":
            try:
                from PIL import Image
                with Image.open(path) as im:
                    info["width"], info["height"] = im.size
                    info["mode"] = im.mode
                    info["summary"] += f" size={im.size} mode={im.mode}"
            except Exception as e:
                info["summary"] += f" (pil_unavailable: {e})"
        else:
            try:
                import wave
                if ext == ".wav":
                    with wave.open(str(path), "rb") as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        dur = frames / float(rate) if rate else 0
                        info["sample_rate"] = rate
                        info["duration_sec"] = round(dur, 3)
                        info["channels"] = wf.getnchannels()
                        info["summary"] += f" sr={rate} dur={dur:.2f}s ch={wf.getnchannels()}"
            except Exception as e:
                info["summary"] += f" (audio_meta_unavailable: {e})"
        return info

    def _probe_file(self, file_path: str, kind: str = "tabular") -> dict:
        path = Path(file_path)
        if not path.exists():
            return {"error": "文件不存在"}
        if kind in {"image", "audio", "media"}:
            return self._probe_media(path, path.parent)
        if kind == "inventory":
            return {"kind": "inventory"}

        result = {
            "kind": "tabular",
            "file_size_kb": round(path.stat().st_size / 1024, 1),
            "probed_delimiter": None,
            "probed_columns": None,
            "probed_has_header": None,
        }
        delimiters = [",", "\t", ";", " ", r"\s+"]
        candidates = []
        for sep in delimiters:
            try:
                df = pd.read_csv(
                    path, sep=sep, header=None,
                    engine="python", nrows=10, on_bad_lines="skip",
                )
                df = df.dropna(axis=1, how="all")
                cols = df.shape[1]
                if cols > 1:
                    candidates.append((sep, cols))
            except Exception:
                continue

        def sort_key(item):
            sep, cols = item
            return (sep in (" ", r"\s+"), -cols)

        if candidates:
            candidates.sort(key=sort_key)
            best_sep, best_cols = candidates[0]
            result["probed_delimiter"] = best_sep
            result["probed_columns"] = best_cols
            try:
                df = pd.read_csv(path, sep=best_sep, engine="python", nrows=3, on_bad_lines="skip")
                df = df.dropna(axis=1, how="all")
                first_row = df.iloc[0].astype(str)
                non_numeric = sum(1 for v in first_row if not self._is_numeric_str(v))
                result["probed_has_header"] = non_numeric > len(first_row) * 0.5
            except Exception:
                result["probed_has_header"] = False
        return result

    @staticmethod
    def _is_numeric_str(s: str) -> bool:
        try:
            float(s)
            return True
        except (ValueError, TypeError):
            return False

    # ==================== Prompt ====================

    def _system_prompt(self) -> str:
        return """你是数据工程专家，擅长识别表格、图片与音频数据集结构。

任务：根据目录统计与样本，推断 DatasetProfile。

模态规则:
- tabular: 主要为 CSV/TXT 数值表或传感器文件
- image: 主要为 jpg/png 等；可能有 labels.csv，或 ImageFolder（类别子目录/*.jpg）
- audio: 主要为 wav/mp3 等；常有 labels.csv / metadata.csv
- mixed: 图文/音表混合时使用

输出硬约束:
1. 只输出符合 Schema 的 JSON 数据实例（不要输出 Schema 自身）
2. image/audio 时: media_extensions 必填；path_column 默认 file_path；label_column 尽量给出
3. ImageFolder（无清单）: modality=image, manifest_pattern="", scan_pattern="**/*.{jpg,png,...}", path_field_names 用 label（父目录）
4. 有 labels.csv: 填写 manifest_pattern，并推断路径列名到 path_column
5. tabular 行为与以往一致（delimiter/has_header/filename_pattern 等）"""

    def _build_prompt(
        self,
        directory_path: str,
        tree_summary: str,
        file_samples: list[dict],
        probe_results: list[dict],
        hypothesis_hint: str,
        inventory: dict,
    ) -> str:
        parts = [
            f"## 数据集目录\n{directory_path}",
            "",
            "## 目录结构\n```",
            tree_summary,
            "```",
            "",
            "## 文件类型统计",
            f"- counts: {inventory.get('counts')}",
            f"- guessed_modality: {inventory.get('guessed_modality')}",
            f"- manifests: {inventory.get('manifests')}",
            f"- examples: {inventory.get('examples')}",
            "",
            "## 探测结果",
        ]
        for pr in probe_results:
            parts.append(f"- {pr}")

        parts.extend(["", "## 样本"])
        for sample in file_samples:
            parts.append(f"### {sample.get('kind')}: {sample['path']}")
            parts.append("```")
            parts.append(str(sample.get("content", ""))[:2000])
            parts.append("```")

        if hypothesis_hint:
            parts.extend(["", f"## 用户实验假设\n{hypothesis_hint}"])

        parts.extend(["", "请推断结构配置并输出 JSON。"])
        return "\n".join(parts)

    # ==================== 转换 ====================

    def _dict_to_profile(self, data: dict, inventory: dict = None) -> DatasetProfile:
        inventory = inventory or {}
        modality = (data.get("modality") or inventory.get("guessed_modality") or "tabular").lower()
        if modality not in {"tabular", "image", "audio", "mixed"}:
            modality = inventory.get("guessed_modality") or "tabular"

        media_exts = list(data.get("media_extensions") or [])
        file_exts = list(data.get("file_extensions") or [])
        if modality == "image" and not media_exts:
            media_exts = [".jpg", ".jpeg", ".png"]
        if modality == "audio" and not media_exts:
            media_exts = [".wav", ".mp3", ".flac"]
        if modality in {"image", "audio"} and not file_exts:
            file_exts = list(media_exts)

        scan = data.get("scan_pattern") or "**/*"
        if modality == "image" and scan in {"**/*", ""}:
            scan = "**/*.*"
        if modality == "audio" and scan in {"**/*", ""}:
            scan = "**/*.*"

        profile = DatasetProfile(
            name=data.get("name", "AutoDetected"),
            description=data.get("description", ""),
            modality=modality,
            scan_pattern=scan,
            file_extensions=file_exts,
            media_extensions=media_exts,
            manifest_pattern=data.get("manifest_pattern", "") or "",
            path_column=data.get("path_column") or "file_path",
            delimiter=data.get("delimiter", ","),
            has_header=data.get("has_header", True if modality != "tabular" else False),
            column_names=data.get("column_names", []) or [],
            comment_prefix=data.get("comment_prefix", "") or "",
            skip_rows=int(data.get("skip_rows") or 0),
            label_column=data.get("label_column", "") or ("label" if modality in {"image", "audio"} else ""),
        )

        # 若 inventory 有 manifest 而 LLM 没填，补上
        if modality in {"image", "audio"} and not profile.manifest_pattern:
            manifests = inventory.get("manifests") or []
            if manifests:
                profile.manifest_pattern = manifests[0]

        fp = data.get("filename_pattern", "")
        ff = data.get("filename_fields", [])
        if fp and ff:
            profile.filename_parser = FilenameParser(pattern=fp, fields=ff)

        pc = data.get("path_components", [])
        pfn = data.get("path_field_names", [])
        if pc and pfn and len(pc) == len(pfn):
            profile.path_parser = PathParser(path_components=pc, field_names=pfn)
        elif modality in {"image", "audio"} and not profile.manifest_pattern:
            # ImageFolder 默认：父目录为 label
            profile.path_parser = PathParser(path_components=[-2], field_names=["label"])
            if not profile.label_column:
                profile.label_column = "label"

        if data.get("sensor_merge_enabled", False):
            profile.sensor_merge = SensorMerge(
                enabled=True,
                merge_key=data.get("sensor_merge_key", "sensor"),
                merge_columns=data.get("sensor_merge_columns", []) or [],
            )

        profile.custom_rules = data.get("custom_rules", {}) or {}
        return profile
