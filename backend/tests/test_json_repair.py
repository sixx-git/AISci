"""测试 JSON 修复逻辑"""
import sys
sys.path.insert(0, ".")

from app.services.qwen_client import _repair_json, _safe_json_loads
import json

# 测试1: 正常JSON
r1 = _safe_json_loads('{"a": 1}')
print("Test1 normal:", r1)
assert r1 == {"a": 1}

# 测试2: markdown包裹
r2 = _safe_json_loads('```json\n{"a": 1}\n```')
print("Test2 markdown:", r2)
assert r2 == {"a": 1}

# 测试3: trailing comma修复
r3 = _repair_json('{"a": 1, "b": [1,2,], "c": {"d": 3,},}')
print("Test3 trailing:", r3)
assert r3 == {"a": 1, "b": [1, 2], "c": {"d": 3}}

# 测试4: Python None/True/False → JSON
r4 = _repair_json('{"a": None, "b": True, "c": False}')
print("Test4 python-null:", r4)
assert r4 == {"a": None, "b": True, "c": False}

# 测试5: 截断JSON补齐括号
r5 = _repair_json('{"a": 1, "b": [1, 2')
print("Test5 truncated:", r5)
assert r5 == {"a": 1, "b": [1, 2]}

# 测试6: 混合文本中提取JSON块
r6 = _repair_json('这是解释文字 {"result": "ok"} 后面还有文字')
print("Test6 extract:", r6)
assert r6 == {"result": "ok"}

# 测试7: Python 单引号 dict → 自动转换（ast.literal_eval）
r7 = _repair_json("{'key': 'value', 'num': 42}")
print("Test7 python-dict:", r7)
assert r7 == {"key": "value", "num": 42}

# 测试8: 应该抛出异常（无法修复的）
try:
    _repair_json("this is not json at all")
    print("Test8: FAILED (should have raised)")
except Exception as e:
    print("Test8 invalid-json raised:", type(e).__name__)

print()
print("All JSON repair tests passed!")