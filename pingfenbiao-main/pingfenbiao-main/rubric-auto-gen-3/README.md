# Rubric Auto-Gen 3 — 科学调研报告 (Literature Review)

基于大语言模型的科学调研（文献综述）报告评分表生成器。从综述论文或领域文献中提取知识，生成领域通用、认知层次分明的三维度评分标准。

## 设计原则

- **领域级质量标准**：评分项泛化到该领域的任何文献综述报告，不绑定特定论文的发现
- **深度推理导向**：SR 维度权重最高（62%），Critical 项比例最高（25%），测试分析论证深度
- **无主题前缀**：SR 维度不使用固定主题标签，由 LLM 根据源文档内容自然组织分析焦点
- **Synth 全 Standard**：所有 Synth 项为 Standard（1 分），侧重结构完整性而非深度分析

## 评分表维度

| 维度 | 权重 | 项数范围 | 认知层次 | 评估内容 |
|------|------|---------|---------|---------|
| Information Acquisition (IA) | 23% | 12-16 | remember / understand | 报告是否准确获取了核心概念定义、技术分类、方法原理 |
| Scientific Reasoning (SR) | 62% | 28-38 | analyze / evaluate / create | 报告的机制分析、跨方法比较、瓶颈识别、策略推理能力 |
| Report Synthesis (Synth) | 15% | 10-14 | apply / evaluate | 报告结构完整性、分类体系、时间覆盖、前瞻性、共识总结 |

**角色分布**：
- IA: Critical（15%）、Mandatory（50%）、Standard（35%）
- SR: Critical（25%）、Mandatory（50%）、Standard（25%）
- Synth: 全部 Standard（100%）

## SR 5 大分析焦点

| 焦点 | 目标占比 | 测试内容 |
|------|---------|---------|
| Mechanism Analysis | ~30% | "为什么"和"怎么做"的深层机制理解 |
| Cross-method Comparison | ~25% | 跨方法比较、优势条件分析 |
| Bottleneck / Limitation Analysis | ~20% | 核心瓶颈识别、局限性评估 |
| Strategy Reasoning | ~15% | 攻防策略逻辑、约束权衡 |
| Effect Quantification | ~10% | 定量分析、参数影响 |

## SR 动词分布

| 类别 | 目标占比 | 核心动词 |
|------|---------|---------|
| Mechanism Analysis | 25% | analyze why, analyze the mechanism |
| Comparative Evaluation | 20% | compare, contrast, evaluate trade-offs |
| Principle Explanation | 15% | explain the scientific logic, explain why |
| Critical Assessment | 15% | evaluate effectiveness, assess limitations |
| Argumentation & Synthesis | 15% | argue, justify, critique, synthesize |
| Quantitative / Formal Reasoning | 10% | derive, quantify, demonstrate |

## Synth 覆盖要求

Synth 维度的评分项必须覆盖以下至少 8 个子主题：

1. 综述结构完整性（Abstract, Introduction, Attack Models, Defense Technologies, Future Directions）
2. 分类体系 / 层次分类图
3. 时间演进（2017-2025 年代际发展）
4. 前瞻性分析（至少 3 个具体研究切入点）
5. 对比框架（不同条件下的防御性能比较）
6. 权衡分析（安全 vs 效率、隐私 vs 效用）
7. 共识与局限（没有单一方案解决所有场景）
8. 可视化辅助（分类图、比较表、时间线图）
9. 最新趋势（2024-2025 发展、新兴风险）
10. 结论综合（关键发现和开放问题重申）

## 环境配置

```bash
cd rubric-auto-gen-3
pip install -r requirements.txt
export DASHSCOPE_API_KEY="sk-xxx"
```

## 输入文件

将 PDF / MD / TXT 放入同一目录，按**文件名排序**编号为 S1、S2…

| 类型 | 说明 |
|------|------|
| **PDF** | 综述论文、领域文献 |
| **MD / TXT** | 文献笔记、阅读标注 |

**test1 示例**：`../测试报告/科学调研/test1/sources/`  
**test2 示例**：`../测试报告/科学调研/test2/sources/`

## CLI 命令详解

入口：`python main.py <command> [options]`

### 通用参数

| 参数 | 说明 |
|------|------|
| `--api-key` | DashScope API Key |
| `--rubric-model` / `--scoring-model` | 模型覆盖 |
| `--quiet` | 安静模式 |

### `generate` — 仅生成评分表

```bash
python main.py generate \
  --source-dir "../测试报告/科学调研/test1/sources" \
  --query "综述联邦学习中后门攻击防御机制的研究进展..." \
  --output "./output" \
  --subject information_security

# 仅上传文献，query 留空
python main.py generate \
  --source-dir "./papers" \
  --output "./output"
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--source-dir` | 是 | 源文件目录 |
| `--output` | 否 | 默认 `./output` |
| `--query` | 否 | 综述问题；**留空则从文献自动生成** |
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

### `highlight` — 源 PDF 高亮标注

```bash
python main.py highlight \
  --task ./output/task.json \
  --source-dir "./papers" \
  --output "./output"
```

**输出**：`output/sources/` 标注 PDF

### `full` — 完整流水线

```bash
python main.py full \
  --source-dir ./papers \
  --report ./report.md \
  --output ./output
```

## 参考输出

| 测试 | 路径 | 总分 | 项数 |
|------|------|------|------|
| test1 (FL) | `../测试报告/科学调研/test1/output_gen3_v6/` | 96 | 45 |
| test2 (PEFT) | `../测试报告/科学调研/test2/output_v6/` | 100 | 45 |

## 依赖

- Python >= 3.10
- openai >= 1.30.0
- pymupdf >= 1.24.0
- rich >= 13.0.0

## License

MIT License
