import streamlit as st
from services.experiment_service import ExperimentService


def render():
    st.title("新建实验")
    st.markdown("输入你的**实验假设**，AI 将推荐经典数据集帮助你验证")

    # 实验类型选择
    col1, col2 = st.columns(2)
    with col1:
        experiment_type = st.radio("实验类型", ["假设验证（数据驱动）", "模拟实验"], horizontal=True)
    with col2:
        max_iterations = st.slider("最大迭代轮数", 1, 20, 10)

    is_data_driven = "数据驱动" in experiment_type
    executor_type = "sandbox" if is_data_driven else "simulation"

    # 实验假设（核心输入）
    hypothesis = st.text_area(
        "实验假设",
        placeholder="例如：在自然语言处理任务中，使用 Few-shot prompting 比 Zero-shot prompting 的准确率提升至少 10%",
        height=120,
        help="清晰陈述你的实验假设",
    )

    # 研究目标（辅助说明）
    research_goal = st.text_area(
        "研究目标（可选，辅助说明）",
        placeholder="描述更广泛的研究背景和目标...",
        height=80,
    )

    # 约束条件
    st.markdown("### 约束条件")
    if "constraint_count" not in st.session_state:
        st.session_state["constraint_count"] = 3

    constraints = []
    for i in range(st.session_state["constraint_count"]):
        c = st.text_input(f"约束 {i+1}", key=f"constraint_{i}", placeholder="例如：样本量不少于 1000")
        if c:
            constraints.append(c)

    if st.button("+ 添加更多约束"):
        st.session_state["constraint_count"] += 1

    st.divider()

    # 创建按钮
    if st.button("🚀 创建实验", type="primary", use_container_width=True, disabled=not hypothesis):
        with st.spinner("正在创建实验..."):
            try:
                service = ExperimentService.get_instance()
                experiment = service.create_experiment(
                    title=hypothesis[:30] + ("..." if len(hypothesis) > 30 else ""),
                    research_goal=research_goal or hypothesis,
                    constraints=constraints,
                    executor_type=executor_type,
                    max_iterations=max_iterations,
                )
                experiment.hypothesis = hypothesis
                from storage.sqlite_store import SQLiteRepository
                repo = SQLiteRepository(service.config.storage.db_path)
                repo.update_experiment(experiment)

                st.session_state["new_experiment_id"] = experiment.id
                st.session_state["selected_experiment_id"] = experiment.id
                st.session_state["pending_detail_jump"] = True
                st.session_state["create_message"] = f"实验已创建！ID: {experiment.id[:8]}"

                if is_data_driven:
                    with st.spinner("正在推荐经典数据集..."):
                        service.recommend_datasets(experiment.id)
                    st.session_state["current_phase"] = "data_recommended"
                    st.session_state["create_message"] = (
                        f"实验已创建！ID: {experiment.id[:8]}。已完成经典数据集推荐，可进入详情页继续。"
                    )
            except Exception as e:
                st.session_state.pop("pending_detail_jump", None)
                st.error(f"创建失败: {e}")

    # 按钮必须放在创建逻辑外，否则下一轮 rerun 后会消失
    if st.session_state.get("pending_detail_jump") and st.session_state.get("selected_experiment_id"):
        st.success(st.session_state.get("create_message", "实验已创建"))
        if st.button("查看实验详情 →", type="primary", use_container_width=True):
            st.session_state.pop("pending_detail_jump", None)
            st.switch_page("pages/3_experiment_detail.py")


render()
