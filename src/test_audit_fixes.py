import os, sys
from datetime import date, datetime, timezone
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(__file__))
from jinja2 import Environment, FileSystemLoader, select_autoescape
import bid_build, deadline as dl, sources

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_latest_revision_canonical():
    rows = [{"id": "R1-000"}, {"id": "R1-002"}, {"id": "R1-001"}, {"id": "R2-000"}, {"id": "X"}]
    m = bid_build.latest_revisions(rows)
    assert m["R1-000"] == "R1-002" and m["R1-001"] == "R1-002" and m["R1-002"] == "R1-002"
    assert m["R2-000"] == "R2-000" and m["X"] == "X"


def test_today_is_kst_on_utc_runner():
    # 21:30 UTC = 다음날 06:30 KST (cron 빌드 시각)
    assert dl.today_kst(datetime(2026, 10, 12, 21, 30, tzinfo=timezone.utc)) == date(2026, 10, 13)
    with patch.object(sources, "today_kst", return_value=date(2026, 10, 13)):
        out = sources._process([{"apply_end": "2026-10-13"}, {"apply_end": "2026-10-12"}])
    assert [(r["dday"], r["is_open"]) for r in out] == [(0, True), (-1, False)]


def _env():
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals.update(asset_v="t")
    return env


SITE = {"name": "지원사업 마감판", "domain": "https://magampan.com", "adsense_client": "ca-pub-1", "adsense_slots": {}}


def test_404_has_no_ads_and_canonical_override():
    env = _env()
    h = env.get_template("404.html").render(site=SITE, path="/404.html", title="t", desc="d", noindex=True, no_ads=True)
    assert "adsbygoogle.js" not in h
    assert 'content="noindex, follow"' in h
    h2 = env.get_template("page.html").render(site=SITE, path="/bid/notice/R1-000/", canonical_path="/bid/notice/R1-001/",
                                              title="t", desc="d", h1="h", content="c")
    assert 'rel="canonical" href="https://magampan.com/bid/notice/R1-001/"' in h2
    assert "adsbygoogle.js" in h2


if __name__ == "__main__":
    test_latest_revision_canonical(); test_today_is_kst_on_utc_runner(); test_404_has_no_ads_and_canonical_override(); print("ok")
