"""将 SJTU 125 Questions 英文数据集翻译为中文版并写出平行文件。"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = ROOT / "output" / "sjtu-125-questions"
EN_JSON = DATASET_ROOT / "en" / "questions.json"
OUT_DIR = ROOT / "output"
CACHE = DATASET_ROOT / "zh" / ".translation-cache.json"

CATEGORY_ZH: dict[str, str] = {
    "Mathematical Sciences": "数学科学",
    "Chemistry": "化学",
    "Medicine & Health": "医学与健康",
    "Biology": "生物学",
    "Astronomy": "天文学",
    "Physics": "物理学",
    "Engineering & Materials Science": "工程与材料科学",
    "Information Science": "信息科学",
    "Neuroscience": "神经科学",
    "Ecology": "生态学",
    "Energy Science": "能源科学",
    "Artificial Intelligence": "人工智能",
    "Unknown": "未分类",
}

EXPECTED_OUTPUTS_ZH = {
    "hypothesis": "假设",
    "experiment_design": "实验设计",
    "report": "研究报告",
}

SOURCE_BOOKLET_ZH = (
    "《125 个科学问题：探索与发现》"
    "（上海交通大学 × Science/AAAS，2021）"
)


def build_file_description_zh(category_zh: str, hint: str, context_zh: str) -> str:
    ctx = (context_zh or "").strip()[:280]
    if ctx:
        return f"领域：{category_zh}。{hint}。背景摘要：{ctx}"
    return f"领域：{category_zh}。{hint}。"


def _extract_domain_hint(en_desc: str) -> str:
    """从英文 file_description 提取已有中文数据提示部分。"""
    if "。" in en_desc:
        parts = en_desc.split("。")
        for p in parts:
            if "数据集" in p or "数据" in p:
                return p.strip()
    return "相关学科开放数据与文献"


def translate_batch_llm(items: list[dict]) -> list[dict]:
    from app.services.qwen_client import qwen_structured_chat

    payload = [
        {
            "id": r["id"],
            "research_question": r["research_question"],
            "context": (r.get("context") or "")[:500],
        }
        for r in items
    ]
    prompt = (
        "将以下科研问题数据集条目翻译为简体中文。"
        "保持学术语气，专有名词可保留英文并在必要时加中文。"
        "返回 JSON 数组，每项包含 id、question_name、research_question、context。"
        "research_question 须以问号结尾。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    schema_example = {
        "items": [
            {
                "id": "sjtu_q_001",
                "question_name": "素数为何如此特殊",
                "research_question": "素数为何如此特殊？",
                "context": "（中文背景摘要）",
            }
        ]
    }
    result = qwen_structured_chat(
        prompt=prompt,
        schema_example=schema_example,
        temperature=0.2,
        prompt_version="sjtu_125_zh_v1",
        system_prompt="你是科技翻译专家，将英文学术问题译为准确流畅的简体中文。",
    )
    if isinstance(result, list):
        return result
    for key in ("items", "translations", "results", "data"):
        if isinstance(result.get(key), list):
            return result[key]
    raise ValueError(f"LLM 返回格式异常: {list(result.keys()) if isinstance(result, dict) else type(result)}")


def load_cache() -> dict[str, dict]:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, dict]) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_records(en_records: list[dict], *, use_llm: bool = True) -> list[dict]:
    cache = load_cache()
    batch_size = 8
    if use_llm:
        for i in range(0, len(en_records), batch_size):
            batch = en_records[i : i + batch_size]
            need = [r for r in batch if r["id"] not in cache]
            if not need:
                continue
            try:
                translated = translate_batch_llm(need)
                for row in translated:
                    cache[row["id"]] = row
                save_cache(cache)
                print(f"  已翻译 {min(i + batch_size, len(en_records))}/{len(en_records)}")
            except Exception as exc:
                print(f"LLM 翻译失败（批次 {i // batch_size + 1}）: {exc}", file=sys.stderr)
                if not cache:
                    raise
                print("使用已有缓存继续…", file=sys.stderr)
                break

    zh_records: list[dict] = []
    for row in en_records:
        cat_en = row.get("category") or "Unknown"
        cat_zh = CATEGORY_ZH.get(cat_en, cat_en)
        hint = _extract_domain_hint(row.get("file_description") or "")
        tr = cache.get(row["id"])
        if tr:
            q_name = tr.get("question_name") or row["question_name"]
            rq = tr.get("research_question") or row["research_question"]
            ctx_zh = tr.get("context") or ""
        else:
            q_name = row["question_name"]
            rq = row["research_question"]
            ctx_zh = row.get("context") or ""

        if not rq.endswith("？"):
            rq = rq.rstrip("?") + "？"

        zh_records.append(
            {
                "id": row["id"],
                "index": row["index"],
                "question_name": q_name,
                "research_question": rq,
                "file_description": build_file_description_zh(cat_zh, hint, ctx_zh),
                "category": cat_zh,
                "category_en": cat_en,
                "domain": cat_zh,
                "context": ctx_zh,
                "page_num": row.get("page_num"),
                "source": row.get("source"),
                "source_booklet": SOURCE_BOOKLET_ZH,
                "tags": [cat_zh, "开放问题", "sjtu_125"],
                "pipeline_mode_suggested": "discovery",
                "expected_outputs": [
                    EXPECTED_OUTPUTS_ZH.get(k, k) for k in (row.get("expected_outputs") or [])
                ],
                "research_question_en": row.get("research_question"),
                "question_name_en": row.get("question_name"),
            }
        )
    return zh_records


def write_zh_outputs(records: list[dict], out_dir: Path) -> None:
    dataset_root = out_dir / "sjtu-125-questions"
    dataset_dir = dataset_root / "zh"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    (dataset_dir / "questions.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (dataset_dir / "questions.jsonl").open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "id",
        "index",
        "question_name",
        "research_question",
        "file_description",
        "category",
        "category_en",
        "page_num",
        "context",
        "research_question_en",
    ]
    with (dataset_dir / "questions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        by_cat[row["category"]].append(row)

    cat_dir = dataset_dir / "by_category"
    cat_dir.mkdir(exist_ok=True)
    for cat, rows in by_cat.items():
        safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", cat).strip("_")
        (cat_dir / f"{safe}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    counts = Counter(r["category"] for r in records)
    readme = [
        "# SJTU 125 Questions（简体中文）",
        "",
        "英文版 `../en/questions.json` 的简体中文平行数据集。",
        "",
        f"- 总条目: **{len(records)}**",
        "- 主文件: `questions.json` / `questions.jsonl` / `questions.csv`",
        "",
        "## 字段说明",
        "",
        "| 字段 | 说明 |",
        "|------|------|",
        "| `question_name` / `research_question` | 中文问题 |",
        "| `research_question_en` | 英文原题（对照） |",
        "| `category` | 中文学科名 |",
        "| `category_en` | 英文学科名 |",
        "| `file_description` | 中文数据/领域描述 |",
        "| `context` | 中文背景段落 |",
        "",
        "## 学科分布",
        "",
    ]
    for cat_zh in CATEGORY_ZH.values():
        if cat_zh == "未分类":
            continue
        readme.append(f"- {cat_zh}: {counts.get(cat_zh, 0)}")
    readme.extend(["", "## 分类子集", "", "见 `by_category/` 目录。", ""])
    (dataset_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")

    overview = [
        "# SJTU 125 Questions",
        "",
        "125 open scientific questions in parallel English and Chinese datasets.",
        "",
        "| Language | Directory |",
        "|----------|-----------|",
        "| English | [en/](en/) |",
        "| 简体中文 | [zh/](zh/) |",
        "",
        "Archives: `../sjtu-125-questions-en.zip` / `../sjtu-125-questions-zh.zip`",
        "",
    ]
    (dataset_root / "README.md").write_text("\n".join(overview), encoding="utf-8")


def main() -> int:
    if not EN_JSON.exists():
        print(f"未找到英文数据集: {EN_JSON}，请先运行 build_sjtu_125_dataset.py", file=sys.stderr)
        return 1

    en_records = json.loads(EN_JSON.read_text(encoding="utf-8"))
    use_llm = "--no-llm" not in sys.argv
    print(f"翻译 {len(en_records)} 条…（LLM={'开' if use_llm else '关'}）")

    # 允许从 backend 目录导入 app
    sys.path.insert(0, str(ROOT / "backend"))

    zh_records = translate_records(en_records, use_llm=use_llm)
    write_zh_outputs(zh_records, OUT_DIR)
    print(f"已写出中文版 -> {OUT_DIR}")
    print(Counter(r["category"] for r in zh_records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
