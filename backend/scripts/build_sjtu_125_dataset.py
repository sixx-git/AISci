"""从 SJTU x Science《125 Questions》手册拆分科研问题数据集。

输入（默认）:
  ../ocr/output/sjtu-booklet.md
  ../ocr/output/sjtu-booklet_parse.json

输出:
  output/sjtu-125-questions/en/questions.json
  output/sjtu-125-questions/en/questions.jsonl
  output/sjtu-125-questions/en/questions.csv
  output/sjtu-125-questions/en/README.md
  output/sjtu-125-questions/en/by_category/*.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = ROOT.parent / "ocr" / "output" / "sjtu-booklet_parse.json"
DEFAULT_MD = ROOT.parent / "ocr" / "output" / "sjtu-booklet.md"
OUT_DIR = ROOT / "output"

CATEGORIES = [
    "Mathematical Sciences",
    "Chemistry",
    "Medicine & Health",
    "Biology",
    "Astronomy",
    "Physics",
    "Engineering & Materials Science",
    "Information Science",
    "Neuroscience",
    "Ecology",
    "Energy Science",
    "Artificial Intelligence",
]

NOISE_PATTERNS = [
    r"^Signup",
    r"^Stay informed",
    r"^Take the opportunity",
    r"^Get alerts",
    r"What We Don.t Know",
    r"Asking questions is one",
    r"^In 2005, Science magazine",
    r"^In 2005, for its 125th",
    r"^The human condition is",
]


DOMAIN_DATA_HINTS: dict[str, str] = {
    "Mathematical Sciences": "公开数学文献、数值模拟数据、素数/流体方程相关基准数据集",
    "Chemistry": "分子结构数据库、材料性能数据、电化学与储能实验数据",
    "Medicine & Health": "临床队列、基因组学、公共卫生与流行病学开放数据",
    "Biology": "基因组/转录组、物种分布、生态与进化比较数据",
    "Astronomy": "巡天观测、宇宙学模拟、天体物理开放目录数据",
    "Physics": "粒子物理、凝聚态实验数据、量子计算基准",
    "Engineering & Materials Science": "材料表征、结构仿真、工程测试与制造数据",
    "Information Science": "计算理论基准、拓扑量子计算与算法实验数据",
    "Neuroscience": "脑成像、神经电生理、认知与语言行为数据集",
    "Ecology": "气候/遥感、物种与农业生态系统监测数据",
    "Energy Science": "能源系统运行数据、氢能/核能相关实验与仿真数据",
    "Artificial Intelligence": "机器学习基准、机器人与群体智能评测数据",
}


def fix_encoding(s: str) -> str:
    if not s:
        return s
    try:
        if "â" in s or "Ã" in s:
            s = s.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


def clean_text(s: str) -> str:
    s = fix_encoding(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    replacements = {
        "Al ": "AI ",
        "ar tificial": "artificial",
        "ef fort": "effort",
        "par t": "part",
        "bet ter": "better",
        "lof ty": "lofty",
        "Ear th": "Earth",
        "for t": "fort",
        "repor ter": "reporter",
        "MeridianSystem": "Meridian System",
        "commoncold": "common cold",
        "bemade": "be made",
        "othersvery": "others very",
        "theuniverse": "the universe",
        "thebrain": "the brain",
        "thespeed": "the speed",
        "theproperties": "the properties",
        "theworld": "the world",
        "thefuture": "the future",
        "theetiology": "the etiology",
        "theMeridian": "the Meridian",
        "thedeep": "the deep",
        "theheavy": "the heavy",
        "theoptimum": "the optimum",
        "thesmallest": "the smallest",
        "themaximum": "the maximum",
        "themicroscopic": "the microscopic",
        "thelimits": "the limits",
        "thevolume": "the volume",
        "therole": "the role",
        "theorigin": "the origin",
        "theshape": "the shape",
        "thenext": "the next",
        "thehuman": "the human",
        "theMilky": "the Milky",
        "theRiemann": "the Riemann",
        "theNavier": "the Navier",
        "theMeridian": "the Meridian",
        "humanCmachine": "human–machine",
        "human–machine": "human–machine",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s


def is_noise(q: str) -> bool:
    if len(q) < 12 or len(q) > 320:
        return True
    for p in NOISE_PATTERNS:
        if re.search(p, q, re.I):
            return True
    if not re.match(
        r"^(What|Why|How|Can|Will|Is|Are|When|Where|Do|Does|Did|Was|Were|Should|Could|Would|If)\b",
        q,
        re.I,
    ):
        return True
    return False


def norm_category(line: str) -> str | None:
    line = re.sub(r"^#+\s*", "", line).strip()
    for c in CATEGORIES:
        if line.lower() == c.lower() or line.startswith(c):
            return c
    return None


def question_key(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", q.lower())


def extract_context_after(text: str, end: int) -> str:
    after = clean_text(text[end : end + 800])
    parts = re.split(
        r"(?=(?:What|Why|How|Can|Will|Is|Are|When|Where|Do|Does|Did|Was|Were|Should|Could|Would|If)\b)",
        after,
        maxsplit=1,
    )
    return (parts[0] if parts else "")[:600]


def extract_from_text(text: str, page_num: int | None, category: str) -> list[dict]:
    found: list[dict] = []
    for m in re.finditer(r"([A-Z0-9\"'(][^?\n]{8,280}\?)", text):
        q = clean_text(m.group(1))
        if is_noise(q):
            continue
        found.append(
            {
                "question": q,
                "context": extract_context_after(text, m.end()),
                "page_num": page_num,
                "category": category,
                "source": "json_pages" if page_num is not None else "markdown",
            }
        )
    return found


def build_file_description(category: str, context: str) -> str:
    hint = DOMAIN_DATA_HINTS.get(category, "相关学科开放数据与文献")
    ctx = clean_text(context)[:280]
    if ctx:
        return f"领域：{category}。{hint}。背景摘要：{ctx}"
    return f"领域：{category}。{hint}。"


def build_category_spans(md_lines: list[str]) -> list[tuple[int, str]]:
    spans: list[tuple[int, str]] = []
    for idx, raw in enumerate(md_lines):
        line = raw.strip()
        if line.startswith("#"):
            cat = norm_category(line)
            if cat:
                spans.append((idx, cat))
    return spans


def category_at_line(spans: list[tuple[int, str]], line_num: int) -> str:
    cat = "Unknown"
    for ln, c in spans:
        if ln <= line_num:
            cat = c
        else:
            break
    return cat


def page_for_question(question: str, pages: list[dict]) -> int | None:
    key = question_key(question)[:40]
    for page in pages:
        text = page.get("text") or ""
        if question_key(text).find(key) >= 0 or key in question_key(text):
            return page.get("page_num")
        if question[:50] in text:
            return page.get("page_num")
    return None


def collect_context(md_lines: list[str], start: int, max_lines: int = 8) -> str:
    parts: list[str] = []
    for k in range(start, min(start + max_lines, len(md_lines))):
        t = clean_text(md_lines[k])
        if t.startswith("#") or t.startswith("<"):
            break
        if "?" in t and re.match(r"^(What|Why|How|Can|Will|Is|Are)", t, re.I):
            break
        if t:
            parts.append(t)
    return " ".join(parts)[:600]


def extract_questions_from_md(md_lines: list[str]) -> list[dict]:
    spans = build_category_spans(md_lines)
    items: list[dict] = []
    seen: set[str] = set()
    i = 0
    while i < len(md_lines):
        raw = md_lines[i]
        line = raw.strip()

        if line.startswith("#"):
            hq = re.sub(r"^#+\s*", "", line).strip()
            if "?" in hq:
                q = clean_text(hq)
                if not is_noise(q):
                    key = question_key(q)
                    if key not in seen:
                        seen.add(key)
                        items.append(
                            {
                                "question": q,
                                "context": collect_context(md_lines, i + 1),
                                "line_num": i,
                                "category": category_at_line(spans, i),
                                "source": "markdown_header",
                            }
                        )
            i += 1
            continue

        if re.match(
            r"^(What|Why|How|Can|Will|Is|Are|When|Where|Do|Does|Did|Was|Were|Should|Could|Would|If)\b",
            line,
            re.I,
        ):
            q = clean_text(line)
            j = i + 1
            if "?" not in q and j < len(md_lines):
                nxt = clean_text(md_lines[j])
                if (
                    nxt
                    and not nxt.startswith("#")
                    and not nxt.startswith("<")
                    and len(nxt) < 140
                    and "?" not in nxt[:30]
                ):
                    q = clean_text(f"{q} {nxt}")
                    j += 1
            if "?" in q and not is_noise(q):
                key = question_key(q)
                if key not in seen:
                    seen.add(key)
                    items.append(
                        {
                            "question": q,
                            "context": collect_context(md_lines, j),
                            "line_num": i,
                            "category": category_at_line(spans, i),
                            "source": "markdown_line",
                        }
                    )
            i = j
            continue
        i += 1
    return items


def build_dataset(json_path: Path, md_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    md_lines = md_path.read_text(encoding="utf-8").splitlines()
    pages = data.get("pages", [])

    items = extract_questions_from_md(md_lines)

    # 用 JSON 页文本补充 MD 中未收录的问题
    seen = {question_key(x["question"]) for x in items}
    category = "Unknown"
    for page in sorted(pages, key=lambda p: p.get("page_num", 0)):
        text = page.get("text") or ""
        page_num = page.get("page_num")
        for line in text.split("\n"):
            nc = norm_category(line.strip())
            if nc:
                category = nc
        for row in extract_from_text(text, page_num, category):
            key = question_key(row["question"])
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "question": row["question"],
                    "context": row["context"],
                    "line_num": 10_000 + (page_num or 0) * 100,
                    "category": row["category"],
                    "source": row["source"],
                    "page_num": page_num,
                }
            )

    for row in items:
        if row.get("page_num") is None:
            row["page_num"] = page_for_question(row["question"], pages)

    items.sort(key=lambda x: x.get("line_num", 99999))

    if len(items) > 125:
        items = items[:125]
    elif len(items) < 125:
        sys.stderr.write(f"警告: 仅提取到 {len(items)} 条问题（目标 125）\n")

    records: list[dict] = []
    for i, row in enumerate(items, start=1):
        q = row["question"]
        cat = row["category"] if row["category"] in CATEGORIES else "Unknown"
        ctx = row.get("context") or ""
        records.append(
            {
                "id": f"sjtu_q_{i:03d}",
                "index": i,
                "question_name": q.rstrip("?")[:120],
                "research_question": q if q.endswith("?") else f"{q}?",
                "file_description": build_file_description(cat, ctx),
                "category": cat,
                "domain": cat,
                "context": ctx,
                "page_num": row.get("page_num"),
                "source": row.get("source"),
                "source_booklet": "125 Questions: Exploration and Discovery (Shanghai Jiao Tong University × Science/AAAS, 2021)",
                "tags": [cat, "open_question", "sjtu_125"],
                "pipeline_mode_suggested": "discovery",
                "expected_outputs": ["hypothesis", "experiment_design", "report"],
            }
        )
    return records


def write_outputs(records: list[dict], out_dir: Path) -> None:
    dataset_root = out_dir / "sjtu-125-questions"
    dataset_dir = dataset_root / "en"
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
        "page_num",
        "context",
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
        safe = re.sub(r"[^\w]+", "_", cat).strip("_")
        (cat_dir / f"{safe}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    counts = Counter(r["category"] for r in records)
    readme = [
        "# SJTU 125 Questions (English)",
        "",
        "From *125 Questions: Exploration and Discovery*, for AISci Pipeline / quick-report benchmarks.",
        "",
        f"- Total: **{len(records)}**",
        "- Main files: `questions.json` / `questions.jsonl` / `questions.csv`",
        "- Chinese version: `../zh/`",
        "",
        "## Fields",
        "",
        "| Field | Description |",
        "|-------|-------------|",
        "| `id` | Unique ID, e.g. `sjtu_q_001` |",
        "| `question_name` | Short title |",
        "| `research_question` | Full research question |",
        "| `file_description` | Data / domain hint for Data Finder |",
        "| `category` | Scientific domain |",
        "| `context` | Background paragraph from the booklet |",
        "",
        "## Categories",
        "",
    ]
    for cat in CATEGORIES:
        readme.append(f"- {cat}: {counts.get(cat, 0)}")
    readme.extend(["", "## By category", "", "See `by_category/`.", ""])
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
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JSON
    md_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MD

    if not json_path.exists():
        print(f"未找到 JSON: {json_path}", file=sys.stderr)
        return 1
    if not md_path.exists():
        print(f"未找到 Markdown: {md_path}", file=sys.stderr)
        return 1

    records = build_dataset(json_path, md_path)
    write_outputs(records, OUT_DIR)
    print(f"已生成 {len(records)} 条问题 -> {OUT_DIR}")
    print(Counter(r["category"] for r in records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
