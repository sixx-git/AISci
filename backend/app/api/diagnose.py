import traceback
import sys
from fastapi import APIRouter

router = APIRouter()


@router.get("/qwen-client")
async def diagnose_qwen_client():
    result = {
        "python_version": sys.version,
        "python_executable": sys.executable,
    }
    
    try:
        import httpx
        result["httpx_version"] = httpx.__version__
        result["httpx_path"] = httpx.__file__
    except Exception as e:
        result["httpx_error"] = str(e)

    try:
        import openai
        result["openai_version"] = openai.__version__
        result["openai_path"] = openai.__file__
    except Exception as e:
        result["openai_error"] = str(e)

    try:
        import httpcore
        result["httpcore_version"] = httpcore.__version__
        result["httpcore_path"] = httpcore.__file__
    except Exception as e:
        result["httpcore_error"] = str(e)

    result["init_qwen_client"] = "not_attempted"
    try:
        from app.services.qwen_client import QwenClient
        client = QwenClient()
        result["init_qwen_client"] = "success"
        result["qwen_model"] = client.model
        result["qwen_base_url"] = client.base_url
    except Exception as e:
        result["init_qwen_client"] = "failed"
        result["init_error"] = str(e)
        result["init_traceback"] = traceback.format_exc()

    result["init_problem_understanding_agent"] = "not_attempted"
    try:
        from app.agents.problem_understanding_agent import ProblemUnderstandingAgent
        agent = ProblemUnderstandingAgent()
        result["init_problem_understanding_agent"] = "success"
    except Exception as e:
        result["init_problem_understanding_agent"] = "failed"
        result["pu_error"] = str(e)
        result["pu_traceback"] = traceback.format_exc()

    return result