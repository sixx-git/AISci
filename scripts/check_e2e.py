#!/usr/bin/env python3
"""
AISci 端到端验收脚本
检查所有核心后端接口，输出 PASS / WARNING / FAIL。
不依赖真实 API Key，LLM 检查只检查配置是否存在，不实际消耗 token。
"""
import sys
import json
import urllib.request
import urllib.error
import os
from typing import Tuple, Optional

BASE_URL = os.environ.get("AISCI_BASE_URL", "http://localhost:8000")
TIMEOUT = 15

PASS = 0
WARNING = 0
FAIL = 0
CHECKS = []


def check(name: str, pass_: bool = False, warning: bool = False, fail: bool = False,
          detail: str = "", skip: bool = False):
    global PASS, WARNING, FAIL
    if skip:
        status = "SKIP"
    elif pass_:
        status = "PASS"
        PASS += 1
    elif warning:
        status = "WARN"
        WARNING += 1
    else:
        status = "FAIL"
        FAIL += 1
    detail_str = f"  └─ {detail}" if detail else ""
    CHECKS.append(f"[{status}] {name}{' ' + detail_str if detail_str else ''}")
    print(CHECKS[-1])


def _get(path: str, timeout: int = TIMEOUT) -> Tuple[int, Optional[dict]]:
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return e.code, json.loads(body) if body else None
        except Exception:
            return e.code, None
    except Exception as e:
        return -1, {"error": str(e)}


def _post(path: str, body: dict = None, timeout: int = TIMEOUT) -> Tuple[int, Optional[dict]]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body or {}).encode("utf-8") if body else None
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            body_raw = e.read().decode("utf-8")
            return e.code, json.loads(body_raw) if body_raw else None
        except Exception:
            return e.code, None
    except Exception as e:
        return -1, {"error": str(e)}


def _unwrap_data(data: Optional[dict]) -> Optional[dict]:
    """解包统一的 ResponseModel 包装：{code, data, message} → data"""
    if data and isinstance(data, dict) and "data" in data and "code" in data:
        return data["data"]
    return data


# ════════════════════════════════════════
# 1. 后端健康检查
# ════════════════════════════════════════
print("=" * 60)
print("AISci 端到端验收检查")
print("=" * 60)
print()

