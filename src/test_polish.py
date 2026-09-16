# -*- coding: utf-8 -*-
"""최종 폴리시: 알림 미리보기·검색 제안·관련 공고·sitemap·a11y."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import build
import filters
import serp
from jinja2 import Environment, FileSystemLoader, select_autoescape
import config
import landing


ROOT = os.path.join(os.path.dirname(__file__), "..")


def _env():
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    env.globals["bid_kinds"] = config.BID_KINDS
    env.globals["bid_has_regions"] = False
    env.globals["amount_bands"] = []
    env.globals["landing"] = landing.context()
    return env


def test_alerts_serp_and_template_noindex():
    assert "알림 조건" in serp.alerts_title()
    assert "mailto" in serp.alerts_desc()
    assert "결제" in serp.alerts_desc()
    html = _env().get_template("alerts.html").render(
        site=config.SITE, path="/alerts/", page="alerts", section="support",
        title=serp.alerts_title(), desc=serp.alerts_desc(),
        noindex=True, crumbs=[],
    )
    assert 'id="alerts-board"' in html
    assert "일시정지" in html
    assert "결제" in html
    assert 'name="robots"' in _env().get_template("base.html").render(
        site=config.SITE, path="/alerts/", title="t", desc="d", noindex=True,
        crumbs=[],
    )


def test_mode_switch_preserves_q_hook():
    base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
    assert 'data-mode="support"' in base
    assert 'data-mode="bid"' in base
    assert "suggest.js" in base
    assert "dns-prefetch" in base
    assert "preload" in base and "style.css" in base
    js = open(os.path.join(ROOT, "static", "state.js"), encoding="utf-8").read()
    assert "encodeURIComponent(q)" in js
    assert "bindDialog" in js
    assert "data-mode" in js


def test_alert_preview_in_filters():
    fjs = open(os.path.join(ROOT, "static", "filter.js"), encoding="utf-8").read()
    assert "previewHTML" in fjs
    assert "MagampanAlerts" in fjs
    assert "MagampanSuggest" in fjs
    bjs = open(os.path.join(ROOT, "static", "bid_filter.js"), encoding="utf-8").read()
    assert "previewHTML" in bjs
    assert "MagampanSuggest" in bjs
    ajs = open(os.path.join(ROOT, "static", "alert.js"), encoding="utf-8").read()
    assert "magampan.alerts.v1" in ajs
    assert "하루 1회" in ajs
    assert "일시정지" in ajs
    assert "결제" in ajs
    sjs = open(os.path.join(ROOT, "static", "suggest.js"), encoding="utf-8").read()
    assert "aria-autocomplete" in sjs
    assert "<mark>" in sjs


def test_card_js_no_double_dash_dday():
    js = open(os.path.join(ROOT, "static", "card.js"), encoding="utf-8").read()
    assert "if (!(d > 0))" in js
    assert "pill-corr" in js
    assert "스크랩에 넣기" in js
    row = open(os.path.join(ROOT, "templates", "_row.html"), encoding="utf-8").read()
    assert "pill-corr" in row
    assert "정정" in row


def test_minify_css_keeps_selectors():
    raw = "/* x */\n.skip { color: #fff; }\n.a > .b { margin: 0; }\n"
    out = build.minify_css(raw)
    assert "/*" not in out
    assert "skip{color:#fff" in out.replace(" ", "")
    assert "calc" not in out or "calc(" in out


def test_date_of_reads_posted_only():
    assert build._date_of({"posted_at": "2026-09-04 11:00"}) == "2026-09-04"
    assert build._date_of({"title": "없음"}) is None
    assert build._date_of({}, fallback="2026-09-16") == "2026-09-16"


def test_a11y_skip_and_dialog_controls():
    filt = open(os.path.join(ROOT, "templates", "_filter.html"), encoding="utf-8").read()
    assert 'aria-controls="f-panel"' in filt
    assert 'aria-hidden="true"' in filt
    css = open(os.path.join(ROOT, "static", "style.css"), encoding="utf-8").read()
    assert ":focus-visible" in css
    assert ".suggest" in css
    assert "--muted:#4E4E4A" in css


def test_related_detail_shows_dday_copy():
    env = _env()
    item = {
        "id": "a", "title": "특례보증", "org": "중기부", "region": "서울",
        "category": "금융", "cls": "d-u", "dlabel": "D-2", "dsub": "마감",
        "ai": {"summary": "요약", "fit": ["적합"], "caution": ["주의"],
               "checklist": ["서류"]},
        "amount": "공고문 참조", "target": "소상공인", "method": "온라인",
        "apply_start": "2026-09-01", "apply_end": "2026-09-20",
        "period_type": "dated", "detail_url": "https://www.bizinfo.go.kr/",
        "signals": [], "is_new": True, "is_correction": False,
        "status_label": "진행", "source_label": "기업마당",
        "deadline_line": "2026-09-20 · 시간 미상",
    }
    rel = [{
        "id": "b", "title": "다른 보증", "org": "중기부", "region": "서울",
        "category": "금융", "cls": "d-u", "dlabel": "오늘", "dsub": "오늘",
        "amount_card": "", "signals": [], "is_new": False, "target_short": "",
        "blurb": "", "source_label": "기업마당", "status_label": "진행",
        "deadline_line": "오늘 마감",
    }]
    html = env.get_template("detail.html").render(
        site=config.SITE, path="/notice/a/", page="detail", section="support",
        title="t", desc="d", a=item, related=rel, jsonld="{}",
        faqs=[], howto=[], crumbs=[], crumb_jsonld="",
    )
    assert "이어서 볼 공고" in html
    assert "마감 가까운 순" in html
    assert "오늘" in html
    assert "정정" in open(os.path.join(ROOT, "templates", "_row.html"), encoding="utf-8").read()


if __name__ == "__main__":
    test_alerts_serp_and_template_noindex()
    test_mode_switch_preserves_q_hook()
    test_alert_preview_in_filters()
    test_card_js_no_double_dash_dday()
    test_minify_css_keeps_selectors()
    test_date_of_reads_posted_only()
    test_a11y_skip_and_dialog_controls()
    test_related_detail_shows_dday_copy()
    print("polish tests ok")
