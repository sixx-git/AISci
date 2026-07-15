"""
快速验证脚本 — 不需要 API Key，仅验证本地模块可以正常导入和运行。

运行: python test_local.py
"""

import sys
import io
import json
from pathlib import Path

# Windows GBK 兼容
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """测试所有模块可以正常导入。"""
    print("测试模块导入...")
    from pipeline.source_parser import SourceParser, SourceDocument, TextBlock
    from pipeline.rubric_generator_v5 import RubricGenerator
    from pipeline.calibrator import Calibrator
    from pipeline.scorer import Scorer
    from pipeline.highlighter import Highlighter
    from pipeline.orchestrator import Pipeline
    print("  [OK] 所有模块导入成功")


def test_source_parser():
    """测试源文件解析器。"""
    print("\n测试源文件解析...")
    from pipeline.source_parser import SourceParser

    parser = SourceParser(verbose=True)

    # 测试 Markdown 解析
    test_md = Path("test_sample.md")
    test_md.write_text("# 测试文档\n\n这是一段测试文本。\n\n## 第二节\n\n更多内容。", encoding="utf-8")

    doc = parser.parse_file(str(test_md), "T1")
    assert doc.source_id == "T1"
    assert doc.file_type == "md"
    assert "测试文档" in doc.full_text
    print(f"  [OK] Markdown: {doc.char_count} chars")

    # 测试 CSV 解析
    test_csv = Path("test_sample.csv")
    test_csv.write_text("name,value,category\nAlice,10,A\nBob,20,B\nCharlie,30,A", encoding="utf-8")

    doc = parser.parse_file(str(test_csv), "T2")
    assert doc.source_id == "T2"
    assert doc.file_type == "csv"
    assert "Columns" in doc.full_text
    print(f"  [OK] CSV 解析: {doc.char_count} 字符")

    # 清理
    test_md.unlink()
    test_csv.unlink()


def test_calibrator():
    """测试校准器。"""
    print("\n测试评分表校准...")
    from pipeline.calibrator import Calibrator

    cal = Calibrator(verbose=True)

    # 构造测试评分表
    test_task = {
        "rubrics": {
            "total_score": 40,
            "dimensions": [
                {
                    "dimension_id": "information_acquisition",
                    "dimension_name": "Information Acquisition",
                    "max_score": 10,
                    "items": [
                        {"rubric_id": "R1", "role": "Critical", "weight": 4,
                         "question": "报告是否定义了X？", "source_ids": ["S1"]},
                        {"rubric_id": "R2", "role": "Mandatory", "weight": 2,
                         "question": "报告是否列出了数据集？", "source_ids": ["S1"]},
                        {"rubric_id": "R3", "role": "Standard", "weight": 1,
                         "question": "报告是否提到了时间范围？", "source_ids": []},
                    ],
                },
                {
                    "dimension_id": "scientific_reasoning",
                    "dimension_name": "Scientific Reasoning",
                    "max_score": 24,
                    "items": [
                        {"rubric_id": "R4", "role": "Critical", "weight": 4,
                         "question": "报告是否分析了因果关系？", "source_ids": ["S1", "S2"]},
                        {"rubric_id": "R5", "role": "Critical", "weight": 4,
                         "question": "报告是否推导了边界条件？", "source_ids": ["S2"]},
                        {"rubric_id": "R6", "role": "Mandatory", "weight": 2,
                         "question": "报告是否对比了方法优劣？", "source_ids": ["S1"]},
                    ],
                },
                {
                    "dimension_id": "report_synthesis",
                    "dimension_name": "Report Synthesis",
                    "max_score": 6,
                    "items": [
                        {"rubric_id": "R7", "role": "Mandatory", "weight": 2,
                         "question": "报告是否有完整结构？", "source_ids": []},
                        {"rubric_id": "R8", "role": "Standard", "weight": 1,
                         "question": "报告是否使用了专业术语？", "source_ids": []},
                        {"rubric_id": "R9", "role": "Standard", "weight": 1,
                         "question": "报告是否提供了未来方向？", "source_ids": []},
                    ],
                },
            ],
        },
    }

    result = cal.calibrate(test_task)
    assert "calibration" in result
    print(f"  [OK] 校准完成: 发现 {result['calibration']['issues_found']} 个问题")
    for issue in result["calibration"].get("issues", []):
        print(f"    - {issue}")


def test_cli_help():
    """测试 CLI 帮助信息。"""
    print("\n测试 CLI 入口...")
    import subprocess
    env = dict(__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
    )
    assert result.returncode == 0
    assert "Rubric Auto-Generator" in result.stdout or "评分表" in result.stdout
    print("  [OK] CLI 帮助信息正常")


if __name__ == "__main__":
    print("=" * 50)
    print("Rubric Auto-Generator — 本地测试")
    print("=" * 50)

    test_imports()
    test_source_parser()
    test_calibrator()
    test_cli_help()

    print("\n" + "=" * 50)
    print("全部测试通过 ✓")
    print("=" * 50)
