import streamlit as st
from services.experiment_service import ExperimentService


def render():
    st.title("🔬 AI 迭代实验设计系统")
    st.markdown("通过 AI 驱动的假设验证闭环迭代，逐步优化实验方案")

    service = ExperimentService.get_instance()

    # 统计卡片
    all_experiments = service.list_all_experiments()
    running = [e for e in all_experiments if getattr(e, 'status', None) and e.status.value in ("running",)]
    completed = [e for e in all_experiments if getattr(e, 'status', None) and e.status.value == "completed"]
    created = [e for e in all_experiments if getattr(e, 'status', None) and e.status.value == "created"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总实验数", len(all_experiments))
    with col2:
        st.metric("运行中", len(running))
    with col3:
        st.metric("已完成", len(completed))
    with col4:
        st.metric("待启动", len(created))

    st.divider()

    # 实验列表
    st.subheader("实验列表")
    if not all_experiments:
        st.info("暂无实验，点击下方按钮创建新实验")
    else:
        for exp in all_experiments:
            phase = getattr(exp, 'phase', 'created')
            status_val = exp.status.value if exp.status else 'created'
            phase_emoji = {
                "created": "📋", "data_recommended": "📂", "data_uploaded": "📁",
                "script_designed": "📝", "running": "🔄", "completed": "✅",
            }.get(phase, "❓")

            # 确认删除状态
            confirm_key = f"confirm_delete_{exp.id}"

            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            with col1:
                st.markdown(f"{phase_emoji} **{exp.title}**")
                hypothesis = getattr(exp, 'hypothesis', '')
                if hypothesis:
                    st.caption(hypothesis[:80] + ("..." if len(hypothesis) > 80 else ""))
                else:
                    st.caption(exp.research_goal[:80] + ("..." if len(exp.research_goal) > 80 else ""))
            with col2:
                st.markdown(f"阶段: {phase}")
            with col3:
                st.markdown(f"{exp.current_iteration}/{exp.max_iterations}轮")
            with col4:
                if st.button("查看", key=f"view_{exp.id}", use_container_width=True):
                    st.session_state["selected_experiment_id"] = exp.id
                    st.switch_page("pages/3_experiment_detail.py")
            with col5:
                if not st.session_state.get(confirm_key, False):
                    if st.button("🗑️", key=f"del_{exp.id}", use_container_width=True):
                        st.session_state[confirm_key] = True
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅", key=f"yes_{exp.id}", use_container_width=True):
                            service.delete_experiment(exp.id)
                            st.session_state.pop(confirm_key, None)
                            st.success("已删除")
                    with c2:
                        if st.button("❌", key=f"no_{exp.id}", use_container_width=True):
                            st.session_state.pop(confirm_key, None)

    st.divider()
    if st.button("➕ 新建实验", type="primary", use_container_width=True):
        st.switch_page("pages/2_new_experiment.py")


render()
