# -*- coding: utf-8 -*-
"""지역×분야 소개문·FAQ·광고 밀도 회귀 확인."""
import os
import re
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
                assert "사업장 소재지 제한이 없는" in blob or "전국에서 신청할 수 있는" in blob
            elif r["name"] == "전남광주":
                assert "전남광주통합특별시" in blob
                assert "광주와 전남을 따로" in blob or "광주와 전남을 한" in blob or "광주와 전남을 나누지" in blob
            else:
                assert r["name"] in blob
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
        assert "3건" in blob
        assert "상시" in blob or "날짜 없는" in blob
        assert "3건" in faqs[0]["a"]
        faq_blob = "\n".join(f["a"] for f in faqs)
        assert "서울경제진흥원" in faq_blob or "중소벤처기업부" in faq_blob
        assert "매일 아침 목록에 반영됩니다" not in faq_blob
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
    g = intros.blurb_of(generic)
    assert g
    assert "이(가)" not in g and "을(를)" not in g
    assert "대상으로 진행하는" not in g
    assert "서울경제진흥원" in g
    assert " · " in g
    generic_amt = _item(org="고용노동부", ai={"summary":
        "고용노동부가 서울 지역 소상공인을 대상으로 진행하는 창업 분야 지원사업입니다. 지원규모는 최대 1억원 수준입니다."})
    g2 = intros.blurb_of(generic_amt)
    assert g2
    assert "대상으로 진행하는" not in g2
    assert "고용노동부" in g2
    # 실제 운영 데이터처럼 boilerplate 뒤에 진짜 개요 문장이 붙는 경우.
    # 예전엔 _GENERIC_BLURB가 뒷부분만 지워서 "중소기업을 ." 같은 잘린
    # 조각이 그대로 남는 버그가 있었다(2026-09-04 라이브에서 실제 발견).
    generic_with_overview = _item(ai={"summary":
        "산업통상부가 전국 지역 중소기업을 대상으로 진행하는 기술 분야 지원사업입니다. "
        "지원규모는 1천만원 수준입니다. "
        "한국세라믹기술원 보유기술을 이전받은 기업의 조기사업화지원을 위하여 아래와 같이 공고하오니 많은 신청 바랍니다."})
    b2 = intros.blurb_of(generic_with_overview)
    assert "중소기업을" not in b2
    assert "산업통상부" not in b2
    assert "한국세라믹기술원" in b2


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
    assert "/guide/sme-apply/" in "\n".join(mparas)
    assert intros.CATEGORY_GUIDE["창업"][0] == "/guide/pre-vs-early/"
    assert intros.CATEGORY_GUIDE["경영"][0] == "/guide/sme-apply/"


def test_district_intros_from_visible_facts():
    cats = {c["name"]: c for c in config.CATEGORIES}
    items = [
        _item(region="경기", category="경영", title="안산 경영 1",
              org="안산시", dday=2, apply_end="2026-09-06"),
        _item(region="전국", category="경영", title="안산 상시",
              org="중소벤처기업부", period_type="always",
              period_raw="예산 소진시까지", dday=9999),
        _item(region="경기", category="금융", title="안산 금융",
              org="경기도", dday=12, apply_end="2026-09-16"),
    ]
    paras = intros.district_page_intro("경기", "안산시", items)
    blob = "\n".join(paras)
    assert "3건" in blob
    assert "안산시" in blob
    assert "해시태그" in blob
    assert "안산시" in blob and "경기도" in blob or "소관기관" in blob
    for bad in AWKWARD:
        assert bad not in blob, bad
    paras2, faqs = intros.district_combo_intro(
        "경기", "안산시", "경영", cats["경영"], items[:2])
    blob2 = "\n".join(paras2)
    assert "경영" in blob2 and "2건" in blob2
    assert "2건" in faqs[0]["a"]
    ld = intros.faq_jsonld(faqs)
    for f in faqs:
        assert f["q"] in ld and f["a"] in ld
    # 전남광주는 통합 단위로 남긴다
    jparas = intros.district_page_intro("전남광주", "여수시", [
        _item(region="전남광주", org="전남광주통합특별시"),
    ])
    jblob = "\n".join(jparas)
    assert "전남광주통합특별시" in jblob
    assert "여수시" in jblob
    assert "광주시만" not in jblob
    assert "광주와 전남을 따로" in jblob


