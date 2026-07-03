"""Resume a stuck pipeline run whose background worker died mid-stage."""
import json
import sys
import threading
import time
import urllib.request

sys.path.insert(0, ".")
from app.api.pipeline import _execute_pipeline_background
from app.core.database import init_db

RUN_ID = "fd2420bd-93c1-43b5-858f-3e00f18b9e38"


def poll_status(run_id: str) -> dict:
    url = f"http://127.0.0.1:8000/api/v1/pipeline/status/{run_id}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode())["data"]


def main() -> None:
    init_db()
    thread = threading.Thread(
        target=_execute_pipeline_background,
        args=(RUN_ID,),
        daemon=False,
    )
    thread.start()
    print(f"pipeline thread started for {RUN_ID}")

    for i in range(120):
        time.sleep(2)
        try:
            st = poll_status(RUN_ID)
            stages = {s["stage"]: s["status"] for s in st["stages"]}
            hr = stages.get("hypothesis_review")
            ed = stages.get("experiment_design")
            print(f"[{i * 2}s] run={st['status']} hypothesis_review={hr} experiment_design={ed}")
            if hr == "completed":
                print("hypothesis_review completed")
                break
            if st["status"] in ("failed", "completed", "cancelled"):
                print("run ended:", st["status"])
                break
        except Exception as exc:
            print("poll error:", exc)

    thread.join(timeout=600)
    print("thread alive:", thread.is_alive())


if __name__ == "__main__":
    main()
