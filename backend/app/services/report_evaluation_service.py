"""
报告质量评估服务 —— 三种评估模式

- simple: 简单提交，不加额外提示词
- weighted: 客观加权评分（7 层 rubric）
- scientist: 科学家人格评分（模拟人类偏好）
"""
import json
import logging

from app.models.project import Report

logger = logging.getLogger(__name__)

# ── 模式二：客观加权评分 prompt ──────────────────────────────────
WEIGHTED_SYSTEM_PROMPT = """你是一位客观、严谨的科研报告评分员。请按照以下七层加权模型对报告进行逐层评分，并给出综合得分。

## 权重体系（合计100%，科研四层 L2-L5 合计85%）

| 层 | 维度 | 权重 |
|---|---|---|
| L0 | 类型识别 | 5% |
| L1 | 形式合规 | 5% |
| L2 | 选题与问题 | 20% |
| L3 | 方法学 | 25% |
| L4 | 证据强度 | 25% |
| L5 | 诚实度 | 15% |
| L6 | 可用性 | 5% |

## 各层评分口径（每层 0–100）

- **L0 类型识别**：是否透明自标 AI/代理/自动生成 → 100，否则 50。
- **L1 形式合规**：摘要/方法/结果/讨论/参考文献 各12分(共60)；有结论段+20；有引言/背景+20。
- **L2 选题与问题**：问题真实性(50%)＝"研究缺口/缺乏/尚未"且文献≥4→100，否则60；跨学科牵强(50%)，学科跨度≤1→100，=2→60，≥3→30。
- **L3 方法学**：可检验性(25%)；泄漏/平凡解(25%，自报越多越扣)；显著性检验(25%)；代理-命题匹配(25%)。
- **L4 证据强度**：样本量(50%)；结论自我限定(50%)。
- **L5 诚实度**：局限声明(40)、负向/失败保留(35)、不确定性量化(25)。
- **L6 可用性**：有真实数据集+40；文献≥5→+30；有具体指标→+30。

## 输出格式

请严格按以下 JSON 格式输出，不要包含额外说明：

```json
{
  "composite": 综合分(0-100),
  "L0": 分数,
  "L1": 分数,
  "L2": 分数,
  "L3": 分数,
  "L4": 分数,
  "L5": 分数,
  "L6": 分数,
  "reason": "简要评语"
}
```"""

# ── 模式三：科学家评分 prompt ────────────────────────────────────
SCIENTIST_SYSTEM_PROMPT = """你是一位严谨但**建设性、鼓励型**的人类科学家（正教授/PI）。请把这份报告视为**探索性前期草案**（自动化生成的 smoke 草稿），按"建设性前期评审"给分。

## 评分原则
- **基础分约 70**，扎实处加分、薄弱处扣分，但**不按已发表顶刊标准苛责**。
- 整体落分区间：70–92。

## 偏好设定
1. 重单一清晰贡献，对泛泛而谈适度扣分（不归零）。
2. 理解代理/smoke 是可行性探测阶段，给"探索分"而非 0 分。
3. 对宏大命题审慎但肯定探索价值，不因题目大直接低分。
4. 欣赏真实数据+恰当方法+显著性检验，明确加分。
5. 看重领域深度，对跨学科拼贴温和扣分。
6. 对诚实局限声明明确加分，并作为整体温和正面项。
7. 对 AI 生成八股温和看待。
8. 偏好可复现（有代码/数据/协议加分）。

## 五维评分体系（权重）
| 维度 | 权重 |
|---|---|
| 选题价值 | 20% |
| 方法恰当性 | 25% |
| 证据强度 | 30% |
| 贡献清晰度 | 15% |
| 表达与诚实度 | 10% |

## 输出格式

请严格按以下 JSON 格式输出，不要包含额外说明：

```json
{
  "composite": 总分(0-100),
  "选题价值": 分数,
  "方法恰当性": 分数,
  "证据强度": 分数,
  "贡献清晰度": 分数,
  "表达与诚实度": 分数,
  "reason": "评语",
  "主要扣分点": "描述主要扣分原因"
}
```"""