def test_home_and_category_search_copy():
    html = intros.home_intro(2, 11, 40)
    assert "오늘 마감" in html and "이번 주 마감" in html
    assert "2건" in html and "11건" in html and "40건" in html
    assert "회원가입 없이" in html
    assert "/urgent/" in html
    hrefs = [g["href"] for g in intros.HOME_GUIDES]
    assert hrefs == [
        "/guide/find-by-deadline/",
        "/guide/workplace-region/",
        "/guide/deadline-alert/",
    ]
    assert intros.category_title("창업") == "창업 지원사업 마감일 | 지원사업 마감판"
    desc = intros.category_desc("금융", {"desc": "융자·보증·이차보전 등 자금 지원"})
    assert desc.startswith("금융 분야 정부지원사업을 마감일 순으로")
    assert "회원가입 없이" in desc
    assert "지역별로" in desc


def _strip_tokens(text, *tokens):
    t = re.sub(r"<[^>]+>", " ", text or "")
    for tok in tokens:
        if tok:
            t = t.replace(tok, "X")
    return " ".join(t.split())


def _token_jaccard(left, right):
    left_set, right_set = set(left.split()), set(right.split())
    return len(left_set & right_set) / max(1, len(left_set | right_set))


def test_etc_combo_guide_josa():
    """기타 가이드 제목 '보는 법'은 받침이 있어 을이다. 법를가 나오면 안 된다."""
    cats = {c["name"]: c for c in config.CATEGORIES}
    items = [
        _item(region="경북", category="기타", title="경북 기타 1",
              org="경상북도", dday=0, apply_end="2026-09-04"),
        _item(region="경북", category="기타", title="경북 기타 2", org="중소벤처기업부",
              period_type="always", period_raw="예산 소진시까지", dday=9999),
        _item(region="경북", category="기타", title="경북 기타 3", org="산업통상부", dday=12),
    ]
    paras, _ = intros.build("경북", "기타", cats["기타"], items)
    html = "\n".join(paras)
    plain = re.sub(r"<[^>]+>", "", html)
    assert "법를" not in html
    assert "법를" not in plain
    assert "법을" in plain
    assert "이(가)" not in html and "을(를)" not in html
    nxt = intros._next_step("기타", {"n": 2})
    assert "법를" not in nxt
    assert re.search(r"법</a>을", nxt)
    import enrich
    for name, (_href, gname) in intros.CATEGORY_GUIDE.items():
        step = intros._next_step(name, {"n": 1})
        eul = enrich._josa(gname, "을", "를")
        wrong = "를" if eul == "을" else "을"
        assert f"</a>{wrong}" not in step, (name, gname, step)
        if f"</a>{eul}" in step:
            assert step.count(f"</a>{eul}") >= 1


def test_deadline_para_varies_and_skips_always_cta_when_zero():
    urgent = [_item(dday=0, apply_end="2026-09-04", title="오늘A")]
    dated = urgent + [_item(dday=20, apply_end="2026-09-24", title="여유A")]
    always = [_item(period_type="always", period_raw="예산 소진시까지", dday=9999)]
    texts = [
        intros._deadline_para(urgent, dated, always, style=i, label="창업")
        for i in range(5)
    ]
    assert len(set(texts)) >= 4, texts
    empty = intros._deadline_para(urgent, dated, [], style=0)
    assert "/guide/always-deadline/" not in empty
    assert "상시" not in empty
    compact = intros._deadline_para(
        urgent, dated, [], style=2, compact=True)
    assert compact == ""
    compact_al = [
        intros._deadline_para(
            urgent, dated, always, style=i, compact=True, label="금융")
        for i in range(5)
    ]
    assert all("오늘 마감" not in t for t in compact_al)
    assert len(set(compact_al)) >= 3


def test_combos_differ_beyond_region_category_tokens():
    """같은 목록 사실이어도 조합마다 문장 골격이 달라야 한다."""
    cats = {c["name"]: c for c in config.CATEGORIES}
    same = [
        _item(title="공통 공고 오늘", org="서울경제진흥원", dday=0, apply_end="2026-09-04"),
        _item(title="공통 공고 상시", org="중소벤처기업부",
              period_type="always", period_raw="예산 소진시까지", dday=9999),
        _item(title="공통 공고 여유", org="산업통상부", dday=20, apply_end="2026-09-24"),
    ]
    pairs = [
        ("서울", "창업", "경기", "금융"),
        ("서울", "창업", "대구", "창업"),
        ("서울", "창업", "서울", "금융"),
        ("전남광주", "경영", "전국", "경영"),
        ("제주", "수출", "세종", "인력"),
    ]
    blobs = {}
    for a, b, c, d in pairs:
        for region, category in ((a, b), (c, d)):
            key = (region, category)
            if key in blobs:
                continue
            paras, _ = intros.build(region, category, cats[category], same)
            blobs[key] = "\n".join(paras)
    for a, b, c, d in pairs:
        left = _strip_tokens(blobs[(a, b)], a, b, "전남광주통합특별시", "전남광주")
        right = _strip_tokens(blobs[(c, d)], c, d, "전남광주통합특별시", "전남광주")
        assert left != right, ((a, b), (c, d), left[:80], right[:80])
        share = _token_jaccard(left, right)
        # 지역·분야 토큰만 바꾼 복붙이면 0.70을 넘는다. 레이아웃·기관·분야가
        # 다른 조합은 그 아래여야 한다.
        assert share < 0.70, ((a, b), (c, d), share, left[:120], right[:120])
        dl_left = intros._deadline_para(
            [same[0]], [same[0], same[2]], [same[1]],
            style=intros._layout_id(f"{a}|{b}|dl"), label=b, compact=True)
        dl_right = intros._deadline_para(
            [same[0]], [same[0], same[2]], [same[1]],
            style=intros._layout_id(f"{c}|{d}|dl"), label=d, compact=True)
        if intros._layout_id(f"{a}|{b}|dl") != intros._layout_id(f"{c}|{d}|dl") or b != d:
            assert dl_left != dl_right, ((a, b), (c, d), dl_left, dl_right)


