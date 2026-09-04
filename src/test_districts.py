# -*- coding: utf-8 -*-
"""시군구 허용 목록·매칭·슬러그 충돌 회귀 확인."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import config
import districts as dmod
import sources


def test_whitelist_integrity():
    assert len(dmod.DISTRICTS) >= 180
    slugs = {c["slug"] for c in config.CATEGORIES}
    sido_names = {r["name"] for r in config.REGIONS}
    seen = set()
    for d in dmod.DISTRICTS:
        assert d["sido_name"] in sido_names
        assert d["sido_name"] != "전국"
        assert d["slug"] not in slugs, d
        assert d["name_ko"] not in dmod.NOISE_TAGS
        key = (d["sido_name"], d["slug"])
        assert key not in seen
        seen.add(key)
    # 전남광주는 분리하지 않는다
    jeonnam = [x for x in dmod.DISTRICTS if x["sido_name"] == "전남광주"]
    assert any(x["name_ko"] == "여수시" for x in jeonnam)
    assert any(x["name_ko"] == "광산구" for x in jeonnam)
    assert all(x["sido_name"] != "전남" and x["sido_name"] != "광주" for x in dmod.DISTRICTS)


def test_noise_and_ambiguous_omitted():
    names = {x["name_ko"] for x in dmod.DISTRICTS}
    for n in dmod.NOISE_TAGS:
        assert n not in names, n
    for n in ("중구", "동구", "서구", "남구", "북구", "강서구", "고성군",
              "전시", "서울특별시", "전남광주통합특별시", "세종시"):
        assert n not in names, n


def test_high_signal_districts_present():
    want = {
        ("경기", "안산시", "ansan"),
        ("경기", "화성시", "hwaseong"),
        ("경기", "부천시", "bucheon"),
        ("경기", "용인시", "yongin"),
        ("경기", "수원시", "suwon"),
        ("경남", "진주시", "jinju"),
        ("경남", "김해시", "gimhae"),
        ("경북", "구미시", "gumi"),
        ("전남광주", "여수시", "yeosu"),
        ("강원", "춘천시", "chuncheon"),
    }
    have = {(x["sido_name"], x["name_ko"], x["slug"]) for x in dmod.DISTRICTS}
    for row in want:
        assert row in have, row


def test_belongs_exact_tag_and_sido():
    ansan = next(x for x in dmod.DISTRICTS if x["name_ko"] == "안산시")
    jinju = next(x for x in dmod.DISTRICTS if x["name_ko"] == "진주시")
    ok = {"tags": ["경영", "경기", "안산시"], "region": "경기"}
    nationwide = {"tags": ["안산시", "2026"], "region": "전국"}
    wrong_sido = {"tags": ["안산시"], "region": "경남"}
    no_tag = {"tags": ["경기", "경영"], "region": "경기"}
    no_tags_field = {"region": "경기"}
    assert dmod.belongs(ok, ansan)
    assert dmod.belongs(nationwide, ansan)
    assert not dmod.belongs(wrong_sido, ansan)
    assert not dmod.belongs(no_tag, ansan)
    assert not dmod.belongs(no_tags_field, ansan)
    assert not dmod.belongs(ok, jinju)
    # 다른 시도 공고의 태그가 우연히 겹쳐도 넣지 않는다
    hanam = next(x for x in dmod.DISTRICTS if x["name_ko"] == "하남시")
    assert hanam["sido_name"] == "경기"
    assert not dmod.belongs({"tags": ["하남시"], "region": "경남"}, hanam)
    assert dmod.belongs({"tags": ["하남시"], "region": "경기"}, hanam)


def test_grouped_min_count():
    ansan = {"tags": ["안산시"], "region": "경기", "id": "1", "category": "경영"}
    rows = [dict(ansan, id=str(i)) for i in range(2)]
    assert "경기" not in dmod.grouped(rows)
    rows.append({"tags": ["안산시"], "region": "전국", "id": "n", "category": "금융"})
    g = dmod.grouped(rows)
    assert len(g["경기"]) == 1
    d, items = g["경기"][0]
    assert d["slug"] == "ansan"
    assert len(items) == 3


def test_api_cache_generates_high_volume_paths():
    cache = os.path.join(os.path.dirname(__file__), "..", "data", "api_cache.json")
    if not os.path.exists(cache):
        return
    rows = sources.JsonSource(cache).fetch()
    g = dmod.grouped(rows)
    slugs = {(d["sido_name"], d["slug"]) for sido in g.values() for d, _ in sido}
    assert ("경기", "ansan") in slugs
    assert ("경기", "hwaseong") in slugs
    assert ("경남", "jinju") in slugs
    assert ("경북", "gumi") in slugs
    assert ("전남광주", "yeosu") in slugs
    assert ("강원", "chuncheon") in slugs
    # 가짜 경로는 허용 목록에 없으므로 생성 집합에 없음
    assert ("경기", "not-a-city") not in slugs
    # 전남광주 시군구는 jeonnam-gwangju 슬러그 아래로만
    for d, items in g.get("전남광주", []):
        assert dmod.SIDO_SLUG[d["sido_name"]] == "jeonnam-gwangju"
        assert len(items) >= dmod.MIN_COUNT
    # 광주/전남으로 쪼개진 키가 없다
    assert "광주" not in g and "전남" not in g


if __name__ == "__main__":
    test_whitelist_integrity()
    test_noise_and_ambiguous_omitted()
    test_high_signal_districts_present()
    test_belongs_exact_tag_and_sido()
    test_grouped_min_count()
    test_api_cache_generates_high_volume_paths()
    print("districts tests ok")
