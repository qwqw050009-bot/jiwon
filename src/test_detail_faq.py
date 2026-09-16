# -*- coding: utf-8 -*-
"""상세 FAQ·신청 순서·허브 링크. 없는 자격을 지어내지 않는다."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import config
import detail_faq
import filters
import intros
import serp


def test_notice_faqs_are_grounded_and_visible_length():
    row = {
        "title": "특례보증",
        "org": "신용보증재단",
        "region": "서울",
        "target": "소상공인",
        "amount": "최대 2,000만원",
        "method": "온라인 신청",
        "detail_url": "https://www.bizinfo.go.kr/n",
        "apply_start": "2026-09-01",
        "apply_end": "2026-09-20",
        "period_type": "dated",
        "deadline_line": "2026-09-20 · 시간 미상",
        "source_label": "기업마당",
        "collected_at": "2026-09-16 06:00",
        "ai": {"checklist": ["사업자등록증", "국세완납증명"]},
    }
    faqs = detail_faq.notice_faqs(row)
    assert 3 <= len(faqs) <= 6
    qs = [f["q"] for f in faqs]
    assert "누가 신청할 수 있나요?" in qs
    assert "마감일은 언제인가요?" in qs
    assert "원문은 어디서 신청하나요?" in qs
    assert "신청에 필요한 서류는 무엇인가요?" in qs
    blob = "\n".join(f["a"] for f in faqs)
    assert "소상공인" in blob
    assert "2026-09-20" in blob
    assert "신용보증재단" in blob
    assert "사업자등록증" in blob
    assert "최대 2,000만원" in blob
    assert "심사하거나 보장하지 않습니다" in blob
    assert "업력 3년 이내" not in blob
    ld = intros.faq_jsonld(faqs)
    for f in faqs:
        assert f["q"] in ld
        assert f["a"] in ld
    empty = detail_faq.notice_faqs({"period_type": "always", "period_raw": "예산 소진시까지"})
    who = next(f["a"] for f in empty if f["q"].startswith("누가"))
    assert "지원대상 표기가 없습니다" in who
    assert "추정하지 않" in who


def test_notice_howto_three_steps_match_jsonld():
    steps = detail_faq.notice_howto({
        "target": "중소기업",
        "region": "경기",
        "org": "경기도",
        "apply_start": "2026-09-01",
        "apply_end": "2026-09-30",
        "deadline_line": "2026-09-30 · 시간 미상",
    })
    assert len(steps) == 3
    ld = detail_faq.howto_jsonld("신청 순서", "원문에서 신청", steps)
    assert '"@type": "HowTo"' in ld
    for s in steps:
        assert s["name"] in ld
        assert s["text"] in ld
        assert s["name"] in ("지원대상과 지역 확인", "마감일과 서류 확인", "원문에서 신청")


def test_bid_faqs_have_no_grant_vocab_and_correction():
    row = {
        "org": "중구청",
        "ntce_org": "서울특별시",
        "close_dt": "2026-09-18 18:00",
        "deadline_line": "2026-09-18 18:00 (KST)",
        "budget": "8,500만원",
        "region": "서울",
        "detail_url": "https://www.g2b.go.kr/n",
        "notice_no": "20260915099",
        "seq": "001",
        "is_correction": True,
        "is_open": True,
        "kind": "물품",
    }
    faqs = detail_faq.bid_notice_faqs(row)
    assert 3 <= len(faqs) <= 6
    blob = "\n".join(f["q"] + f["a"] for f in faqs)
    assert "지원금" not in blob
    assert "바우처" not in blob
    assert "보조금" not in blob
    assert "중구청" in blob
    assert "8,500만원" in blob
    assert "정정공고" in blob
    howto = detail_faq.bid_notice_howto(row)
    assert len(howto) == 3
    ht = "\n".join(s["text"] for s in howto)
    assert "지원금" not in ht
    assert "나라장터" in ht


def test_related_hubs_at_least_three_and_skip_self():
    links = intros.related_hubs(path="/region/seoul/startup/", region="서울", category="창업")
    assert len(links) >= 3
    hrefs = [x["href"] for x in links]
    assert "/region/seoul/startup/" not in hrefs
    assert "/urgent/" in hrefs
    assert len(hrefs) == len(set(hrefs))
    hub = intros.related_hubs(path="/category/")
    assert len(hub) >= 3
    bid = intros.bid_related_hubs(path="/bid/kind/goods/", kind_slug="goods")
    assert len(bid) >= 3
    assert "/bid/kind/goods/" not in [x["href"] for x in bid]
    assert all("지원금" not in x["name"] for x in bid)


def test_today_rail_only_dday_zero():
    items = [
        {"dday": 0, "title": "오늘"},
        {"dday": 3, "title": "주간"},
        {"dday": 9999, "title": "상시"},
        {"dday": -1, "title": "마감"},
    ]
    rail = filters.today_rail(items)
    assert [a["title"] for a in rail] == ["오늘"]
    assert filters.urgent_rail(items)[0]["title"] == "오늘"


def test_ledes_stay_unique_with_counts():
    cats = {c["name"]: c for c in config.CATEGORIES}
    items = [{"dday": 0, "period_type": "dated", "is_open": True}] * 2
    items += [{"dday": 3, "period_type": "dated", "is_open": True}]
    seen = set()
    for r in config.REGIONS:
        lede = serp.region_lede(r["name"], items)
        assert lede not in seen, r["name"]
        seen.add(lede)
        assert "오늘 마감 2건" in lede
        if r["name"] == "전남광주":
            assert "전남광주통합특별시" in lede
    cat_seen = set()
    for c in config.CATEGORIES:
        lede = serp.category_lede(c["name"], cats[c["name"]], items)
        assert lede not in cat_seen
        cat_seen.add(lede)
        assert "오늘 마감 2건" in lede
    combo = serp.combo_lede("서울", "창업", items)
    assert "서울" in combo and "창업" in combo
    assert serp.notice_title({"title": "소상공인 특례보증", "dday": 0}).startswith("오늘마감")


def test_seq_correction_and_compact_bid_flags():
    assert detail_faq.seq_is_correction("001")
    assert detail_faq.seq_is_correction(1)
    assert not detail_faq.seq_is_correction("000")
    assert not detail_faq.seq_is_correction("")
    rec = filters.compact_bid({
        "id": "20260915001-001", "title": "정정", "kind": "물품",
        "kind_slug": "goods", "org": "중구청", "budget_card": "1천만원",
        "budget_raw": 10_000_000, "close_dt": "2026-09-18 18:00",
        "dday": 2, "status": "open", "bid_no": "20260915001",
        "is_correction": True, "is_new": False,
        "detail_url": "https://www.g2b.go.kr/n",
    })
    assert rec["corr"] == 1
    assert "n" not in rec


if __name__ == "__main__":
    test_notice_faqs_are_grounded_and_visible_length()
    test_notice_howto_three_steps_match_jsonld()
    test_bid_faqs_have_no_grant_vocab_and_correction()
    test_related_hubs_at_least_three_and_skip_self()
    test_today_rail_only_dday_zero()
    test_ledes_stay_unique_with_counts()
    test_seq_correction_and_compact_bid_flags()
    print("detail faq tests ok")