def test_intro_has_no_repeated_sentences():
    cats = {c["name"]: c for c in config.CATEGORIES}
    items = [
        _item(title="오늘 마감 공고", org="서울경제진흥원", dday=0, apply_end="2026-09-04",
              target="소상공인"),
        _item(title="상시 공고", org="중소벤처기업부", period_type="always",
              period_raw="예산 소진시까지", dday=9999, target="중소기업"),
        _item(title="여유 공고", org="산업통상부", dday=20, apply_end="2026-09-24",
              target="중소기업"),
    ]
    samples = [("서울", "창업"), ("경기", "금융"), ("전남광주", "경영"),
               ("전국", "기술"), ("제주", "수출"), ("대구", "인력"),
               ("세종", "내수"), ("경북", "기타")]
    for region, category in samples:
        paras, faqs = intros.build(region, category, cats[category], items)
        blob = "\n".join(paras)
        sents = [s.strip() for s in re.split(r"(?<=다\.)\s+", blob) if s.strip()]
        assert len(sents) == len(set(sents)), (region, category, sents)
        faq_text = "\n".join(f["a"] for f in faqs)
        assert "서울경제진흥원" in faq_text or "중소벤처기업부" in faq_text
        assert "소상공인" in faq_text or "중소기업" in faq_text
        ld = intros.faq_jsonld(faqs)
        for f in faqs:
            assert f["q"] in ld and f["a"] in ld


def test_guide_tags_cover_all_slugs():
    import guides
    slugs = [slug for slug, *_ in guides.build()]
    for slug in slugs:
        assert slug in guides.TAGS, slug
        name, cls = guides.tag_of(slug)
        assert name != "가이드", slug
        assert cls.startswith("tag-")


def test_deadline_guide_exists_and_links_lists():
    import guides
    rows = {slug: (h1, desc, content) for slug, h1, desc, content in guides.build()}
    assert "find-by-deadline" in rows
    assert "pre-vs-early" in rows
    assert "grant-vs-loan" in rows
    content = rows["find-by-deadline"][2]
    assert "오늘 마감" in content and "이번 주 마감" in content
    assert "/category/startup/" in content
    assert "/category/financial/" in content
    assert "체험" not in content
    assert "/category/financial/" in rows["grant-vs-loan"][2]
    assert "/category/startup/" in rows["pre-vs-early"][2]
    for slug in ("sme-apply", "sme-types", "deadline-alert", "workplace-region"):
        assert slug in rows, slug
    assert "/category/management/" in rows["sme-apply"][2]
    assert "/guide/sme-grant-checklist/" in rows["sme-apply"][2]
    assert "/category/financial/" in rows["sme-types"][2]
    assert "/calendar/" in rows["deadline-alert"][2]
    assert "/urgent/" in rows["deadline-alert"][2]
    assert "/region/nationwide/" in rows["workplace-region"][2]
    assert "/region/jeonnam-gwangju/" in rows["workplace-region"][2]
    assert "광주와 전남을 따로" in rows["workplace-region"][2]


if __name__ == "__main__":
    test_intro_length_and_uniqueness()
    test_sample_combos_read_naturally()
    test_jeonnam_gwangju_stays_united()
    test_ad_plan_thin_vs_long()
    test_blurb_skips_generic_fallback()
    test_hub_and_page_intros()
    test_district_intros_from_visible_facts()
    test_home_and_category_search_copy()
    test_etc_combo_guide_josa()
    test_deadline_para_varies_and_skips_always_cta_when_zero()
    test_combos_differ_beyond_region_category_tokens()
    test_intro_has_no_repeated_sentences()
    test_guide_tags_cover_all_slugs()
    test_deadline_guide_exists_and_links_lists()
    print("intros tests ok")
