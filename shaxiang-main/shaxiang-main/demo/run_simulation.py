"""
命令行演示脚本 - 运行 AI 迭代实验的完整闭环

用法:
    python -m demo.run_simulation              # 默认场景，5轮迭代
    python -m demo.run_simulation --rounds 3  # 自定义轮数
    python -m demo.run_simulation --scenario drug_dosage  # 指定场景
"""
import sys
import argparse
import time
from pathlib import Path

# 确保项目根目录在 path 中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.experiment_service import ExperimentService
from demo.scenarios import PRESET_SCENARIOS


def print_separator(char="─", width=60):
    print(char * width)


def print_iteration_summary(record, total):
    """打印单轮迭代摘要"""
    metrics = record.metrics
    analysis = record.analysis
    decision = record.decision

    print(f"\n  📊 指标:")
    for k, v in metrics.items():
        if k not in ("iteration", "sample_size"):
            print(f"     {k}: {v:.4f}" if isinstance(v, float) else f"     {k}: {v}")

    print(f"\n  🔍 分析: {analysis.get('overall_assessment', '?')}")
    print(f"     摘要: {analysis.get('summary', '')[:80]}")

    issues = analysis.get("identified_issues", [])
    if issues:
        print(f"     问题: {'; '.join(issues[:2])}")

    adjustments = analysis.get("suggested_adjustments", [])
    if adjustments:
        print(f"     建议: {'; '.join(adjustments[:2])}")

    print(f"\n  🧭 决策: {'继续' if decision.get('should_continue', True) else '停止'}")
    print(f"     预期改进: {decision.get('expected_improvement', '')[:60]}")
    print(f"  ⏱️  耗时: {record.duration_seconds:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="AI 迭代实验模拟运行")
    parser.add_argument("--scenario", default="drug_dosage", choices=list(PRESET_SCENARIOS.keys()))
    parser.add_argument("--rounds", type=int, default=5, help="最大迭代轮数")
    parser.add_argument("--auto", action="store_true", help="自动运行至完成")
    args = parser.parse_args()

    scenario = PRESET_SCENARIOS[args.scenario]

    print_separator("=")
    print(f"  🔬 AI 迭代实验设计系统 - 命令行演示")
    print_separator("=")
    print(f"\n  场景: {scenario['name']}")
    print(f"  目标: {scenario['research_goal'][:60]}")
    print(f"  最大轮数: {args.rounds}")
    print()

    # 初始化服务
    service = ExperimentService.get_instance()

    # 创建实验
    print("📋 创建实验...")
    experiment = service.create_experiment(
        title=scenario["name"],
        research_goal=scenario["research_goal"],
        constraints=scenario["constraints"],
        executor_type=scenario["executor_type"],
        max_iterations=args.rounds,
    )

    print(f"  实验ID: {experiment.id}")
    print(f"  标题: {experiment.title}")

    # 启动实验（生成初始方案）
    print("\n🧠 AI 正在设计初始方案...")
    service.start_experiment(experiment.id)
    print("  ✅ 初始方案已生成")

    # 逐轮迭代
    max_rounds = args.rounds if args.auto else args.rounds
    for i in range(max_rounds):
        exp = service.get_experiment(experiment.id)
        if exp.status.value == "completed":
            print(f"\n🏁 实验已完成（共 {exp.current_iteration} 轮）")
            break

        print_separator()
        print(f"  ▶️ 第 {i + 1} 轮迭代")
        print_separator()

        record = service.run_iteration(experiment.id)
        print_iteration_summary(record, max_rounds)

        # 简要暂停让用户阅读
        if not args.auto and i < max_rounds - 1:
            try:
                input("\n  按 Enter 继续下一轮...")
            except (EOFError, KeyboardInterrupt):
                print("\n  已中断")
                break

    # 最终总结
    print_separator("=")
    print("  📊 最终总结")
    print_separator("=")

    final_exp = service.get_experiment(experiment.id)
    metrics_history = service.get_improvement_metrics(experiment.id)

    print(f"\n  总轮数: {final_exp.current_iteration}")
    print(f"  最终状态: {final_exp.status.value}")

    if metrics_history:
        print(f"\n  指标变化轨迹:")
        for m in metrics_history:
            it = m.get("iteration", "?")
            parts = [f"{k}={v:.4f}" for k, v in m.items() if k != "iteration" and isinstance(v, (int, float))]
            print(f"    第{it}轮: {', '.join(parts)}")

    print(f"\n  实验ID: {experiment.id}")
    print(f"  提示: 运行 streamlit run web/app.py 查看可视化界面")
    print()


if __name__ == "__main__":
    main()
