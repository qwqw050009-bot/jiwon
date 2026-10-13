# -*- coding: utf-8 -*-
"""2026-10 수정: 포상·표창 공고 제외, 숫자 없는 금액 제거, /pricing/ 301, 잔재 HTML 가드."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import build
import enrich
import sources


def test_excluded_titles():
    bad = [
        "2026년 전자문서 유공 포상 계획 연장 공고",
        "2026년 대한민국 ICT 대상 표창 수여계획 추가 공고",
        "제9회 세종시 기업인의 날 우수기업 및 유공자 선정계획 공고",
        "부천시 2026년 수출 유공 및 ESG 경영 유공 포상 후보자 모집 공고",
    ]
    for t in bad:
        assert sources.is_excluded_title(t), t
    # '공유공장'(공·유공·장)은 지원사업이다 — 걸리면 안 된다.
    assert not sources.is_excluded_title("혁신기술 제조창업 기업지원 수혜기업 추가모집 공고(혁신기술 제조창업 공유공장 구축사업)")
    assert not sources.is_excluded_title("2026년 소상공인 경영개선 지원사업 공고")
    rows = sources._process([
        {"title": "2026년 지식재산 거래 유공 포상 공고", "period_type": "always"},
        {"title": "2026년 창업 사업화 지원", "period_type": "always"},
    ])
    assert [r["title"] for r in rows] == ["2026년 창업 사업화 지원"]


def test_amount_without_digits_is_dropped():
    assert enrich._pick_amount("사업비 , 원 지원") is None
    assert enrich._pick_amount("최대 억원") is None
    assert enrich._pick_amount("업체당 최대 200만원 지원") == "업체당 최대 200만원"
    assert enrich.amount_card({"amount": ", 원"}) == ""
    assert enrich.amount_card({"amount": "최대 5천만원"}) == "최대 5천만원"
    row = build.fill_defaults({"amount": ", 원", "points": [], "overview": ""})
    assert row["amount"] == "공고문 참조" and row["amount_card"] == ""
    import intros
    assert intros._blurb_amount({"amount": ", 원"}) == ""
    # 캐시에 남은 숫자 없는 금액 문장은 규칙 기반으로 다시 만든다
    healed = enrich.heal_broken_josa({"summary": "OK FTA 컨설팅 · 공고문 지원규모 표기는 , 원입니다."},
                                     {"title": "FTA 컨설팅", "amount": ", 원"})
    assert ", 원" not in healed["summary"]


def test_pricing_redirects_home():
    r = build.cf_redirects_contents()
    assert "/pricing/ / 301" in r and "/pricing / 301" in r
    root = os.path.join(os.path.dirname(__file__), "..")
    assert not os.path.exists(os.path.join(root, "templates", "pricing.html"))


def test_stray_html_guard():
    d = tempfile.mkdtemp()
    for rel in ("index.html", "bid/index.html", "bid.html", "404.html", "static/x.html"):
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write("x")
    stray = build.stray_html_files(d, {"index.html", "bid/index.html"})
    assert stray == ["bid.html"]


if __name__ == "__main__":
    test_excluded_titles()
    test_amount_without_digits_is_dropped()
    test_pricing_redirects_home()
    test_stray_html_guard()
    print("round1 ok")
