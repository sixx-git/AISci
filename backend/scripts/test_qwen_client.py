"""
Qwen / 千问客户端最小连通性测试

读取 .env 中的 QWEN_API_KEY / QWEN_BASE_URL / QWEN_MODEL，
发起一次最小 chat completion 并输出结果。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

root_env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.isfile(root_env):
    load_dotenv(root_env, override=True)

from openai import OpenAI


def main():
    api_key = os.getenv("QWEN_API_KEY", "")
    base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.getenv("QWEN_MODEL", "qwen-max")

    if not api_key or api_key == "your_qwen_api_key_here":
        print("[FAIL] QWEN_API_KEY 未配置或为占位值，请在项目根目录 .env 中设置真实的 API Key")
        sys.exit(1)

    print(f"model : {model}")
    print(f"base  : {base_url}")
    print("key   : *** (已隐藏)")
    print("-" * 50)

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'hello' in one word."}],
            max_tokens=10,
            temperature=0.0,
        )
    except Exception as e:
        print(f"[FAIL] API 调用失败: {e}")
        sys.exit(1)

    choice = response.choices[0]
    print(f"response_id       : {response.id}")
    print(f"content           : {choice.message.content}")
    usage = response.usage
    if usage:
        print(f"prompt_tokens     : {usage.prompt_tokens}")
        print(f"completion_tokens : {usage.completion_tokens}")
        print(f"total_tokens      : {usage.total_tokens}")
    print("-" * 50)
    print("[OK] Qwen 客户端连通测试通过")


if __name__ == "__main__":
    main()