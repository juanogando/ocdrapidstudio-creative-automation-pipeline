"""Fast tests: run offline with the mock provider in a temp folder."""
import shutil
from pathlib import Path

import pytest
from PIL import Image

from creative_pipeline import checks
from creative_pipeline.brief import BriefError, load_brief, parse_brief
from creative_pipeline.compose import output_size
from creative_pipeline.pipeline import run
from creative_pipeline.providers import MockProvider

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def workspace(tmp_path):
    assets = tmp_path / "assets"
    shutil.copytree(EXAMPLES / "assets", assets)
    for p in assets.glob("*_generated.png"):  # start clean: force one generation
        p.unlink()
    return assets, tmp_path / "out"


def test_full_run_reuses_and_generates(workspace):
    assets, out = workspace
    brief = load_brief(EXAMPLES / "brief.yaml")
    report = run(brief, assets, out, MockProvider())

    assert report.heroes == {"citrus-spark": "reused", "mango-chili": "generated"}
    expected = len(brief.products) * len(brief.locales) * len(brief.aspect_ratios)
    assert len(report.creatives) == expected
    for c in report.creatives:
        img = Image.open(out / c.path)
        assert img.size == output_size(c.ratio)
    assert (out / brief.campaign_id / "report.json").exists()

    # second run: the generated hero is now on disk and must be reused
    again = run(brief, assets, out, MockProvider())
    assert set(again.heroes.values()) == {"reused"}


def test_brief_needs_two_products():
    with pytest.raises(BriefError):
        parse_brief({"campaign_id": "x", "region": "r", "audience": "a", "message": "m",
                     "products": [{"id": "only", "name": "Only"}]})


def test_legal_flags_whole_words_only():
    assert not checks.check_legal("Results guaranteed!").passed
    assert checks.check_legal("A cured ham sandwich").passed  # 'cure' inside 'cured' is fine


def test_contrast_ratio():
    assert round(checks.contrast_ratio((0, 0, 0), (255, 255, 255))) == 21
