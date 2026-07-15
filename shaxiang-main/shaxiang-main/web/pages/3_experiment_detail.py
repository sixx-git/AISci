import streamlit as st
import json
from pathlib import Path
from services.experiment_service import ExperimentService
from web.components.metrics_chart import render_metrics_trend
from web.components.iteration_timeline import render_iteration_timeline


def render():
    service = ExperimentService.get_instance()

    # 获取实验 ID（优先从 session_state 获取，兼容多种跳转方式）
    experiment_id = st.session_state.get("selected_experiment_id")
    if not experiment_id:
        experiment_id = st.query_params.get("id", None)
    if not experiment_id:
        experiment_id = st.session_state.get("new_experiment_id")

    if not experiment_id:
        st.warning("尚未选择实验。请从下方列表进入，或返回仪表盘。")
        experiments = service.list_all_experiments()
        if experiments:
            options = {f"{e.title} ({e.id[:8]})": e.id for e in experiments}
            selected_label = st.selectbox("选择实验", list(options.keys()))
            if st.button("打开实验详情", type="primary", use_container_width=True):
                st.session_state["selected_experiment_id"] = options[selected_label]
                st.rerun()
        else:
            st.info("暂无实验")
        if st.button("返回仪表盘"):
            st.switch_page("pages/1_dashboard.py")
        return

    # 只用 session 记住当前实验，避免在跳转 callback 中写 query_params/rerun
    st.session_state["selected_experiment_id"] = experiment_id

    # 加载实验数据
    experiment = service.get_experiment(experiment_id)
    if not experiment:
        st.error("实验不存在")
        st.session_state.pop("selected_experiment_id", None)
        if st.button("返回"):
            st.switch_page("pages/1_dashboard.py")
        return

    phase = getattr(experiment, 'phase', 'created')

    # ===== 标题和状态 =====
    status_emoji = {
        "created": "📋", "data_recommended": "📂", "data_uploaded": "📁",
        "script_designed": "📝", "running": "🔄", "completed": "✅", "failed": "❌",
    }.get(phase, "❓")

    st.title(f"{status_emoji} {experiment.title}")
    st.markdown(f"**阶段**: {phase}  |  **迭代**: {experiment.current_iteration}/{experiment.max_iterations}")

    # 导航按钮
    col_back, col_del, col_right = st.columns([1, 1, 4])
    with col_back:
        if st.button("🏠 返回列表", use_container_width=True):
            st.switch_page("pages/1_dashboard.py")
    with col_del:
        del_confirm_key = f"confirm_delete_detail_{experiment_id}"
        if not st.session_state.get(del_confirm_key, False):
            if st.button("🗑️ 删除", use_container_width=True):
                st.session_state[del_confirm_key] = True
                st.rerun()
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确认", key="del_yes", use_container_width=True):
                    service.delete_experiment(experiment_id)
                    st.session_state.pop(del_confirm_key, None)
                    st.session_state.pop("selected_experiment_id", None)
                    st.switch_page("pages/1_dashboard.py")
            with c2:
                if st.button("❌ 取消", key="del_no", use_container_width=True):
                    st.session_state.pop(del_confirm_key, None)
                    st.rerun()

    st.divider()

    # ===== 实验假设展示 =====
    hypothesis = getattr(experiment, 'hypothesis', '') or experiment.research_goal
    if hypothesis:
        with st.expander("📌 实验假设", expanded=True):
            st.markdown(f"> {hypothesis}")
            for c in experiment.constraints:
                st.markdown(f"- 约束: {c}")

    # ===== 按阶段展示不同内容 =====

    # --- Phase: data_recommended ---
    if phase in ("created", "data_recommended"):
        st.subheader("📂 推荐数据集")

        recommendations = getattr(experiment, 'dataset_recommendations', None)
        if recommendations:
            required = [d for d in recommendations if d.get("is_required")]
            optional = [d for d in recommendations if not d.get("is_required")]

            if required:
                st.markdown("**必须上传的数据集：**")
                for d in required:
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{d['name']}**")
                            st.caption(d.get('description', ''))
                            st.markdown(f"推荐理由: {d.get('reason', '')}")
                            if d.get('download_url'):
                                st.markdown(f"下载链接: {d['download_url']}")
                            if d.get('expected_columns'):
                                st.caption(f"预期字段: {', '.join(d['expected_columns'])}")
                            if d.get('size_hint'):
                                st.caption(f"大小: {d['size_hint']}")
                        with col2:
                            st.caption(f"格式: {d.get('file_format', '?')}")
                    st.divider()

            if optional:
                with st.expander("可选补充数据集"):
                    for d in optional:
                        st.markdown(f"- **{d['name']}**: {d.get('reason', '')}")
                        if d.get('download_url'):
                            st.caption(f"  下载: {d['download_url']}")
        else:
            st.info("暂无数据集推荐。点击下方按钮让 AI 推荐，或直接上传你的数据。")

        # 操作按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 推荐数据集", type="primary", use_container_width=True):
                with st.spinner("AI 正在分析假设并推荐数据集..."):
                    try:
                        report = service.recommend_datasets(experiment_id)
                        st.success(f"已推荐 {len(report.recommended_datasets)} 个数据集")
                    except Exception as e:
                        st.error(f"推荐失败: {e}")

    # --- 上传数据区域（始终显示） ---
    if phase not in ("running", "completed"):
        st.subheader("📁 上传数据集")

        # 先选数据源类型，再根据类型显示不同的输入方式
        source_type = st.radio(
            "数据源类型",
            ["📂 上传文件", "📁 本地目录路径", "🔗 本地文件路径", "🤗 HuggingFace"],
            horizontal=True,
            help="选择数据来源方式",
        )
        # 映射到内部 source_type
        source_type_map = {
            "📂 上传文件": "uploaded",
            "📁 本地目录路径": "directory",
            "🔗 本地文件路径": "local_csv",
            "🤗 HuggingFace": "huggingface",
        }
        actual_source_type = source_type_map[source_type]

        uploaded_file = None
        file_path = ""
        profile_name = ""

        if source_type == "📂 上传文件":
            uploaded_file = st.file_uploader(
                "选择数据文件",
                type=["csv", "json", "jsonl", "parquet", "xlsx", "tsv"],
                help="支持 CSV, JSON, Parquet, Excel, TSV 格式",
            )
            st.caption("💡 点击上方按钮选择本地文件上传")

        elif source_type == "📁 本地目录路径":
            st.info("📌 **操作方式**：打开文件资源管理器，进入数据集文件夹，点击地址栏复制完整路径，粘贴到下方输入框")
            file_path = st.text_input(
                "数据集目录路径",
                placeholder=r"例如: D:\浏览器\b62cb-main\b62cb-main\SisFall",
                help="粘贴数据集文件夹的完整路径",
            )
            profile_name = st.selectbox(
                "选择数据集 Profile",
                ["", "SisFall", "MobiAct", "UCI_HAR", "AutoDetect"],
                help="选择预置 Profile，或选 AutoDetect 让 AI 自动识别格式",
            )

        elif source_type == "🔗 本地文件路径":
            st.info("📌 **操作方式**：右键点击数据文件 →「复制文件路径」，粘贴到下方")
            file_path = st.text_input(
                "文件路径",
                placeholder=r"例如: D:\data\my_dataset.csv",
            )
            file_ext = Path(file_path).suffix.lower() if file_path else ""
            if file_ext in (".json", ".jsonl"):
                actual_source_type = "local_json"

        elif source_type == "🤗 HuggingFace":
            file_path = st.text_input(
                "HuggingFace 数据集 ID",
                placeholder="例如: scikit-learn/iris",
            )

        # 自动识别（directory 模式下）
        if actual_source_type == "directory" and profile_name == "AutoDetect":
            st.caption(
                "提示：SisFall / MobiAct / UCI_HAR 请优先选预置 Profile。"
                "AutoDetect 支持表格，以及图片/音频目录（labels.csv 或 ImageFolder 类别子目录）。"
            )
            if file_path:
                if st.button("🔍 自动识别并试加载验证", type="secondary"):
                    with st.spinner("AI 正在分析数据集结构，并试加载采样数据..."):
                        try:
                            import json
                            experiment = service.get_experiment(experiment_id)
                            hypothesis = getattr(experiment, 'hypothesis', '') or experiment.research_goal
                            profile = service.auto_detect_profile(file_path, hypothesis_hint=hypothesis)
                            st.session_state["detected_profile"] = profile.to_dict()
                            # 强制试加载；失败则不可进入设计脚本
                            verify_cfg = {
                                "source_type": "directory",
                                "source_path": file_path,
                                "profile_json": json.dumps(profile.to_dict()),
                                "preprocessing_steps": [],
                                "sample_size": 5000,
                            }
                            preview = service.verify_data_config(verify_cfg, sample_size=5000)
                            st.session_state["data_preview"] = preview
                            st.session_state["profile_confirmed"] = False
                            modality = preview.get("modality") or getattr(profile, "modality", "tabular")
                            st.success(
                                f"识别并试加载成功: {profile.name} | modality={modality} | "
                                f"{preview.get('row_count')} 行 | "
                                f"数值列 {len(preview.get('numeric_columns') or [])} | "
                                f"路径列 {preview.get('media_path_column') or '-'}"
                            )
                        except Exception as e:
                            st.session_state.pop("detected_profile", None)
                            st.session_state.pop("data_preview", None)
                            st.session_state.pop("profile_confirmed", None)
                            st.error(f"识别/试加载失败，已阻断设计脚本: {e}")
            else:
                st.warning("请先在上方输入数据集目录路径")

        # 显示识别结果 + 试加载预览
        if st.session_state.get("detected_profile"):
            with st.expander("🔍 识别的数据集配置", expanded=True):
                st.json(st.session_state["detected_profile"])
            if st.session_state.get("data_preview"):
                with st.expander("📋 试加载列契约预览", expanded=True):
                    preview = st.session_state["data_preview"]
                    st.write({
                        "modality": preview.get("modality") or st.session_state.get("detected_profile", {}).get("modality"),
                        "row_count": preview.get("row_count"),
                        "column_count": preview.get("column_count"),
                        "numeric_columns": preview.get("numeric_columns"),
                        "non_numeric_columns": preview.get("non_numeric_columns"),
                        "suggested_target_columns": preview.get("suggested_target_columns"),
                        "media_path_column": preview.get("media_path_column"),
                        "sample_paths": preview.get("sample_paths"),
                        "label_distribution": preview.get("label_distribution"),
                    })
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ 确认使用此配置", type="primary"):
                        st.session_state["profile_confirmed"] = True
                        st.success("已确认配置，可点击下方设计脚本")
                with c2:
                    if st.button("❌ 清除重新识别"):
                        st.session_state.pop("detected_profile", None)
                        st.session_state.pop("data_preview", None)
                        st.session_state.pop("profile_confirmed", None)

        autodetect_blocked = (
            actual_source_type == "directory"
            and profile_name == "AutoDetect"
            and not st.session_state.get("profile_confirmed")
        )
        if autodetect_blocked:
            st.warning("AutoDetect 模式下，请先完成「识别并试加载验证」并确认配置，才能设计脚本。")

        # 提交按钮
        if st.button(
            "🚀 确认并设计分析脚本",
            type="primary",
            use_container_width=True,
            disabled=(not uploaded_file and not file_path) or autodetect_blocked,
        ):
            if uploaded_file or file_path:
                with st.spinner("正在设计脚本：生成 → 试跑 → 按报错自动修补（IDE 式，可能需几分钟）..."):
                    try:
                        import os
                        import json
                        save_path = None
                        if uploaded_file:
                            save_dir = "data/uploads"
                            os.makedirs(save_dir, exist_ok=True)
                            save_path = os.path.join(save_dir, uploaded_file.name)
                            with open(save_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            actual_source_type = "uploaded"
                            file_path = save_path

                        data_config = {
                            "source_type": actual_source_type,
                            "source_path": file_path or "",
                            "preprocessing_steps": [],
                            "sample_size": 0,
                        }
                        if actual_source_type == "directory":
                            if profile_name and profile_name != "AutoDetect":
                                data_config["profile_name"] = profile_name
                            elif st.session_state.get("detected_profile"):
                                data_config["profile_json"] = json.dumps(st.session_state["detected_profile"])
                            else:
                                raise ValueError("directory 模式需要选择预置 Profile 或完成 AutoDetect 确认")

                        # 设计前再验一次数据可用性
                        service.verify_data_config({**data_config, "sample_size": 5000}, sample_size=5000)
                        plan = service.design_script(experiment_id, data_config)
                        st.success("分析脚本已设计完成，并已通过小样本试跑门禁！")
                        st.session_state["show_upload"] = False
                        st.session_state.pop("detected_profile", None)
                        st.session_state.pop("data_preview", None)
                        st.session_state.pop("profile_confirmed", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"处理失败: {e}")
            else:
                st.warning("请先上传文件或指定数据路径")

    # --- Phase: script_designed / running / 执行和分析 ---
    if phase in ("script_designed", "running") or (
        experiment.executor_type == "sandbox" and experiment.initial_plan is not None
        and phase not in ("completed", "failed")
    ):
        data = service.get_experiment_with_iterations(experiment_id)
        iterations = data["iterations"]

        # 运行模式开关：默认仅小样本 smoke，打开后才正式全量推演
        if experiment.executor_type == "sandbox":
            st.subheader("⚡ 运行模式")
            current_mode = (getattr(experiment, "run_mode", None) or "smoke_only").lower()
            full_on = st.toggle(
                "正式全量推演",
                value=(current_mode == "full"),
                help=(
                    "关闭（推荐）：仅小样验收；大模型可按任务/类不平衡动态设定 script_params.sample_size"
                    "（约 2000~80000，分层采样），smoke 通过即本轮完成，图在 data/charts/smoke。\n"
                    "打开：smoke 通过后再正式全量推演，图进 data/charts，可能很慢。"
                ),
                key=f"full_run_toggle_{experiment_id}",
            )
            desired = "full" if full_on else "smoke_only"
            if desired != current_mode:
                try:
                    experiment = service.set_run_mode(experiment_id, desired)
                    st.rerun()
                except Exception as e:
                    st.error(f"切换运行模式失败: {e}")
            if desired == "smoke_only":
                sp = {}
                if experiment.initial_plan is not None:
                    sp = dict(getattr(experiment.initial_plan, "script_params", None) or {})
                    params = getattr(experiment.initial_plan, "parameters", None) or {}
                    if isinstance(params.get("script_params"), dict):
                        sp.update(params["script_params"])
                n = sp.get("sample_size")
                n_txt = f"，当前计划 sample_size≈{n}" if n else ""
                st.caption(
                    f"当前：动态小样验收（关闭全量）。LLM 可按需调整抽取行数{n_txt}；不会加载数百万行全表。"
                )
            else:
                st.warning("当前：正式全量推演。smoke 通过后会再跑正式数据，可能非常耗时。")

        # 操作按钮
        col1, col2 = st.columns(2)
        with col1:
            smoke_only = (getattr(experiment, "run_mode", "smoke_only") or "smoke_only") == "smoke_only"
            btn_label = "▶️ 执行下一轮（smoke）" if smoke_only else "▶️ 执行下一轮（全量）"
            if st.button(btn_label, type="primary", use_container_width=True):
                spinner_msg = (
                    "正在脚本迭代 + 动态小样验收（按 sample_size 分层抽样，不会全量加载）..."
                    if smoke_only
                    else "正在执行迭代（含正式全量推演，可能很久）..."
                )
                with st.spinner(spinner_msg):
                    try:
                        record = service.run_iteration(experiment_id)
                        scope = (record.metrics or {}).get("run_scope", "?")
                        if record.status == "failed":
                            st.error(f"第 {record.iteration_number} 轮执行失败: {record.error_message}")
                        else:
                            st.success(
                                f"第 {record.iteration_number} 轮完成（run_scope={scope}）"
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(f"迭代失败: {e}")
        with col2:
            if phase == "running" or experiment.current_iteration > 0:
                if st.button("🔄 自动运行至完成", use_container_width=True):
                    with st.spinner("正在自动运行..."):
                        try:
                            service.run_full_experiment(experiment_id)
                            st.success("实验已完成！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"运行失败: {e}")

        st.divider()

        # 指标趋势图
        metrics_history = service.get_improvement_metrics(experiment_id)
        if metrics_history:
            render_metrics_trend(metrics_history)

        # 迭代时间线
        if iterations:
            st.subheader("迭代历史")
            render_iteration_timeline(iterations)

        # 人工反馈区
        st.divider()
        st.subheader("💬 人工反馈（写入后会进入下一轮脚本迭代）")
        st.caption(
            "可贴脚本片段、图表问题与修改方向。"
            "系统已取消「成功只调参」：每轮都会基于脚本 + 分析意见 + 数据集列契约重写脚本，"
            "并用 IDE 式试跑修补保证可运行。也可点「重新设计脚本」立即生效。"
        )
        existing_fb = getattr(experiment, "human_feedback", None) or ""
        if "feedback_input" not in st.session_state and existing_fb:
            st.session_state["feedback_input"] = existing_fb
        feedback_text = st.text_area(
            "输入你的反馈",
            placeholder=(
                "例如：\n"
                "1) 当前 Accuracy=1.0 疑似行级泄漏，请改为 GroupKFold(按 sensor/受试者)\n"
                "2) feature 只用传感器数值列，排除 activity_type\n"
                "3) 增加类别分布图与逻辑回归基线\n"
                "（也可粘贴脚本片段并指出要改的函数）"
            ),
            height=180,
            key="feedback_input",
        )
        fb_status = getattr(experiment, "feedback_status", "none")
        if existing_fb:
            st.info(f"当前反馈状态: `{fb_status}`")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📝 提交反馈", use_container_width=True, disabled=not feedback_text):
                service.submit_feedback(experiment_id, feedback_text)
                st.success("反馈已提交！下一轮迭代将解锁脚本重写；或直接点右侧重设计。")
                st.rerun()
        with col2:
            if st.button("🤖 基于反馈推荐新数据集", use_container_width=True):
                with st.spinner("AI 正在根据反馈推荐新数据集..."):
                    try:
                        report = service.recommend_datasets(experiment_id, human_feedback=feedback_text)
                        st.success(f"已推荐 {len(report.recommended_datasets)} 个新数据集")
                        st.rerun()
                    except Exception as e:
                        st.error(f"推荐失败: {e}")
        with col3:
            if st.button("🔄 基于反馈重新设计脚本", use_container_width=True, disabled=not feedback_text):
                with st.spinner("按反馈高自由度重设计：生成 → 试跑 → 自动修补（可能需几分钟）..."):
                    try:
                        plan = service.redesign_script_from_feedback(experiment_id, feedback_text)
                        st.success(
                            f"脚本已按反馈重设计并通过试跑门禁：{getattr(plan, 'title', '')}"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"设计失败: {e}")

    # --- Phase: completed ---
    if phase == "completed":
        data = service.get_experiment_with_iterations(experiment_id)
        iterations = data["iterations"]

        st.success("🎉 实验已完成！")

        metrics_history = service.get_improvement_metrics(experiment_id)
        if metrics_history:
            render_metrics_trend(metrics_history)

        if iterations:
            st.subheader("迭代历史")
            render_iteration_timeline(iterations)


render()
