"""Pipeline 小样验证阶段空值防护测试。"""


def test_merged_none_does_not_chain_get_crash():
    df_results = {"merged": None}
    merged = df_results.get("merged") if isinstance(df_results.get("merged"), dict) else {}
    merged_path = merged.get("cleaned_csv_path") or merged.get("merged_csv_path")
    assert merged_path is None


def test_skill_outputs_none_uses_or_fallback():
    ed = {"skill_outputs": {"multimodal_data_ingest": None}}
    ed_skill_outputs = ed.get("skill_outputs") or {}
    ingest_output = ed_skill_outputs.get("multimodal_data_ingest") or {}
    assert ingest_output == {}
