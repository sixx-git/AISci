from app.services.analysis_script_utils import sanitize_analysis_script


def test_sanitize_fixes_wasserstein_import():
    script = (
        "from scipy.spatial.distance import wasserstein_distance\n"
        "import pandas as pd\n"
    )
    fixed = sanitize_analysis_script(script)
    assert "from scipy.stats import wasserstein_distance" in fixed
    assert "scipy.spatial.distance import wasserstein_distance" not in fixed


def test_sanitize_injects_matplotlib_agg():
    script = "import matplotlib.pyplot as plt\nplt.plot([1, 2])\n"
    fixed = sanitize_analysis_script(script)
    assert "matplotlib.use('Agg')" in fixed