class ReportEvaluationService:
    """报告质量评估服务"""

    MODE_SIMPLE = "simple"
    MODE_WEIGHTED = "weighted"
    MODE_SCIENTIST = "scientist"

    def evaluate(self, report: Report, mode: str) -> dict:
        """执行评估，返回结构化结果"""
        if mode not in (self.MODE_SIMPLE, self.MODE_WEIGHTED, self.MODE_SCIENTIST):
            raise ValueError(f"不支持的评估模式: {mode}")

        # 构建报告内容
        report_text = self._build_report_text(report)
        # 构建 prompt 并调用 LLM
        result = self._call_llm(report_text, mode)
        # 解析并标准化
        return self._normalize_result(result, mode)

    def _build_report_text(self, report: Report) -> str:
        """将 Report 模型组装为纯文本"""
        parts = []
        if report.title:
            parts.append(f"# {report.title}")
        if report.paper_title:
            parts.append(f"\n## 论文标题\n{report.paper_title}")
        if report.paper_abstract:
            parts.append(f"\n## 摘要\n{report.paper_abstract}")
        if report.problem_statement:
            parts.append(f"\n## 问题陈述\n{report.problem_statement}")
        if report.rationale:
            parts.append(f"\n## 原理依据\n{report.rationale}")
        if report.technical_details:
            parts.append(f"\n## 技术细节\n{report.technical_details}")
        if report.datasets:
            parts.append(f"\n## 数据集\n{report.datasets}")
        if report.source:
            parts.append(f"\n## 源数据\n{report.source}")
        if report.target:
            parts.append(f"\n## 目标\n{report.target}")
        if report.methods:
            parts.append(f"\n## 研究方法\n{report.methods}")
        if report.experiments:
            parts.append(f"\n## 实验设计\n{report.experiments}")
        if report.results:
            parts.append(f"\n## 预期结果\n{report.results}")
        if report.references:
            parts.append(f"\n## 参考文献\n{report.references}")
        # 如果 markdown_content 内容更完整，优先使用
        if report.markdown_content and len(report.markdown_content) > sum(len(p) for p in parts):
            return report.markdown_content
        return "\n\n".join(parts)

    def _call_llm(self, report_text: str, mode: str) -> dict:
        """调用 LLM 进行评估"""
        from app.services.qwen_client import qwen_chat

        if mode == self.MODE_SIMPLE:
            result_text = qwen_chat(
                prompt=f"请帮我客观评估这篇科研报告，给出评分（0-100）和简要评语。\n\n报告内容：\n\n{report_text[:10000]}",
                system_prompt="你是一位客观的科研报告评估专家。请以 JSON 格式输出 {{\"composite\": 分数, \"reason\": \"评语\"}}。",
                temperature=0.3,
            )
        elif mode == self.MODE_WEIGHTED:
            result_text = qwen_chat(
                prompt=f"请按七层加权模型评估以下报告：\n\n{report_text[:10000]}",
                system_prompt=WEIGHTED_SYSTEM_PROMPT,
                temperature=0.3,
            )
        elif mode == self.MODE_SCIENTIST:
            result_text = qwen_chat(
                prompt=f"请以科学家人格评估以下报告：\n\n{report_text[:10000]}",
                system_prompt=SCIENTIST_SYSTEM_PROMPT,
                temperature=0.3,
            )
        else:
            raise ValueError(f"不支持的评估模式: {mode}")

        if not result_text or not result_text.strip():
            return {"composite": 0, "error": "LLM 返回空结果"}

        # 尝试提取 JSON
        raw = result_text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0] if "```" in raw else raw
            raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[报告评估] LLM 返回非 JSON 格式: {raw[:200]}")
            return {"composite": 0, "reason": raw[:500], "error": "LLM 返回格式非 JSON"}

    def _normalize_result(self, result: dict, mode: str) -> dict:
        """标准化输出格式"""
        normalized = {
            "mode": mode,
            "composite": result.get("composite", result.get("总分", 0)),
            "reason": result.get("reason", result.get("评语", "")),
        }
        if mode == self.MODE_WEIGHTED:
            for k in ("L0", "L1", "L2", "L3", "L4", "L5", "L6"):
                normalized[k] = result.get(k, 0)
        elif mode == self.MODE_SCIENTIST:
            for k in ("选题价值", "方法恰当性", "证据强度", "贡献清晰度", "表达与诚实度"):
                normalized[k] = result.get(k, 0)
            normalized["主要扣分点"] = result.get("主要扣分点", "")
        if "error" in result:
            normalized["error"] = result["error"]
        return normalized