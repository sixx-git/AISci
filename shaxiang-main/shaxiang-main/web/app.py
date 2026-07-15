import streamlit as st
import sys
from pathlib import Path

# 确保项目根目录在 path 中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 页面配置
st.set_page_config(
    page_title="AI 迭代实验设计系统",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 全局自定义样式
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        border-radius: 8px;
        padding: 12px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.title("🔬 AI 实验引擎")
    st.markdown("---")
    st.markdown("### 导航")
    st.page_link("pages/1_dashboard.py", label="📊 仪表盘", icon="📊")
    st.page_link("pages/2_new_experiment.py", label="➕ 新建实验", icon="➕")
    st.page_link("pages/3_experiment_detail.py", label="📄 实验详情", icon="📄")
    st.markdown("---")
    st.caption("AI 驱动的闭环迭代实验设计系统")
    st.caption("Plan → Execute → Analyze → Reflect")

# 主页内容
st.title("🔬 AI 迭代实验设计系统")
st.markdown("""
### 欢迎使用 AI 迭代实验设计系统

本系统展示 AI 如何通过 **闭环迭代** 逐步优化实验方案：

1. **📋 规划 (Plan)** — AI 根据研究目标设计实验方案
2. **⚡ 执行 (Execute)** — 运行实验并获取数据
3. **🔍 分析 (Analyze)** — AI 分析结果，评估效果
4. **🧭 反思 (Reflect)** — AI 根据分析调整下一轮方案

点击左侧 **新建实验** 开始体验！
""")

# 快速统计
from services.experiment_service import ExperimentService
service = ExperimentService.get_instance()
all_exps = service.list_all_experiments()
if all_exps:
    col1, col2 = st.columns(2)
    with col1:
        st.metric("总实验数", len(all_exps))
    with col2:
        running = len([e for e in all_exps if e.status.value == "running"])
        st.metric("运行中", running)
