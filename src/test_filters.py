# -*- coding: utf-8 -*-
"""금액 밴드·시군구 태그·compact feed 회귀."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import filters
import enrich


def test_amount_won_reads_korean_units():
    assert filters.amount_won("기업당 3백만원 이내") == 3_000_000
    assert filters.amount_won("기업당 최대 2,000만원 이내") == 20_000_000
    assert filters.amount_won("최대 2억원") == 200_000_000
    assert filters.amount_won("1인당 500만원") == 5_000_000
    assert filters.amount_won("총 사업비의 50%") is None
    assert filters.amount_won("공고문 참조") is None
    assert filters.amount_won("") is None
    assert filters.amount_won(None) is None


def test_amount_band_uses_amount_of_not_placeholder():
    row = {
        "amount": "공고문 참조",
        "points": ["기업당 최대 2,000만원 이내 특례보증을 지원합니다."],
    }
    assert enrich.amount_of(row)
    assert filters.amount_band_id(row) == "10to50"
    empty = {"amount": "공고문 참조", "points": ["대상은 소상공인입니다."]}
    assert filters.amount_band_id(empty) == "unk"
    small = {"amount": "기업당 3백만원 이내"}
    assert filters.amount_band_id(small) == "lt10"
    big = {"amount": "최대 2억원"}
    assert filters.amount_band_id(big) == "gte100"


def test_districts_of_exact_tag_only():
    row = {
        "region": "경기",
        "tags": ["경영", "경기", "안산시", "2026"],
    }
    assert filters.districts_of(row) == ["안산시"]
    other = {"region": "서울", "tags": ["안산시"]}
    assert filters.districts_of(other) == []
    nation = {"region": "전국", "tags": ["안산시"]}
    assert "안산시" in filters.districts_of(nation)
    guessed = {"region": "경기", "title": "[안산] 지원", "tags": []}
    assert filters.districts_of(guessed) == []


def test_source_and_compact_keys():
    row = {
        "id": "abc", "title": "특례보증", "category": "금융", "region": "충남",
        "org": "충청남도", "amount_card": "최대 2,000만원", "apply_end": "2026-09-20",
        "dday": 4, "is_new": True, "period_raw": "2026-09-01 ~ 2026-09-20",
        "period_type": "dated", "blurb": "한 줄", "target_short": "소상공인",
        "signals": [{"cls": "loan", "label": "융자·보증"}],
        "amount": "최대 2,000만원",
        "tags": ["천안시", "충남"],
    }
    rec = filters.compact(row)
    assert rec["i"] == "abc"
    assert rec["src"] == "bizinfo"
    assert rec["b"] == "10to50"
    assert rec["g"] == ["천안시"]
    assert rec["n"] == 1
    assert rec["w"] == "소상공인"
    assert rec["sg"][0]["k"] == "loan"
    ks = filters.compact({**row, "source": "kstartup", "tags": []})
    assert ks["src"] == "kstartup"
    assert "g" not in ks


def test_tally_and_rail_deadline_first():
    items = [
        {"dday": 0, "period_type": "dated", "source": "bizinfo"},
        {"dday": 3, "period_type": "dated", "source": "kstartup"},
        {"dday": 9999, "period_type": "always"},
        {"dday": 20, "period_type": "dated"},
        {"dday": -1, "period_type": "dated"},
    ]
    t = filters.source_tally(items)
    assert t["today"] == 1
    assert t["week"] == 2
    assert t["always"] == 1
    assert t["kstartup"] == 1
    assert t["bizinfo"] == 4
    rail = filters.urgent_rail(items, limit=8)
    assert [a["dday"] for a in rail] == [0, 3]


def test_related_notices_prefer_same_region_category():
    pool = [
        {"id": "a", "region": "서울", "category": "금융", "dday": 2, "is_open": True},
        {"id": "b", "region": "서울", "category": "금융", "dday": 1, "is_open": True},
        {"id": "c", "region": "서울", "category": "창업", "dday": 0, "is_open": True},
        {"id": "d", "region": "경기", "category": "금융", "dday": 3, "is_open": True},
        {"id": "e", "region": "서울", "category": "금융", "dday": -2, "is_open": False},
    ]
    rel = filters.related_notices(pool[0], pool, limit=3)
    assert [x["id"] for x in rel] == ["b", "c", "d"]
    assert all(x["id"] != "a" for x in rel)
    assert all(x["id"] != "e" for x in rel)
    empty = filters.related_notices(pool[0], [], limit=5)
    assert empty == []


if __name__ == "__main__":
    test_amount_won_reads_korean_units()
    test_amount_band_uses_amount_of_not_placeholder()
    test_districts_of_exact_tag_only()
    test_source_and_compact_keys()
    test_tally_and_rail_deadline_first()
    test_related_notices_prefer_same_region_category()
    print("filters tests ok")
