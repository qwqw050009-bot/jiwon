# -*- coding: utf-8 -*-
"""_routes.json(함수 호출 최소화)·HTML 공백 정리·광고 자리 예약."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_routes_keep_html_and_api_on_functions():
    r = json.loads(build.routes_json_contents())
    assert r["version"] == 1 and r["include"] == ["/*"]
    ex = r["exclude"]
    assert "/static/*" in ex
    # HTML·API·robots·sitemap 은 미들웨어(별칭 호스트 301)와 /api/alerts 를 거쳐야 한다
    for p in ("/", "/*", "/api/*", "/api/alerts/*", "/notice/*", "/robots.txt", "/sitemap.xml", "/bid/*"):
        assert p not in ex, p
    assert len(r["include"]) + len(ex) <= 100


def test_minify_html_keeps_lines_and_pre():
    assert build.minify_html("<p>\n   <a>x</a>\n\n  <b>y</b>  \n</p>") == "<p>\n<a>x</a>\n<b>y</b>\n</p>\n"
    raw = "<pre>\n  a\n</pre>"
    assert build.minify_html(raw) == raw


def test_ad_slot_collapsed_until_filled():
    """미승인·미로드 광고가 빈 박스로 보이지 않게 높이를 미리 잡지 않고, 채워진 단위에만 여백을 준다."""
    base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
    head = base.split("</style>")[0]
    assert "min-height:200px" not in head and "min-height:250px" not in head
    assert '.ad-slot:has(ins.adsbygoogle[data-ad-status="filled"])' in head
    assert '.ad-slot:has(ins.adsbygoogle[data-ad-status="unfilled"]){display:none}' in head
    css = open(os.path.join(ROOT, "static", "style.css"), encoding="utf-8").read()
    assert "min-height:200px" not in css
    assert 'rel="preconnect" href="https://pagead2.googlesyndication.com"' in base


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("ok")
