# Rubric Auto-Generator（评分表自动生成系统）

基于大语言模型（LLM）的自动化评分表（Rubric）生成与评分系统，面向学术报告评估场景。上传源文献（及可选的数据、元数据说明），即可生成**领域级质量标准**评分表，并对报告自动评分、对源 PDF 标注。

三种任务类型对应三个独立优化的生成器，共享相同的 7 阶段流水线架构。

---

## 目录

- [项目结构](#项目结构)
- [环境配置](#环境配置)
- [输入文件说明](#输入文件说明)
- [脚本与入口一览](#脚本与入口一览)
- [Gen-1：主张核查](#gen-1主张核查-rubric-auto-gen)
- [Gen-2：数据分析](#gen-2数据分析-rubric-auto-gen-2)
- [Gen-3：科学调研](#gen-3科学调研-rubric-auto-gen-3)
- [Web 界面](#web-界面)
- [辅助工具](#辅助工具)
- [输出文件说明](#输出文件说明)
- [常见问题](#常见问题)

---

## 项目结构

```
pingfenbiao/
├── rubric-auto-gen/              # Gen-1 主张核查 (claim_verification)
│   ├── main.py                   # CLI：generate / score / highlight / full
│   ├── compare_rubric.py         # 与人工样例对比
│   └── pipeline/                 # 生成、校准、评分、标注
├── rubric-auto-gen-2/            # Gen-2 数据分析 (data_analysis)
│   └── main.py                   # CLI：generate / score / full
├── rubric-auto-gen-3/            # Gen-3 科学调研 (literature_review)
│   └── main.py                   # CLI：generate / score / highlight / full
├── common/
│   └── auto_query.py             # Query 为空时从文献自动生成
├── web/                          # Web 上传生成（含进度显示）
├── 样例/Deep交付模板/             # 人工编制黄金标准 task.json
└── 测试报告/                      # 各类型 test1/test2 最佳输出
```

---

## 环境配置

### 依赖安装

每个子项目目录下均有 `requirements.txt`，按需安装：

```bash
# 主张核查（Gen-1）
cd rubric-auto-gen && pip install -r requirements.txt

# 数据分析（Gen-2）
cd rubric-auto-gen-2 && pip install -r requirements.txt

# 科学调研（Gen-3）
cd rubric-auto-gen-3 && pip install -r requirements.txt

# Web 界面（可选）
cd web && pip install -r requirements.txt
```

**要求**：Python >= 3.10

### API Key

使用阿里云百炼 DashScope（兼容 OpenAI SDK），任选一种方式配置：

```bash
# 方式 1：环境变量
export DASHSCOPE_API_KEY="sk-xxx"

# 方式 2：.env 文件（推荐放在 rubric-auto-gen/.env）
DASHSCOPE_API_KEY=sk-xxx

# 方式 3：CLI 参数
python main.py generate ... --api-key sk-xxx
```

**默认模型**：`deepseek-v4-flash`（可通过 `--rubric-model` / `--scoring-model` 覆盖）

---

## 输入文件说明

所有生成器从 `--source-dir` 目录读取文件，**按文件名排序**后依次编号为 `S1`、`S2`、`S3`…

| 扩展名 | 用途 | 说明 |
|--------|------|------|
| `.pdf` | 文献 | PyMuPDF 提取全文 |
| `.csv` | 实验数据 | 解析表头、前 50 行预览、基础统计 |
| `.md` / `.txt` | 元数据 / 说明 | 数据字典、实验配置、文献笔记等 |

**组合输入示例**（数据分析 test1）：

```
files/
├── fl_training_metrics.csv      # 训练日志
├── datadict.md                  # 变量定义
├── experiment_metadata.md       # 实验设计
└── （可选）相关论文 PDF
```

**仅论文输入**（如数据分析 test2、主张核查 test2）同样支持：系统从 PDF 中的实验描述与方法信息生成领域级评分标准。

> 不支持独立的 JSON/YAML 元数据协议；元数据请写成 Markdown/纯文本放入同一目录。

---

## 脚本与入口一览

| 入口 | 路径 | 子命令 | 说明 |
|------|------|--------|------|
| Gen-1 CLI | `rubric-auto-gen/main.py` | `generate` `score` `highlight` `full` | 主张核查全流程 |
| Gen-2 CLI | `rubric-auto-gen-2/main.py` | `generate` `score` `full` | 数据分析（`full` 含标注） |
| Gen-3 CLI | `rubric-auto-gen-3/main.py` | `generate` `score` `highlight` `full` | 科学调研全流程 |
| 对比工具 | `rubric-auto-gen/compare_rubric.py` | — | 生成表 vs 人工样例 |
| Web | `web/app.py` | 浏览器 + REST API | 上传文献生成 / 报告打分 |

### 通用 CLI 参数

以下参数在对应子命令中可用（Gen-1/2/3 略有差异，见各节）：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--source-dir` | 源文件目录（必填，generate/full） | — |
| `--query` | 研究/分析问题（**可选**，留空则从文献自动生成） | `""` |
| `--output` | 输出目录 | `./output` |
| `--task` | 已有 `task.json` 路径（score/highlight） | — |
| `--report` | 待评报告路径 `.md`（score/full） | — |
| `--api-key` | DashScope API Key | 环境变量 |
| `--rubric-model` | 评分表生成模型 | `deepseek-v4-flash` |
| `--scoring-model` | 自动评分模型 | `deepseek-v4-flash` |
| `--quiet` | 安静模式（减少日志） | 关闭 |
| `--task-id` | 自定义任务 ID | 自动生成 |
| `--subject` | 学科领域标签 | `""` |

**`score` 子命令专用参数**（Gen-1/2/3 均支持）：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--source-dir` | 源文献目录（**可选**），注入源文献摘要辅助 source 引用项评分 | 不传入 |
| `--max-report-chars` | 报告送入 LLM 前的字符上限；超长时智能截断（首尾 + 关键章节） | `20000` |

**Gen-1 额外参数**：`--task-type`（`claim_verification` / `data_analysis` / `literature_review`，默认 `claim_verification`）

**评分器版本**：共用 `common/scorer.py`（v3），输出含 `scoring_meta`（截断信息、补评项、告警等）。

---

## Gen-1：主张核查 (`rubric-auto-gen`)

**适用场景**：对某一可核验主张，基于多篇领域论文撰写核查报告并评估质量。

```bash
cd rubric-auto-gen
```

### `generate` — 仅生成评分表

```bash
python main.py generate \
  --source-dir "../测试报告/主张核查/test1/sources" \
  --output "./output" \
  --task-type claim_verification

# 手动指定研究问题（可选）
python main.py generate \
  --source-dir "./papers" \
  --query "在差分隐私保护下，联邦学习的后门防御机制在面对自适应攻击时是否仍然有效？" \
  --output "./output" \
  --task-type claim_verification
```

**输出**：`output/task.json`（含 `calibration` 校准报告）

**耗时**：约 3–8 分钟（视文献数量与 API 速度）

### `score` — 对报告自动评分

```bash
python main.py score \
  --task ./output/task.json \
  --report ./report.md \
  --output ./output

# 注入源文献上下文（推荐，与生成时同一目录）
python main.py score \
  --task ./output/task.json \
  --report ./report.md \
  --source-dir "../测试报告/主张核查/test1/sources" \
  --output ./output \
  --max-report-chars 30000
```

**输出**：`output/self_check/rubric_scores.json`（含 `scoring_meta`）

### `highlight` — 源 PDF 高亮标注

```bash
python main.py highlight \
  --task ./output/task.json \
  --source-dir "../测试报告/主张核查/test1/sources" \
  --output ./output
```

**输出**：`output/sources/` 下带高亮的 PDF

### `full` — 完整流水线

依次执行：生成 → 评分 → 标注。

```bash
python main.py full \
  --source-dir "./papers" \
  --report "./report.md" \
  --output "./output" \
  --task-type claim_verification
```

---

## Gen-2：数据分析 (`rubric-auto-gen-2`)

**适用场景**：数据分析报告——可含 CSV 日志 + 元数据，也可仅含方法论文（跨文献对比型分析）。

```bash
cd rubric-auto-gen-2
```

### `generate`

```bash
# test1：CSV + 元数据 + 可选论文
python main.py generate \
  --source-dir "../测试报告/数据分析/test1/files" \
  --query "分析联邦学习实验日志中的收敛行为与算法性能差异..." \
  --output "./output"

# test2：仅论文 PDF（LoRA / QLoRA / DoRA）
python main.py generate \
  --source-dir "../测试报告/数据分析/test2/sources" \
  --output "./output"
  # --query 可省略，将从文献自动生成
```

### `score`

```bash
python main.py score \
  --task ./output/task.json \
  --report ./report.md \
  --output ./output

python main.py score \
  --task ./output/task.json \
  --report ./report.md \
  --source-dir "../测试报告/数据分析/test1/files" \
  --output ./output
```

**输出**：`output/rubric_scores.json`

### `full`

生成 + 评分 + PDF 标注（无单独 `highlight` 子命令，标注包含在 `full` 内）。

```bash
python main.py full \
  --source-dir "./data" \
  --report "./report.md" \
  --output "./output"
```

---

## Gen-3：科学调研 (`rubric-auto-gen-3`)

**适用场景**：文献综述 / 科学调研报告，输入综述 PDF 或领域文献。

```bash
cd rubric-auto-gen-3
```

### `generate`

```bash
python main.py generate \
  --source-dir "../测试报告/科学调研/test1/sources" \
  --query "综述联邦学习中后门攻击防御机制的研究进展..." \
  --output "./output"

# 仅上传文献、留空 query
python main.py generate \
  --source-dir "./papers" \
  --output "./output"
```

### `score` / `highlight` / `full`

```bash
python main.py score --task ./output/task.json --report ./report.md --output ./output

python main.py highlight \
  --task ./output/task.json \
  --source-dir "./papers" \
  --output ./output

python main.py full \
  --source-dir "./papers" \
  --report "./report.md" \
  --output "./output"
```

---

## Web 界面

浏览器完成**评分表生成**与**报告自动打分**（异步任务 + 进度条），底层调用与 CLI 相同的 `main.py generate` / `main.py score`。

```bash
cd web
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8765
```

浏览器打开：**http://127.0.0.1:8765**

### 生成评分表

| 功能 | 说明 |
|------|------|
| 报告类型 | 主张核查 / 数据分析 / 科学调研 |
| 文件上传 | 多选 PDF、CSV、MD、TXT，单文件 ≤ 50MB |
| 补充说明 | 可选，留空则从文献自动生成 Query |
| API Key | 可选，未填则使用服务器环境变量 |
| 进度 | 轮询 `/api/status/{job_id}` |
| 下载 | `GET /api/download/{job_id}` → `task.json` |

### 报告打分

| 功能 | 说明 |
|------|------|
| task.json | 必填；系统读取 `task_type` 自动选择 Gen-1/2/3 |
| 待评报告 | 必填；MD / TXT / PDF |
| 源文献 | 可选；与 CLI `--source-dir` 相同，辅助 source 引用项评分 |
| 报告截断上限 | 高级选项 `max_report_chars`（0 = 默认 20000） |
| 下载 | `GET /api/download/{job_id}/scores` → `rubric_scores.json` |

**REST API**（供集成）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/generate` | 提交生成任务，返回 `job_id` |
| `POST` | `/api/score` | 提交打分任务（multipart：`task_file`、`report_file`、可选 `source_files`） |
| `GET` | `/api/status/{job_id}` | 查询进度；完成时含 `job_mode`（`generate` / `score`） |
| `GET` | `/api/download/{job_id}` | 下载 `task.json`（生成任务） |
| `GET` | `/api/download/{job_id}/scores` | 下载 `rubric_scores.json`（打分任务） |

---

## 辅助工具

### `compare_rubric.py`（主张核查专用）

对比生成结果与人工样例 `样例/Deep交付模板/主张核查报告/task.json`：

```bash
cd rubric-auto-gen
python compare_rubric.py ./output/task.json
```

输出：总分、项数、IA/SR/Synth 分布、SR claim-focused 比例、动词统计等。

### 可视化对比报告

浏览器打开：`rubric-comparison-report/rubric-comparison-report.html`

---

## 输出文件说明

| 文件 | 产生命令 | 内容 |
|------|----------|------|
| `task.json` | `generate` / `full` / Web | 完整评分表 + `generation_meta` + `calibration` |
| `rubric_scores.json` | Gen-2/3 `score` / Web 打分 | 逐项得分、`scoring_meta` |
| `self_check/rubric_scores.json` | Gen-1 `score` / `full` / Web 打分 | 同上（Gen-1 路径不同） |
| `sources/*.pdf` | `highlight` / `full` | 高亮标注后的源 PDF |

**`task.json` 单条评分项示例**：

```json
{
  "rubric_id": "R1",
  "rubric_key": "information_acquisition.definition.does_the_report_define...",
  "competency_category": "definition",
  "role": "Critical",
  "weight": 4,
  "question": "Does the report define X as...?",
  "source_ids": ["S1"]
}
```

---

## 当前最佳测试输出

| 类型 | 测试 | 路径 | 总分 | 项数 |
|------|------|------|------|------|
| 主张核查 | test1 (FL) | `测试报告/主张核查/test1/output_v5_cv3/` | 88 | 41 |
| 主张核查 | test2 (PEFT) | `测试报告/主张核查/test2/output_v5_cv3/` | 105 | 46 |
| 数据分析 | test1 (FL) | `测试报告/数据分析/test1/output_gen2_v7/` | 118 | 56 |
| 数据分析 | test2 (PEFT) | `测试报告/数据分析/test2/output_v7/` | 117 | 54 |
| 科学调研 | test1 (FL) | `测试报告/科学调研/test1/output_gen3_v6/` | 96 | 45 |
| 科学调研 | test2 (PEFT) | `测试报告/科学调研/test2/output_v6/` | 100 | 45 |

人工样例对照：`样例/Deep交付模板/*/task.json`

---

## 常见问题

**Q：`--query` 必须填吗？**  
不必。Gen-1/2/3 均支持留空，系统调用 `common/auto_query.py` 从文献自动生成研究问题。

**Q：三种类型该用哪个目录？**  
- 核验单一主张 → `rubric-auto-gen`（Gen-1）  
- 分析实验数据或对比方法论文 → `rubric-auto-gen-2`（Gen-2）  
- 文献综述 → `rubric-auto-gen-3`（Gen-3）  

**Q：Web 与 CLI 结果一致吗？**  
是。Web 通过 subprocess 调用对应 `main.py generate` 或 `main.py score`，参数与 CLI 等价。

**Q：Web 打分如何选生成器？**  
读取上传 `task.json` 的 `task_type` 字段，无需手动选择。

**Q：生成失败如何排查？**  
检查 `DASHSCOPE_API_KEY`、源目录是否有支持的文件、API 配额；加 `--quiet` 去掉或用默认日志查看 Stage 报错。

---

## 核心设计（简述）

- **领域级质量标准**：评「该领域好报告应达到什么水平」，非「是否复述 S1 某句」  
- **7 阶段流水线**：Query 解析 → 知识提取 → 概念泛化 → 三维度生成 → 规则校准 → LLM 去重 → 类型专用后处理  
- **三维度**：IA（信息获取）/ SR（科学推理）/ Synth（报告综合）  
- **角色分值**：Critical 4 分、Mandatory 2 分、Standard 1 分  

详见各子目录 `README.md` 与 `.cursorrules`。

---

## 相关文档

- `rubric-auto-gen/README.md` — Gen-1 详细说明  
- `rubric-auto-gen-2/README.md` — Gen-2 详细说明  
- `rubric-auto-gen-3/README.md` — Gen-3 详细说明  
- `.cursorrules` — 开发约束与修改规范  
- `*评分表*报告.md` — 各类型质量对比分析  

## License

MIT License
