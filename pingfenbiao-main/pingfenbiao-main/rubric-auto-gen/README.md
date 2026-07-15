# Rubric Auto-Gen — 主张核查 (Claim Verification)

基于大语言模型的主张核查报告评分表生成器（**v5.1-cv**）。从源文献提取领域知识，生成**领域通用、质量驱动**的三维度评分标准。

## 设计原则

- **领域级质量标准**：评估该领域任何报告应达到的质量，不绑定特定源文档
- **claim-focused SR**：≥35% 的 SR 项直接检验主张有效性，构建推理链（机制冲突 → 边界条件 → 证据综合）
- **Synth 无 Critical**：与人工样例一致，Mandatory 覆盖证据表、Verdict、sub-proposition 映射
- **防答案泄露**：问题不预设结论，使用 "evaluate whether..." 而非 "explain why X fails..."
- **轻量校准**：规则检查 + LLM 去重（20% 上限），不调用 LLM 修复

## 评分表维度（claim_verification）

| 维度 | 权重 | 项数范围 | 评估内容 |
|------|------|---------|---------|
| IA | 26% | 12–16 | 领域概念、机制、实验设置的准确获取 |
| SR | 62.5% | 20–28 | 主张分析、证据综合、边界推导、跨源推理 |
| Synth | 11.5% | 8–11 | 证据表、Verdict、引用准确性、逻辑自洽 |

## 环境配置

```bash
cd rubric-auto-gen
pip install -r requirements.txt

# 任选其一
export DASHSCOPE_API_KEY="sk-xxx"
# 或复制 .env.example 为 .env 并填入 Key
```

## 输入文件

将 PDF / CSV / MD / TXT 放入同一目录，按**文件名排序**编号为 S1、S2…

| 类型 | 典型用途 |
|------|---------|
| PDF | 领域论文、实验方法文献 |
| MD / TXT | 实验说明、主张定义补充 |
| CSV | 可选，实验数据摘要 |

**test1 示例**（FL 后门防御）：`../测试报告/主张核查/test1/sources/`  
**test2 示例**（PEFT 参数效率）：`../测试报告/主张核查/test2/sources/`

## CLI 命令详解

入口：`python main.py <command> [options]`

### 通用参数（所有子命令）

| 参数 | 说明 |
|------|------|
| `--api-key` | DashScope API Key（默认读环境变量） |
| `--rubric-model` | 评分表生成模型（默认 `deepseek-v4-flash`） |
| `--scoring-model` | 自动评分模型 |
| `--quiet` | 减少控制台日志 |

### `generate` — 仅生成评分表

```bash
python main.py generate \
  --source-dir "../测试报告/主张核查/test1/sources" \
  --output "./output" \
  --task-type claim_verification
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--source-dir` | 是 | 源文件目录 |
| `--output` | 否 | 输出目录，默认 `./output` |
| `--query` | 否 | 研究问题；**留空则从文献自动生成** |
| `--task-type` | 否 | `claim_verification`（默认）/ `data_analysis` / `literature_review` |
| `--task-id` | 否 | 自定义任务 ID |
| `--subject` | 否 | 学科标签，如 `information_security` |

**输出**：`output/task.json`（含 `generation_meta`、`calibration`）

### `score` — 对报告自动评分

```bash
python main.py score \
  --task ./output/task.json \
  --report ./report.md \
  --output ./output
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--task` | 是 | 已有 `task.json` |
| `--report` | 是 | 待评报告（Markdown） |
| `--output` | 否 | 输出目录 |
| `--source-dir` | 否 | 源文献目录，注入上下文辅助评分 |
| `--max-report-chars` | 否 | 报告截断上限，默认 20000 |

**输出**：`output/self_check/rubric_scores.json`（含 `scoring_meta`）

### `highlight` — 源 PDF 高亮标注

```bash
python main.py highlight \
  --task ./output/task.json \
  --source-dir "../测试报告/主张核查/test1/sources" \
  --output ./output
```

**输出**：`output/sources/` 下标注后的 PDF

### `full` — 完整流水线

依次：生成 → 评分 → 标注。

```bash
python main.py full \
  --source-dir "./papers" \
  --report "./report.md" \
  --output "./output" \
  --task-type claim_verification
```

## 辅助脚本：`compare_rubric.py`

与人工样例 `样例/Deep交付模板/主张核查报告/task.json` 对比质量指标：

```bash
python compare_rubric.py ./output/task.json
```

对比项包括：总分、项数、IA/SR/Synth 分布、claim-focused 比例、动词统计等。

## 生成流程

```
Stage 1   知识提取 + 概念泛化 + LLM 术语过滤
Stage 2   IA / SR / Synth 分别生成（质量驱动 Prompt）
Stage 3a  规则校准（模糊词、弱动词、泄露、术语、冗余）
Stage 3b  LLM 去重
Stage 3c  主张核查后处理（结构项注入、多源上限 30%、claim-focused 保底）
→ Calibrator 后置校准 → task.json
```

## 参考输出

| 测试 | 路径 | 总分 | 项数 |
|------|------|------|------|
| test1 (FL) | `../测试报告/主张核查/test1/output_v5_cv3/` | 88 | 41 |
| test2 (PEFT) | `../测试报告/主张核查/test2/output_v5_cv3/` | 105 | 46 |

## 依赖

- Python >= 3.10
- openai >= 1.30.0
- pymupdf >= 1.24.0
- rich >= 13.0.0

## License

MIT License
