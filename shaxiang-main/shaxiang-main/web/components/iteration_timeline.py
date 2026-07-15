import streamlit as st
from pathlib import Path


def render_iteration_timeline(iterations: list[dict]):
    """渲染迭代时间线

    Args:
        iterations: 从 get_experiment_with_iterations 返回的迭代列表
    """
    if not iterations:
        st.info("暂无迭代记录")
        return

    # 反转以最新轮次在上
    for it in reversed(iterations):
        num = it["iteration_number"]
        status = it["status"]
        metrics = it.get("metrics", {})
        plan = it.get("plan", {})
        result = it.get("result", {})
        analysis = it.get("analysis", {})
        decision = it.get("decision", {})
        duration = it.get("duration_seconds", 0)

        # 状态标签颜色
        status_map = {
            "success": ("✅ 成功", "green"),
            "failed": ("❌ 失败", "red"),
            "partial": ("⚠️ 部分成功", "orange"),
        }
        status_text, status_color = status_map.get(status, ("⏳ 待定", "gray"))

        # 头部
        header_cols = st.columns([1, 3, 1, 1])
        with header_cols[0]:
            st.markdown(f"### 第 {num} 轮")
        with header_cols[1]:
            st.markdown(f"**方案**: {plan.get('title', '未知')}")
        with header_cols[2]:
            st.markdown(status_text)
        with header_cols[3]:
            st.caption(f"耗时 {duration:.1f}s")

        st.divider()

        # ===== 图表展示区域 =====
        chart_paths = _extract_chart_paths(result)
        viz_notes = _viz_note_map(analysis)
        if chart_paths:
            st.markdown("**📊 可视化结果**")
            chart_cols = st.columns(min(len(chart_paths), 3))
            for i, cp in enumerate(chart_paths):
                with chart_cols[i % len(chart_cols)]:
                    try:
                        st.image(cp, use_container_width=True)
                    except Exception:
                        st.caption(f"图表加载失败: {Path(cp).name}")
                    note = viz_notes.get(Path(cp).name.lower()) or viz_notes.get(str(i))
                    if note:
                        st.caption(note)
            st.divider()

        # 核心指标卡片
        metric_cols = st.columns(len(metrics) if metrics else 1)
        for i, (k, v) in enumerate(metrics.items()):
            if k in ("iteration", "sample_size", "dosage", "frequency"):
                continue
            if isinstance(v, (int, float)):
                with metric_cols[i % len(metric_cols)]:
                    st.metric(label=k.replace("_", " ").title(), value=f"{v:.4f}")

        # 可展开详情
        col1, col2 = st.columns(2)

        with col1:
            with st.expander("📋 实验方案", expanded=(num == len(iterations))):
                st.markdown(f"**描述**: {plan.get('description', '')}")
                st.markdown(f"**方法**: {plan.get('methodology', '')}")
                params = plan.get('parameters', {})
                if params:
                    st.markdown("**参数**:")
                    for pk, pv in params.items():
                        st.markdown(f"  - {pk}: {pv}")
                criteria = plan.get('success_criteria', [])
                if criteria:
                    st.markdown("**成功标准**:")
                    for c in criteria:
                        st.markdown(f"  - {c}")

            with st.expander("📝 执行日志"):
                raw_output = result.get("raw_output", {})
                script_log = raw_output.get("script_log", "") if isinstance(raw_output, dict) else ""
                if script_log:
                    st.code(script_log, language="text")
                else:
                    st.caption("无执行日志")

        with col2:
            with st.expander("🔍 分析报告"):
                assessment = analysis.get("overall_assessment", "unknown")
                assessment_emoji = {
                    "success": "🎯",
                    "promising": "📈",
                    "needs_adjustment": "🔧",
                    "significant_issue": "⚠️",
                }.get(assessment, "❓")
                st.markdown(f"**整体评估**: {assessment_emoji} {assessment}")
                st.markdown(f"**摘要**: {analysis.get('summary', '')}")

                viz_list = analysis.get("visualization_notes") or []
                if viz_list:
                    st.markdown("**可视化解读**:")
                    for note in viz_list:
                        if isinstance(note, dict):
                            name = (note.get("chart_name") or "").strip()
                            desc = (note.get("description") or "").strip()
                        else:
                            name, desc = "", str(note)
                        if not desc:
                            continue
                        if name:
                            st.markdown(f"  - **{name}**: {desc}")
                        else:
                            st.markdown(f"  - {desc}")

                findings = analysis.get("findings", [])
                if findings:
                    st.markdown("**关键发现**:")
                    for f in findings:
                        st.markdown(f"  - {f}")

                issues = analysis.get("identified_issues", [])
                if issues:
                    st.markdown("**识别的问题**:")
                    for i in issues:
                        st.markdown(f"  - ⚠️ {i}")

                adjustments = analysis.get("suggested_adjustments", [])
                if adjustments:
                    st.markdown("**建议调整**:")
                    for a in adjustments:
                        st.markdown(f"  - 💡 {a}")

            with st.expander("🧭 迭代决策"):
                should_continue = decision.get("should_continue", True)
                st.markdown(f"**继续迭代**: {'✅ 是' if should_continue else '❌ 否'}")
                st.markdown(f"**预期改进**: {decision.get('expected_improvement', '')}")
                focus = decision.get("focus_areas", [])
                if focus:
                    st.markdown("**重点关注**:")
                    for f in focus:
                        st.markdown(f"  - {f}")
                adj = decision.get("next_plan_adjustments", [])
                if adj:
                    st.markdown("**方案调整方向**:")
                    for a in adj:
                        st.markdown(f"  - 🔄 {a}")

        st.divider()


def _extract_chart_paths(result: dict) -> list[str]:
    """从迭代结果中提取图表文件路径"""
    if not result or not isinstance(result, dict):
        return []

    # 尝试多个位置
    # 1. result["raw_output"]["chart_paths"]
    raw = result.get("raw_output", {})
    if isinstance(raw, dict):
        paths = raw.get("chart_paths", [])
        if paths:
            return [p for p in paths if isinstance(p, str) and Path(p).exists()]

    # 2. result["data_points"] 中的 chart 路径
    data_points = result.get("data_points", [])
    chart_paths = []
    for dp in data_points:
        if isinstance(dp, dict) and dp.get("key") == "chart_path":
            val = dp.get("value")
            if isinstance(val, str) and Path(val).exists():
                chart_paths.append(val)
        elif hasattr(dp, 'key') and dp.key == "chart_path":
            if hasattr(dp, 'value') and isinstance(dp.value, str) and Path(dp.value).exists():
                chart_paths.append(dp.value)

    return chart_paths


def _viz_note_map(analysis: dict) -> dict[str, str]:
    """chart_name(小写) / 序号 → 简介，供图下 caption 使用。"""
    if not isinstance(analysis, dict):
        return {}
    out: dict[str, str] = {}
    for i, note in enumerate(analysis.get("visualization_notes") or []):
        if not isinstance(note, dict):
            continue
        desc = (note.get("description") or "").strip()
        if not desc:
            continue
        name = (note.get("chart_name") or "").strip()
        if name:
            out[Path(name).name.lower()] = desc
        out[str(i)] = desc
    return out
