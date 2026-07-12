import pandas as pd

from app.services.experiment_pilot_analysis_service import run_pilot_from_csv
from app.services.tabular_encoding_utils import encode_tabular_frame, pick_value_column


def test_encode_hepar_categorical():
    frame = pd.DataFrame({
        "carcinoma": ["absent", "present", "absent"],
        "jaundice": ["present", "absent", "present"],
        "phosphatase": ["a699_240", "a100_50", "a200_100"],
    })
    enc = encode_tabular_frame(frame)
    assert enc["carcinoma"].tolist() == [0.0, 1.0, 0.0]
    assert enc["phosphatase"].iloc[0] == (699 + 240) / 2
    col = pick_value_column(enc)
    assert col is not None


def test_pilot_on_hepar_csv():
    import os
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "storage",
        "uploads",
        "datasets",
        "df5768a0-8084-4a84-a0ec-6401b546568e",
        "1da21cc2_HEPAR_simulated_patients.csv",
    )
    path = os.path.normpath(path)
    if not os.path.isfile(path):
        return
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        r = run_pilot_from_csv(path, {"baselines": "Baseline; Proposed"}, output_dir=tmp, hypothesis="test")
        assert r.get("success") is True
        assert len(r.get("plots") or []) >= 1
