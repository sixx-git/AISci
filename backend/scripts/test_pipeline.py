import requests
import json

BASE = "http://localhost:8001/api/v1"

r = requests.get(f"{BASE}/projects")
data = r.json()
items = data.get("data", {}).get("list", [])
pid = items[0]["id"]
print(f"Running pipeline for: {pid}")

p = requests.post(f"{BASE}/pipeline/run", json={
    "project_id": pid,
    "research_question": "如何利用机器学习提高医学影像诊断的准确率？"
})
print("Status:", p.status_code)
resp = p.json()
stages = resp.get("data", {}).get("stages", [])
for s in stages:
    msg = f"  {s['stage']}: {s['status']}"
    if s.get("error_message"):
        msg += f" | error: {s['error_message'][:100]}"
    if s.get("duration"):
        msg += f" | {s['duration']:.2f}s"
    print(msg)
print(f"Overall: {resp.get('data',{}).get('status','?')}")