#!/usr/bin/env python3
"""Unified entry used by fl_pack_service.run_local_fedavg_pilot()."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    script = HERE / "hfl_fedavg_pilot.py"
    out = HERE / "_last_fedavg_metrics.json"
    proc = subprocess.run(
        [sys.executable, str(script), "--rounds", "5", "--clients", "5", "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.is_file():
        print(out.read_text(encoding="utf-8"))
        return
    print(proc.stdout or proc.stderr or json.dumps({"error": "fedavg pilot failed", "code": proc.returncode}))


if __name__ == "__main__":
    main()
