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
        "ai": {"summary": "이 사업은 초기창업 사업화 자금을 지원합니다. 두 번째 문장."},
    }
    row.update(kw)
    return row


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
            ]
            paras, faqs = intros.build(r["name"], c["name"], cats[c["name"]], items)
            assert 2 <= len(paras) <= 4, (r["name"], c["name"], len(paras))
            blob = "\n".join(paras)
            assert blob not in seen
            seen.add(blob)
            assert r["name"] in blob
            if r["name"] == "전국":
                assert "전국 단위로" in blob
            else:
                assert f"{r['name']} 지역에서" in blob
                assert f"{r['name']}은 지역에서" not in blob
                assert f"{r['name']}는 지역에서" not in blob
            assert c["name"] in blob
            assert "기관A" in blob or "기관B" in blob
            assert len(faqs) >= 4
            qs = [f["q"] for f in faqs]
            ans = [f["a"] for f in faqs]
            assert len(qs) == len(set(qs))
            for f in faqs:
                assert f["q"] and f["a"]
            # JSON-LD 문구는 화면 FAQ와 같아야 한다
            ld = intros.faq_jsonld(faqs)
            for f in faqs:
                assert f["q"] in ld
                assert f["a"] in ld
            # 가짜 공고를 지어내지 않는다
            assert "테스트가 아닌 가짜" not in blob


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


def test_blurb_one_line_from_cache():
    assert intros.blurb_of({}) == ""
    b = intros.blurb_of(_item())
    assert "초기창업" in b
    assert "두 번째" not in b
    assert len(b) <= 90


if __name__ == "__main__":
    test_intro_length_and_uniqueness()
    test_jeonnam_gwangju_stays_united()
    test_ad_plan_thin_vs_long()
    test_blurb_one_line_from_cache()
    print("intros tests ok")
