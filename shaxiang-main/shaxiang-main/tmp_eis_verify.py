# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from executors.data_adapter import DataConfig
from executors.directory_loader import DirectoryLoader
from services.experiment_service import ExperimentService

p = r"D:\浏览器\报告汇总\sjtu_q_111_人机混合物种\data\EIS_data"
profile = {
    "name": "eis",
    "modality": "tabular",
    "scan_pattern": "**/*",
    "file_extensions": [".csv", ".txt"],
    "delimiter": ",",
    "has_header": True,
    "comment_prefix": "",
}
cfg = DataConfig(
    source_type="directory",
    source_path=p,
    profile_name="AutoDetect",
    profile_json=json.dumps(profile, ensure_ascii=False),
    sample_size=2000,
)
try:
    df = DirectoryLoader().load(cfg)
    print("LOAD shape", df.shape)
    print("dtypes", df.dtypes.value_counts().to_dict())
    print("numeric", list(df.select_dtypes("number").columns)[:20], "n=", df.select_dtypes("number").shape[1])
    print("cols", list(df.columns)[:15])
    print(df.head(2))
except Exception as e:
    print("LOAD FAIL", type(e).__name__, e)

svc = ExperimentService.__new__(ExperimentService)
vcfg = {
    "source_type": "directory",
    "source_path": p,
    "profile_name": "AutoDetect",
    "profile_json": json.dumps(profile, ensure_ascii=False),
    "sample_size": 2000,
}
try:
    out = ExperimentService.verify_data_config(svc, vcfg, sample_size=2000)
    print("VERIFY OK rows", out.get("row_count"), "cols", out.get("column_count"),
          "numeric", len(out.get("numeric_columns") or []), "recovered", out.get("profile_recovered"))
except Exception as e:
    print("VERIFY FAIL", type(e).__name__, e)
