# -*- coding: utf-8 -*-
"""무료 알림 랜딩: 카피 반영, 유료 플랜·가짜 후기/결제/로그인 없음."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import config
import landing
import intros
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env():
    root = os.path.join(os.path.dirname(__file__), "..")
    env = Environment(loader=FileSystemLoader(os.path.join(root, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    env.globals["bid_kinds"] = config.BID_KINDS
    env.globals["bid_has_regions"] = False
    env.globals["amount_bands"] = []
    env.globals["landing"] = landing.context()
    return env


def test_no_paid_plans_and_no_fake_review():
    """사업자 없음 → 유료 플랜·요금제·결제 문구를 두지 않는다(광고 수익만)."""
    ctx = landing.context()
    assert "plans" not in ctx and "pro_lock" not in ctx and "pricing_h1" not in ctx
    blob = " ".join(f["q"] + " " + f["a"] for f in ctx["alert_faqs"]) + ctx["mid_cta_lede"]
    assert "하루 1회, 새 공고가 있을 때만" in blob
    for bad in ("베이직", "프로", "사업자 등록", "유료 구독", "구독료", "카드로 매월 자동", "결제대행사",
                "낙찰까지 받았습니다", "최대 1시간", "1시간 이내"):
        assert bad not in blob, bad
    assert "OO기업" not in ctx["hero_h1"]
    assert "무료" in ctx["hero_hint"]


def test_business_placeholders_are_not_invented():
    biz = config.SITE["business"]
    assert not biz.get("ceo")
    assert not biz.get("biz_no")
    assert not biz.get("mail_order")
    assert not biz.get("address")
    assert "[대표자명]" not in (biz.get("ceo") or "")
    assert "123-45-67890" not in (biz.get("biz_no") or "")
    assert "000-00-00000" not in (biz.get("biz_no") or "")
    assert config.SITE["email"] == "qwqw050009@gmail.com"


def test_home_hero_and_footer():
    env = _env()
    home = env.get_template("list.html").render(
        site=config.SITE, path="/", page="home", section="support",
        title="t", desc="d", h1="seo", lede="lede", items=[],
        tally={"urgent": 1, "soon": 0, "open": 1},
        blocks=[], intro="", intro_paras=[], faqs=landing.ALERT_FAQS,
        faq_jsonld="", website_jsonld="", ad_top=None, ad_mid_after=None,
        ad_bottom=None, all_regions=config.REGIONS,
        all_categories=config.CATEGORIES, sel_region="", sel_category="",
        sel_district="", slugmap="{}", today=0, new_cnt=0, ics_url="",
        limit=0, more_href="/all/", sections=[], beginner_cta=False,
        crumbs=[], crumb_jsonld="", home_guides=[], list_guides=[],
        urgent_rail=[], source_tally={},
    )
    assert landing.HERO_H1 in home
    assert landing.HERO_LEDE in home
    assert "무료 알림 등록" in home
    assert "가입 없이 이메일로 무료 마감 알림" in home
    assert "이 조건 저장하고 알림받기" in home
    assert "프로 전용" not in home
    # 업종 칩(입찰용 분류)은 지원 홈에 두지 않는다
    assert "인테리어·마감공사" not in home
    assert "IT·소프트웨어" not in home
    assert "매번 검색하기 번거로우신가요?" in home
    assert "요금제" not in home and "/pricing/" not in home and "구독하기" not in home
    assert 'href="#alert"' in home and "무료 알림 받기" in home
    assert "알림은 얼마나 정확하고 빠른가요?" in home
    # 개인 메일 주소는 평문·mailto 로 두지 않고 문의 페이지로
    assert "qwqw050009@gmail.com" not in home
    assert 'href="/contact/"' in home
    assert 'href="https://tool.magampan.com/"' in home
    assert "카카오" not in home       # 알림톡은 사업자가 필요해 열지 않는다
    assert "RSS" in home
    assert "path-card" in home
    assert "오늘 마감" in home
    assert "개 시·도에서 고르기" in home
    assert "처음이세요?" in home
    assert "입찰 탭" in home
    assert "로그인</a>" not in home
    assert 'href="/login' not in home
    assert "낙찰까지 받았습니다" not in home
    footer_bits = ("지원사업", "입찰공고", "지원금 계산기", "사이트 소개",
                   "개인정보처리방침", "이용약관", "문의")
    for bit in footer_bits:
        assert bit in home
    assert "© 지원사업 마감판" in home
    assert "개인이 운영하는 지원사업·입찰 마감 안내 사이트" in home
    assert "[000-00-00000]" not in home
    assert "[대표자명]" not in home
    assert "통신판매업" not in home
    assert "사업장 주소" not in home


def test_alert_js_is_free_signup_not_checkout():
    root = os.path.join(os.path.dirname(__file__), "..")
    js = open(os.path.join(root, "static", "alert.js"), encoding="utf-8").read()
    assert "@gmail.com" not in js
    assert "/contact/" in js
    assert "/api/alerts/subscribe" in js
    assert "localStorage" in js
    assert "IMP.init" not in js
    assert "Kakao.init" not in js
    assert "checkout" not in js.lower()


def test_home_faqs_keep_counts_and_landing():
    faqs = intros.home_faqs(2, 11, 40)
    qs = [f["q"] for f in faqs]
    assert "알림은 얼마나 정확하고 빠른가요?" in qs
    assert "정부지원사업은 어떻게 신청하나요?" in qs
    assert any("오늘 마감 2건" in f["a"] for f in faqs)


if __name__ == "__main__":
    test_no_paid_plans_and_no_fake_review()
    test_business_placeholders_are_not_invented()
    test_home_hero_and_footer()
    test_alert_js_is_free_signup_not_checkout()
    test_home_faqs_keep_counts_and_landing()
    print("ok")