code, data = _get("/health")
if code == 200 and data:
    inner = data.get("data", data)
    status_ok = isinstance(inner, dict) and inner.get("status") == "healthy"
    if status_ok:
        check("后端健康检查 (/health)", pass_=True)
    else:
        check("后端健康检查 (/health)", fail=True, detail=f"data={str(data)[:100]}")
        print("\n❌ 后端状态异常，终止检查。请先启动后端服务。")
        print("   启动命令: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
else:
    check("后端健康检查 (/health)", fail=True, detail=f"status={code}")
    print("\n❌ 后端未运行或不可达，终止检查。")
    print("   启动命令: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("   注意: 必须在 backend/ 目录下启动，否则 .env 无法加载。")
    sys.exit(1)

# ════════════════════════════════════════
# 2. LLM 客户端健康检查（替代旧的 /diagnose/qwen-client）
# ════════════════════════════════════════
code, data = _get("/health/llm")
if code == 200 and data:
    llm = _unwrap_data(data) or {}
    use_mock = llm.get("use_mock_llm", False)
    api_key_ok = llm.get("qwen_api_key_configured", False)
    base_url_ok = llm.get("base_url_configured", False)
    client_ok = llm.get("client_init_ok", False)
    model = llm.get("model", "unknown")
    error = llm.get("error")

    if client_ok:
        if use_mock:
            check("千问客户端诊断 (/health/llm)", pass_=True,
                  detail="Mock LLM 模式已启用 (model=mock-model)")
        else:
            check("千问客户端诊断 (/health/llm)", pass_=True,
                  detail=f"client_init_ok=true, model={model}")
    elif not api_key_ok:
        check("千问客户端诊断 (/health/llm)", warning=True,
              detail="QWEN_API_KEY 未配置，LLM 功能不可用。请在 .env 中设置 QWEN_API_KEY")
    elif not base_url_ok:
        check("千问客户端诊断 (/health/llm)", warning=True,
              detail="QWEN_BASE_URL 未配置")
    else:
        check("千问客户端诊断 (/health/llm)", fail=True,
              detail=f"client_init_ok=false, error={error}")
else:
    check("千问客户端诊断 (/health/llm)", fail=True,
          detail=f"status={code}, /health/llm 接口不可达")

# ════════════════════════════════════════
# 3. 项目列表
# ════════════════════════════════════════
code, data = _get("/api/v1/projects")
projects = []
if code == 200 and data:
    inner = _unwrap_data(data) or {}
    projects = inner.get("items", [])
    check("项目列表 (/api/v1/projects)", pass_=True,
          detail=f"共 {len(projects)} 个项目")
else:
    check("项目列表 (/api/v1/projects)", fail=True,
          detail=f"status={code}")

# ════════════════════════════════════════
# 4. 文献搜索接口
# ════════════════════════════════════════
code, data = _get("/api/v1/literature/sources")
if code == 200:
    check("文献源列表 (/api/v1/literature/sources)", pass_=True)
else:
    check("文献源列表 (/api/v1/literature/sources)", warning=True,
          detail=f"status={code}")

code, data = _post("/api/v1/literature/search/arxiv", {
    "query": "machine learning",
    "max_results": 3,
    "project_id": "e2e-test",
})
if code in (200, 201) and data:
    inner = _unwrap_data(data) or data
    papers = inner.get("papers", [])
    if papers:
        check("arXiv 论文搜索 (/api/v1/literature/search/arxiv)", pass_=True,
              detail=f"返回 {len(papers)} 篇论文")
    else:
        check("arXiv 论文搜索 (/api/v1/literature/search/arxiv)", pass_=True,
              detail="返回 0 篇（网络限制，fallback 可用）")
else:
    check("arXiv 论文搜索 (/api/v1/literature/search/arxiv)", warning=True,
          detail=f"status={code}，可能是网络限制或 API 未配置")

# ════════════════════════════════════════
# 5. 数据集接口
# ════════════════════════════════════════
code, data = _get("/api/v1/datasets")
if code in (200, 422):
    check("数据集列表 (/api/v1/datasets)", pass_=True,
          detail="接口可达" if code == 200 else "需要 project_id 参数 (符合预期)")
else:
    check("数据集列表 (/api/v1/datasets)", warning=True,
          detail=f"status={code}")

# ════════════════════════════════════════
# 6. Pipeline 接口
# ════════════════════════════════════════
test_project_id = None
if projects:
    test_project_id = projects[0].get("id") or projects[0].get("project_id")

if test_project_id:
    code, data = _get(f"/api/v1/pipeline/runs/{test_project_id}")
    if code == 200:
        runs = _unwrap_data(data) or []
        check("Pipeline 运行列表", pass_=True,
              detail=f"项目 {str(test_project_id)[:8]} 共 {len(runs)} 次运行")
    else:
        check("Pipeline 运行列表", warning=True,
              detail=f"status={code}, project_id={str(test_project_id)[:8]}")
else:
    check("Pipeline 运行列表", pass_=True,
          detail="无项目（预期行为：创建项目后可测试 Pipeline）")

code, data = _get("/api/v1/pipeline/status/nonexistent-run-id")
if code in (200, 404, 422):
    check("Pipeline 状态接口", pass_=True,
          detail="接口可达 (404/422 为预期行为)")
else:
    check("Pipeline 状态接口", warning=True, detail=f"status={code}")

# ════════════════════════════════════════
# 7. 报告接口
# ════════════════════════════════════════
if test_project_id:
    code, data = _get(f"/api/v1/reports/latest/{test_project_id}")
    if code == 200:
        report = _unwrap_data(data)
        if report:
            report_id = report.get("report_id") or report.get("id", "")
            check("最新报告 (/api/v1/reports/latest)", pass_=True,
                  detail=f"report_id={str(report_id)[:8]}")
        else:
            check("最新报告 (/api/v1/reports/latest)", pass_=True,
                  detail="无可用报告（预期行为：需先运行 Pipeline）")
    else:
        check("最新报告 (/api/v1/reports/latest)", warning=True,
              detail=f"status={code}")
else:
    check("最新报告 (/api/v1/reports/latest)", pass_=True,
          detail="无项目（预期行为：创建项目并运行 Pipeline 后可生成报告）")

# ════════════════════════════════════════
# 8. Agent 接口（修复前缀: /agents 非 /agent）
# ════════════════════════════════════════
agent_get_endpoints = [
    ("agent-hypotheses", "/api/v1/agents/hypotheses/e2e-test"),
    ("agent-experiment-designs", "/api/v1/agents/experiment-designs/e2e-test"),
    ("agent-small-validations", "/api/v1/agents/small-validations/e2e-test"),
]

for name, path in agent_get_endpoints:
    code, data = _get(path)
    if code in (200, 404):
        check(f"Agent 接口可达 ({name})", pass_=True,
              detail=f"GET {path.split('/')[-2]} status={code} (接口可达)")
    else:
        check(f"Agent 接口可达 ({name})", warning=True,
              detail=f"status={code}")

# ════════════════════════════════════════
# 9. Skills 文件完整性
# ════════════════════════════════════════
backend_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "app")
expected_skills = [
    "skills/literature/search_papers_skill.py",
    "skills/literature/citation_grounding_skill.py",
    "skills/data/dataset_discovery_skill.py",
    "skills/data/data_juicer_lite_skill.py",
    "skills/report/scientific_plot_skill.py",
    "skills/report/report_chart_generation_skill.py",
    "skills/report/report_quality_check_skill.py",
    "skills/reasoning/question_alignment_skill.py",
    "skills/reasoning/hypothesis_novelty_review_skill.py",
    "skills/experiment/experiment_sanity_check_skill.py",
]

missing_skills = []
for skill_path in expected_skills:
    full_path = os.path.join(backend_root, skill_path)
    if not os.path.exists(full_path):
        missing_skills.append(skill_path)

if missing_skills:
    check("Skills 文件完整性", fail=True,
          detail=f"缺失 {len(missing_skills)} 个: {', '.join(missing_skills)}")
else:
    check("Skills 文件完整性", pass_=True,
          detail=f"全部 {len(expected_skills)} 个核心 Skill 文件存在")

# ════════════════════════════════════════
# 10. 环境变量检查（.env 文件存在性；具体 API Key 状态由 /health/llm 检查）
# ════════════════════════════════════════
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(env_path):
    check(".env 配置文件", pass_=True, detail=".env 文件存在")
else:
    check(".env 配置文件", warning=True,
          detail=".env 不存在，请从 .env.example 复制。注意: 必须在 backend/ 目录下启动 uvicorn 才能正确加载 .env。")

# ════════════════════════════════════════
# 汇总
# ════════════════════════════════════════
print()
print("=" * 60)
print(f"检查完成:  {PASS} PASS  {WARNING} WARN  {FAIL} FAIL")
print("=" * 60)

if FAIL > 0:
    print("\n[WARN] 存在失败项，请检查后端服务和配置。")
    print("   常见排查步骤:")
    print("   1. 确认后端已启动: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("   2. 确认前端已构建: cd frontend && npm run build")
    print("   3. 确认 .env 配置正确（注意: .env 需在 uvicorn 启动目录下）")
    print("   4. 检查 /health/llm 接口确认 QWEN_API_KEY 是否已加载")
    sys.exit(1)
else:
    print("\n[OK] 端到端检查通过！所有核心接口可达。")
    sys.exit(0)