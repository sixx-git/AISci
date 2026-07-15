"""
便捷启动脚本

用法:
    python run.py web       # 启动 Web 界面
    python run.py demo      # 运行命令行演示
    python run.py demo --rounds 3  # 演示3轮
"""
import sys
import subprocess
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python run.py web       # 启动 Streamlit Web 界面")
        print("  python run.py demo      # 运行命令行演示")
        print("  python run.py demo --rounds 3  # 演示指定轮数")
        sys.exit(1)

    command = sys.argv[1]

    if command == "web":
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(project_root / "web" / "app.py"),
            "--server.port", "8501",
        ])
    elif command == "demo":
        subprocess.run([
            sys.executable, "-m", "demo.run_simulation",
            *sys.argv[2:],
        ], cwd=str(project_root))
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
