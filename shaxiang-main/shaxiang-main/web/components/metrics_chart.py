import plotly.graph_objects as go
import streamlit as st
import pandas as pd


# 元信息/噪声字段，不进入趋势图
_EXCLUDE_COLS = {
    "iteration", "sample_size", "dosage", "frequency",
    "dataset_rows", "dataset_columns", "error", "run_scope",
}


def render_metrics_trend(metrics_history: list[dict]):
    """渲染指标趋势折线图

    Args:
        metrics_history: [{"iteration": 1, "efficacy_score": 0.45, "overall_score": 0.40, ...}, ...]
    """
    if not metrics_history:
        st.info("暂无指标数据")
        return

    scopes = {(m or {}).get("run_scope") for m in metrics_history if (m or {}).get("run_scope")}
    if scopes:
        label = " / ".join(sorted(str(s) for s in scopes if s))
        st.caption(f"运行范围标记 run_scope: {label}（smoke=小样本验收，full=正式全量）")

    df = pd.DataFrame(metrics_history)
    if "iteration" not in df.columns:
        st.info("暂无可视化指标")
        return

    metric_cols = [
        c for c in df.columns
        if c not in _EXCLUDE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    # 优先展示接近 0-1 的评分类指标；避免把超大计数画进趋势图后被裁切成“空图”
    score_cols = []
    for c in metric_cols:
        series = df[c].dropna()
        if series.empty:
            continue
        vmin, vmax = float(series.min()), float(series.max())
        if vmin >= -0.05 and vmax <= 1.5:
            score_cols.append(c)

    plot_cols = score_cols or metric_cols
    if not plot_cols:
        st.info("暂无可视化指标（本轮可能只有执行错误或元数据，没有有效评分）")
        if any("error" in (m or {}) for m in metrics_history):
            st.warning("检测到执行错误指标（error=1）。请查看迭代历史里的执行日志。")
        return

    colors = {
        "efficacy_score": "#2ecc71",
        "side_effect_score": "#e74c3c",
        "overall_score": "#3498db",
    }

    fig = go.Figure()
    for col in plot_cols:
        ys = df[col]
        fig.add_trace(go.Scatter(
            x=df["iteration"],
            y=ys,
            mode='lines+markers+text',
            name=col.replace("_", " ").title(),
            line=dict(color=colors.get(col, "#95a5a6"), width=2),
            marker=dict(size=10),
            text=[f"{v:.3f}" if pd.notna(v) else "" for v in ys],
            textposition="top center",
            textfont=dict(size=10),
        ))

    y_all = pd.concat([df[c] for c in plot_cols], axis=0).dropna()
    if not y_all.empty and float(y_all.min()) >= -0.05 and float(y_all.max()) <= 1.5:
        yaxis = dict(range=[-0.05, 1.1])
    else:
        yaxis = dict(autorange=True)

    fig.update_layout(
        title="实验指标趋势",
        xaxis_title="迭代轮次",
        yaxis_title="指标值",
        yaxis=yaxis,
        xaxis=dict(dtick=1),
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)
