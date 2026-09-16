# -*- coding: utf-8 -*-
"""알림·요금제 랜딩: 카피 반영, 가짜 후기/결제/로그인 없음."""
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


def test_copy_has_three_plans_and_no_fake_review():
    ctx = landing.context()
    names = [p["name"] for p in ctx["plans"]]
    assert names == ["무료", "베이직", "프로"]
    prices = [p["price"] for p in ctx["plans"]]
    assert prices == ["₩0", "₩9,900", "₩29,000"]
    basic = next(p for p in ctx["plans"] if p["id"] == "basic")
    assert basic["popular"] is True
    assert "가장 인기있는 플랜" in basic["badge"]
    blob = " ".join(ctx["alert_faqs"][i]["a"] for i in range(len(ctx["alert_faqs"])))
    assert "최대 1시간" in blob
    assert "낙찰까지 받았습니다" not in blob
    assert "OO기업" not in ctx["hero_h1"]
    for p in ctx["plans"]:
        assert p["cta_href"].startswith("/")
        assert "checkout" not in p["cta_href"]
        assert "kakao" not in p["cta_href"].lower()


def test_business_placeholders_are_not_invented():
    biz = config.SITE["business"]
    assert biz["ceo"].startswith("[")
    assert biz["biz_no"].startswith("[")
    assert biz["mail_order"].startswith("[")
    assert biz["address"].startswith("[")
    assert "123-45-67890" not in biz["biz_no"]
    assert config.SITE["email"] == "qwqw050009@gmail.com"


def test_pricing_page_render():
    html = _env().get_template("pricing.html").render(
        site=config.SITE, path="/pricing/", page="pricing", section="support",
        title="t", desc="d", h1=landing.PRICING_H1, lede=landing.PRICING_LEDE,
        faqs=landing.ALERT_FAQS, faq_jsonld="", crumbs=[], crumb_jsonld="",
    )
    assert "₩0" in html and "₩9,900" in html and "₩29,000" in html
    assert "가장 인기있는 플랜" in html
    assert "무료로 시작하기" in html
    assert "베이직 시작하기" in html
    assert "프로 시작하기" in html
    assert "알림 신청" in html
    assert "준비 중" in html
    assert "낙찰까지 받았습니다" not in html
    assert "후기" not in html
    assert 'href="/login' not in html
    assert ">로그인<" not in html
    assert "로그인</a>" not in html
    assert "[대표자명]" in html
    assert "qwqw050009@gmail.com" in html
    assert 'href="/pricing/"' in html
    assert "요금제" in html
    assert landing.PLAN_LEGAL[:20] in html


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
    assert "이 조건 저장하고 알림받기" in home
    assert "인테리어·마감공사" in home
    assert "설비·기계" in home
    assert "IT·소프트웨어" in home
    assert "기타 용역" in home
    assert "매번 검색하기 번거로우신가요?" in home
    assert 'href="/pricing/"' in home
    assert "알림은 얼마나 정확하고 빠른가요?" in home
    assert "mailto:qwqw050009@gmail.com" in home
    assert "카카오톡 · 준비 중" in home
    assert "로그인</a>" not in home
    assert 'href="/login' not in home
    assert "낙찰까지 받았습니다" not in home
    footer_bits = ("지원사업", "입찰공고", "요금제", "사이트 소개",
                   "개인정보처리방침", "이용약관", "문의")
    for bit in footer_bits:
        assert bit in home
    assert "© 지원사업 마감판" in home
    assert "[000-00-00000]" in home


def test_alert_js_is_mailto_not_checkout():
    root = os.path.join(os.path.dirname(__file__), "..")
    js = open(os.path.join(root, "static", "alert.js"), encoding="utf-8").read()
    assert "mailto:" in js
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
    test_copy_has_three_plans_and_no_fake_review()
    test_business_placeholders_are_not_invented()
    test_pricing_page_render()
    test_home_hero_and_footer()
    test_alert_js_is_mailto_not_checkout()
    test_home_faqs_keep_counts_and_landing()
    print("ok")
