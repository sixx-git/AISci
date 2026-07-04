"""Monitor a quick-report pipeline run until completion or pause."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else ""
BASE = "http://127.0.0.1:8000"
POLL_SEC = int(sys.argv[2]) if len(sys.argv) > 2 else 30
MAX_POLLS = int(sys.argv[3]) if len(sys.argv) > 3 else 120


def fetch(path: str) -> dict:
    req = urllib.request.urlopen(BASE + path, timeout=90)
    return json.loads(req.read().decode("utf-8")).get("data", {})


def main() -> int:
    if not RUN_ID:
        print("Usage: python monitor_quick_report.py <run_id> [poll_sec] [max_polls]")
        return 1

    last_line = None
    for _ in range(MAX_POLLS):
        try:
            st = fetch(f"/api/v1/pipeline/status/{RUN_ID}")
            qr = fetch(f"/api/v1/pipeline/quick-report/status/{RUN_ID}")
        except Exception as exc:
            print(f"[{datetime.now():%H:%M:%S}] POLL ERROR: {exc}", flush=True)
            time.sleep(15)
            continue

        status = st.get("status", "?")
        stages = st.get("stages") or []
        running = [s["stage"] for s in stages if s.get("status") == "running"]
        completed = [s["stage"] for s in stages if s.get("status") in ("completed", "success")]
        failed = [s for s in stages if s.get("status") == "failed"]
        cur = running[0] if running else (completed[-1] if completed else "?")

        line = f"[{datetime.now():%H:%M:%S}] status={status} stage={cur} done={len(completed)}/9"
        if qr.get("awaiting_data_upload"):
            line += (
                f" AWAIT_UPLOAD pending={qr.get('pending_upload_count', 0)}"
                f" can_resume={qr.get('can_resume')}"
            )
        if st.get("error_message"):
            line += f" ERR={str(st.get('error_message'))[:120]}"
        if failed:
            line += f" FAILED_STAGES={[f['stage'] for f in failed]}"

        if line != last_line:
            print(line, flush=True)
            last_line = line

        status_lower = str(status).lower()
        if status_lower in ("completed", "failed", "cancelled"):
            report_id = qr.get("final_report_id") or st.get("final_report_id")
            if report_id:
                print(f"REPORT_ID: {report_id}", flush=True)
            if status_lower == "failed":
                print(f"FAILED_STAGE: {st.get('failed_stage')}", flush=True)
                print(f"ERROR: {st.get('error_message')}", flush=True)
                return 2
            return 0

        if qr.get("awaiting_data_upload"):
            print("PAUSED_FOR_DATA_UPLOAD", flush=True)
            print(json.dumps(qr, ensure_ascii=False, indent=2), flush=True)
            return 3

        time.sleep(POLL_SEC)

    print("MONITOR_TIMEOUT", flush=True)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
