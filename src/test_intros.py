# -*- coding: utf-8 -*-
"""지역×분야 소개문·FAQ·광고 밀도 회귀 확인."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import config
import intros


def _item(**kw):
    row = {
        "title": "테스트 공고",
        "org": "서울경제진흥원",
        "category": "창업",
        "region": "서울",
        "period_type": "dated",
        "period_raw": "2026-09-01 ~ 2026-09-10",
        "apply_end": "2026-09-10",
        "dday": 6,
        "ai": {"summary": "초기창업 사업화 자금을 최대 1억원까지 지원합니다. 두 번째 문장."},
    }
    row.update(kw)
    return row


AWKWARD = (
    "모아 둔 페이지입니다",
    "해당하는 공고입니다",
    "은 지역에서",
    "는 지역에서",
    "목록에서 연",
    "신청을 대행하지",
    "없는 사업을 보태",
    "이 사이트는 신청",
)


def test_intro_length_and_uniqueness():
    cats = {c["name"]: c for c in config.CATEGORIES}
    seen = set()
    for r in config.REGIONS:
        for c in config.CATEGORIES:
            items = [
                _item(region=r["name"], category=c["name"],
                      title=f"{r['name']} {c['name']} 1", org="기관A", dday=3),
                _item(region=r["name"], category=c["name"],
                      title=f"{r['name']} {c['name']} 2", org="기관B",
                      period_type="always", period_raw="예산 소진시까지", dday=9999),
                _item(region=r["name"], category=c["name"],
                      title=f"{r['name']} {c['name']} 3", org="기관C", dday=10),
            ]
            paras, faqs = intros.build(r["name"], c["name"], cats[c["name"]], items)
            assert 2 <= len(paras) <= 4, (r["name"], c["name"], len(paras))
            blob = "\n".join(paras)
            faq_text = "\n".join(f["q"] + f["a"] for f in faqs)
            assert blob not in seen
            seen.add(blob)
            assert r["name"] in blob or r["name"] == "전남광주"
            if r["name"] == "전국":
                assert "전국에서 신청할 수 있는" in blob
            elif r["name"] == "전남광주":
                assert "전남광주통합특별시에서" in blob
            else:
                assert f"{r['name']}에서 지금" in blob
                assert f"{r['name']} 지역에서" not in blob
            assert c["name"] in blob
            assert "기관A" in blob or "기관B" in blob
            assert len(faqs) >= 4
            qs = [f["q"] for f in faqs]
            assert len(qs) == len(set(qs))
            for f in faqs:
                assert f["q"] and f["a"]
            ld = intros.faq_jsonld(faqs)
            for f in faqs:
                assert f["q"] in ld
                assert f["a"] in ld
            for bad in AWKWARD:
                assert bad not in blob, (r["name"], c["name"], bad)
                assert bad not in faq_text, (r["name"], c["name"], bad)


def test_sample_combos_read_naturally():
    cats = {c["name"]: c for c in config.CATEGORIES}
    samples = [
        ("서울", "창업"),
        ("경기", "금융"),
        ("전남광주", "창업"),
    ]
    for region, category in samples:
        items = [
            _item(region=region, category=category, title=f"{region} {category} 오늘",
                  org="서울경제진흥원", dday=0, apply_end="2026-09-04"),
            _item(region=region, category=category, title=f"{region} {category} 상시",
                  org="중소벤처기업부", period_type="always",
                  period_raw="예산 소진시까지", dday=9999),
            _item(region=region, category=category, title=f"{region} {category} 여유",
                  org="산업통상부", dday=20, apply_end="2026-09-24"),
        ]
        paras, faqs = intros.build(region, category, cats[category], items)
        blob = "\n".join(paras)
        assert 3 <= len(paras) <= 4
        assert "지원사업은 3건입니다" in blob
        assert "/guide/always-deadline/" in blob
        assert faqs[0]["a"].startswith("이 페이지에는 3건이 있습니다.")
        ld = intros.faq_jsonld(faqs)
        for f in faqs:
            assert f["a"] in ld


def test_jeonnam_gwangju_stays_united():
    cat = next(c for c in config.CATEGORIES if c["name"] == "창업")
    paras, faqs = intros.build("전남광주", "창업", cat, [
        _item(region="전남광주", category="창업", org="전남광주통합특별시"),
    ])
    text = "\n".join(paras) + "\n".join(f["a"] for f in faqs)
    assert "전남광주" in text
    assert "광주와 전남을 따로" in text
    assert "광주시만" not in text


def test_ad_plan_thin_vs_long():
    assert intros.ad_plan(2) == (False, 0, False)
    assert intros.ad_plan(6) == (True, 0, False)
    assert intros.ad_plan(10) == (True, 0, True)
    assert intros.ad_plan(20) == (True, 8, True)
    assert intros.ad_plan(0, has_sections=True) == (True, 0, True)
    empty = {"adsense_client": "ca-pub-x", "adsense_slots": {}}
    assert intros.resolve_ads((True, 8, True), empty) == (False, 0, False)
    filled = {"adsense_client": "ca-pub-x", "adsense_slots": {
        "list_top": "1", "list_mid": "2", "list_bottom": "3"}}
    assert intros.resolve_ads((True, 8, True), filled) == (True, 8, True)


def test_blurb_skips_generic_fallback():
    assert intros.blurb_of({}) == ""
    b = intros.blurb_of(_item())
    assert "초기창업" in b
    assert "두 번째" not in b
    assert len(b) <= 90
    generic = _item(ai={"summary":
        "서울경제진흥원이 서울 지역 중소기업을 대상으로 진행하는 창업 분야 지원사업입니다."})
    assert intros.blurb_of(generic) == ""
    generic_amt = _item(ai={"summary":
        "고용노동부가 서울 지역 소상공인을 대상으로 진행하는 창업 분야 지원사업입니다. 지원규모는 최대 1억원 수준입니다."})
    assert intros.blurb_of(generic_amt) == ""


def test_hub_and_page_intros():
    cats = {c["name"]: c for c in config.CATEGORIES}
    hub_r = intros.region_hub_intro(40, 17)
    assert "17곳" in hub_r
    assert "전남광주통합특별시" in hub_r
    assert "광주와 전남을 한 단위" in hub_r
    hub_c = intros.category_hub_intro(40)
    assert "8종" in hub_c
    paras = intros.region_page_intro("전남광주", [_item(region="전남광주")] * 3)
    blob = "\n".join(paras)
    assert "전남광주통합특별시에서" in blob
    assert "3건" in blob
    for bad in AWKWARD:
        assert bad not in blob
    cparas = intros.category_page_intro("창업", cats["창업"], [_item()] * 4)
    cblob = "\n".join(cparas)
    assert "/guide/pre-vs-early/" in cblob
    mparas = intros.category_page_intro("경영", cats["경영"], [_item(category="경영")] * 2)
    assert "/guide/sme-grant-checklist/" in "\n".join(mparas)
    assert intros.CATEGORY_GUIDE["창업"][0] == "/guide/pre-vs-early/"
    assert intros.CATEGORY_GUIDE["경영"][0] == "/guide/sme-grant-checklist/"


if __name__ == "__main__":
    test_intro_length_and_uniqueness()
    test_sample_combos_read_naturally()
    test_jeonnam_gwangju_stays_united()
    test_ad_plan_thin_vs_long()
    test_blurb_skips_generic_fallback()
    test_hub_and_page_intros()
    print("intros tests ok")
