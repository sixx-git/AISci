# Rubric Auto-Gen 2 — 数据分析报告 (Data Analysis)

基于大语言模型的数据分析报告评分表生成器。从领域文献、数据集和实验配置中提取知识，生成领域通用、认知层次分明的三维度评分标准。

## 设计原则

- **领域级质量标准**：评分项泛化到该领域的任何数据分析报告，不绑定特定数据集或算法名
- **数据实证导向**：SR 动词强调 quantify、demonstrate、verify 等数据驱动的分析动作
- **8 大分析主题**：SR 维度使用强制主题前缀标签，确保分析覆盖面完整
- **中文源文件兼容**：校准阶段采用中文容忍模式（清除中文保留英文），适配中文数据集/配置文件

## 评分表维度

| 维度 | 权重 | 项数范围 | 认知层次 | 评估内容 |
|------|------|---------|---------|---------|
| Information Acquisition (IA) | 20% | 10-14 | remember / understand | 报告是否准确获取了数据特征、实验参数、变量约束 |
| Scientific Reasoning (SR) | 65% | 28-38 | analyze / evaluate / create | 报告的数据分析能力、推理深度、结论严谨性 |
| Report Synthesis (Synth) | 15% | 10-14 | apply / evaluate | 报告结构、可视化质量、数据追溯性、结论约束 |

**角色分布**：Critical（4 分, 10%）、Mandatory（2 分, 55%）、Standard（1 分, 35%）。

## SR 8 大分析主题

| 主题前缀 | 建议项数 | 核心关注 |
|---------|---------|---------|
| Convergence analysis | 3-5 | 收敛轮判定、收敛失败条件、收敛速度对比 |
| Heterogeneity impact | 3-5 | 异质性对精度的影响、单调性、跨算法差异 |
| Algorithm comparison | 3-5 | 算法性能对比、鲁棒性评估、优势归因 |
| Statistical verification | 2-4 | 统计显著性、置信区间、假设检验 |
| Error/Variance analysis | 2-4 | 误差分解、方差溯源、异常值影响 |
| Sensitivity analysis | 2-4 | 超参数敏感性、转折点识别、边界条件 |
| Data integrity validation | 2-4 | 物理约束验证、缺失值检测、异常记录 |
| Theoretical grounding | 2-4 | 理论框架联系、极端场景分析、公式验证 |

## SR 动词分布

| 类别 | 目标占比 | 核心动词 |
|------|---------|---------|
| Quantification & Demonstration | 20% | quantify, demonstrate, show |
| Mechanism Analysis | 20% | analyze why, analyze the mechanism |
| Comparative Evaluation | 15% | compare, contrast, evaluate trade-offs |
| Data-Driven Inference | 15% | infer, derive, deduce, trace |
| Verification & Validation | 15% | verify, validate, confirm, check |
| Sensitivity & Robustness | 15% | assess sensitivity, identify tipping points |

## 环境配置

```bash
cd rubric-auto-gen-2
pip install -r requirements.txt
export DASHSCOPE_API_KEY="sk-xxx"
```

## 输入文件

将 PDF / CSV / MD / TXT 放入同一目录，按**文件名排序**编号为 S1、S2…

| 类型 | 说明 |
|------|------|
| **PDF** | 领域论文、方法对比文献（test2 可仅含 PDF） |
| **CSV** | 实验数据（列名、前 50 行、基础统计） |
| **MD / TXT** | 数据字典、实验配置、变量定义 |

**test1 示例**（CSV + 元数据）：`../测试报告/数据分析/test1/files/`  
**test2 示例**（仅论文）：`../测试报告/数据分析/test2/sources/`

## CLI 命令详解

入口：`python main.py <command> [options]`

> Gen-2 **无独立 `highlight` 子命令**；`full` 会在生成与评分后自动执行 PDF 标注。

### 通用参数

| 参数 | 说明 |
|------|------|
| `--api-key` | DashScope API Key |
| `--rubric-model` / `--scoring-model` | 模型覆盖 |
| `--quiet` | 安静模式 |

### `generate` — 仅生成评分表

```bash
# test1：CSV + 元数据
python main.py generate \
  --source-dir "../测试报告/数据分析/test1/files" \
  --query "分析联邦学习实验日志中的收敛行为和算法性能差异..." \
  --output "./output" \
  --subject computer_science

# test2：仅论文，query 可省略
python main.py generate \
  --source-dir "../测试报告/数据分析/test2/sources" \
  --output "./output"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--source-dir` | 是 | 源文件目录 |
| `--output` | 否 | 默认 `./output` |
| `--query` | 否 | 分析问题；**留空则从文献自动生成** |
| `--task-id` / `--subject` | 否 | 任务元数据 |

**输出**：`output/task.json`

### `score` — 对报告自动评分

```bash
python main.py score \
  --task ./output/task.json \
  --report ./report.md \
  --output ./output
```

**输出**：`output/rubric_scores.json`

### `full` — 生成 + 评分 + 标注

```bash
python main.py full \
  --source-dir ./data \
  --report ./report.md \
  --output ./output
```

**输出**：`task.json`、`rubric_scores.json`、`sources/` 标注 PDF

## 参考输出

| 测试 | 路径 | 总分 | 项数 |
|------|------|------|------|
| test1 (FL) | `../测试报告/数据分析/test1/output_gen2_v7/` | 118 | 56 |
| test2 (PEFT) | `../测试报告/数据分析/test2/output_v7/` | 117 | 54 |

## 依赖

- Python >= 3.10
- openai >= 1.30.0
- pymupdf >= 1.24.0
- rich >= 13.0.0

## License

MIT License
