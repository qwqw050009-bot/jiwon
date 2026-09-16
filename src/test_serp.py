# -*- coding: utf-8 -*-
"""SERP title·description 헬퍼 회귀."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

import config
import intros
import serp


def _item(**kw):
    row = {
        "title": "테스트 공고",
        "org": "서울경제진흥원",
        "category": "창업",
        "region": "서울",
        "period_type": "dated",
        "period_raw": "",
        "dday": 3,
        "is_open": True,
        "is_closed": False,
        "apply_end": "2026-09-19",
        "target": "소상공인",
        "ai": {"summary": "소상공인 대상 창업 사업화 자금입니다. 업력 제한을 원문에서 확인하세요."},
    }
    row.update(kw)
    return row


def _branded(s):
    assert s.endswith("| 지원사업 마감판"), s
    assert "이(가)" not in s and "을(를)" not in s, s
    return s


def test_home_urgent_all_have_magnets():
    rows = [
        _item(dday=0, title="오늘A"),
        _item(dday=2, title="주간A"),
        _item(period_type="always", dday=99, title="상시A"),
        _item(dday=20, title="여유A"),
    ]
    ht = _branded(serp.home_title())
    assert ht.startswith("오늘마감")
    assert "오늘 마감" in ht
    assert "정부지원사업" in ht
    assert "2026" in ht
    hd = serp.home_desc(rows)
    assert "오늘 마감 1건" in hd
    assert "오늘마감" in hd
    assert "이번 주 마감 2건" in hd
    assert "원문" in hd
    assert 70 <= len(hd) <= 120, (len(hd), hd)
    assert "오늘마감" in serp.home_h1()
    assert "오늘 마감" in serp.home_h1()

    urgent = [a for a in rows if 0 <= a["dday"] <= 7]
    ut = _branded(serp.urgent_title(urgent))
    assert ut.startswith("오늘마감")
    assert "오늘 마감" in ut
    assert "2건" in ut
    ud = serp.urgent_desc(urgent)
    assert "오늘마감" in ud and "2건" in ud
    assert "오늘 마감" in ud
    assert "원문" in ud
    assert 70 <= len(ud) <= 120, (len(ud), ud)
    assert "오늘마감" in serp.urgent_h1()
    assert "오늘 마감" in serp.urgent_h1()

    at = _branded(serp.all_title(rows))
    assert at.startswith("정부지원사업 전체")
    assert "4건" in at
    ad = serp.all_desc(rows)
    assert "4건" in ad or "접수" in ad
    assert 70 <= len(ad) <= 120, (len(ad), ad)


def test_no_zero_count_in_titles():
    empty = []
    assert "0건" not in serp.urgent_title(empty)
    assert "0건" not in serp.region_title("서울", empty)
    assert "0건" not in serp.combo_title("경기", "창업", empty)
    assert "0건" not in serp.bid_urgent_title(0)
    assert "0건" not in serp.category_title("창업", empty)


def test_page_types_differ():
    items = [_item(region="경기", category="창업", dday=0) for _ in range(3)]
    titles = [
        serp.home_title(),
        serp.urgent_title(items),
        serp.all_title(items),
        serp.region_hub_title(),
        serp.category_hub_title(),
        serp.region_title("경기", items),
        serp.category_title("창업", items),
        serp.combo_title("경기", "창업", items),
        serp.district_title("경기", "수원", items),
        serp.district_combo_title("경기", "수원", "창업", items),
        serp.guide_hub_title(),
        serp.bid_hub_title(),
    ]
    for t in titles:
        _branded(t)
    assert len(titles) == len(set(titles)), titles
    descs = [
        serp.home_desc(items),
        serp.urgent_desc(items),
        serp.region_desc("경기", items),
        serp.category_desc("창업", {"desc": "예비·초기창업 사업화 자금"}, items),
        serp.combo_desc("경기", "창업", {"desc": "예비·초기창업 사업화 자금"}, items),
        serp.district_desc("경기", "수원", items),
        serp.guide_hub_desc(),
        serp.bid_hub_desc({"today": 1, "urgent": 3, "open": 10}),
    ]
    for d in descs:
        assert d
        assert "이(가)" not in d and "을(를)" not in d
    # 페이지 종류마다 앞머리가 달라야 스니펫이 안 겹친다.
    opens = [d[:12] for d in descs]
    assert len(opens) == len(set(opens)), opens


def test_region_and_category_variants():
    items = [_item(dday=4) for _ in range(5)]
    seen = []
    for r in config.REGIONS:
        t = _branded(serp.region_title(r["name"], items))
        assert r["name"] == "전남광주" or r["name"] in t or (
            r["name"] == "전국" and t.startswith("전국")
        )
        if r["name"] == "전남광주":
            assert "전남광주" in t
            assert "광주광역시" not in t
        seen.append(t)
        d = serp.region_desc(r["name"], items)
        assert "5건" in d
        assert 70 <= len(d) <= 120, (r["name"], len(d), d)
    assert len(seen) == len(set(seen))

    cats = []
    for c in config.CATEGORIES:
        t = _branded(serp.category_title(c["name"], items))
        assert c["name"] in t or (c["name"] == "기술" and "R&D" in t)
        cats.append(t)
        d = serp.category_desc(c["name"], c, items)
        assert "5건" in d
        assert 70 <= len(d) <= 130, (c["name"], len(d), d)
    assert len(cats) == len(set(cats))


def test_combo_titles_unique_and_use_real_counts():
    titles = []
    for r in config.REGIONS:
        for c in config.CATEGORIES:
            items = [
                _item(region=r["name"], category=c["name"], dday=0),
                _item(region=r["name"], category=c["name"], dday=10),
            ]
            t = _branded(serp.combo_title(r["name"], c["name"], items))
            assert f"{c['name']} 지원사업" in t
            assert "2건" in t
            assert "오늘 마감 1건" in t
            titles.append(t)
            d = serp.combo_desc(r["name"], c["name"], c, items)
            assert "2건" in d
            assert d.startswith(r["name"] if r["name"] != "전남광주" else "전남광주")
    assert len(titles) == len(set(titles))
    # 지역 단독·분야 단독과 앞머리가 다르다.
    assert not serp.combo_title("경기", "창업", [
        _item(region="경기", category="창업", dday=3)
    ]).startswith("경기 소상공인")
    assert "창업 지원금" not in serp.combo_title("경기", "창업", [
        _item(region="경기", category="창업", dday=3)
    ])


def test_notice_urgency_prefix_only_within_week():
    today = _item(dday=0, title="소상공인 특례보증")
    week = _item(dday=3, title="소상공인 특례보증")
    later = _item(dday=20, title="소상공인 특례보증")
    always = _item(period_type="always", period_raw="예산 소진시까지",
                   dday=99, title="소상공인 특례보증")
    closed = _item(dday=-3, is_closed=True, is_open=False, title="소상공인 특례보증",
                   apply_end="2026-09-13")
    assert _branded(serp.notice_title(today)).startswith("오늘마감 ·")
    assert _branded(serp.notice_title(week)).startswith("이번 주 마감 D-3 ·")
    assert "이번 주 마감" not in serp.notice_title(later)
    assert "오늘마감" not in serp.notice_title(later)
    assert "오늘 마감" not in serp.notice_title(later)
    assert "상시 접수" in serp.notice_title(always)
    assert "마감된 공고" not in serp.notice_title(closed)
    assert "소상공인 특례보증" in serp.notice_title(closed)
    assert serp.notice_title(later).startswith("소상공인 특례보증")
    assert serp.notice_desc(today).startswith("오늘마감")
    assert "특례보증" in serp.notice_desc(today) or "소상공인" in serp.notice_desc(today)
    assert "원문" in serp.notice_desc(today)
    assert "접수 마감" in serp.notice_desc(closed)
    assert "마감일 2026-09-19" in serp.notice_desc(later) or "2026-09-19" in serp.notice_desc(later)
    paid = _item(dday=14, apply_end="2026-10-02", target="창업벤처",
                 amount="최대 1,000만원", region="인천")
    pd = serp.notice_desc(paid)
    assert pd.startswith("마감일 2026-10-02")
    assert "대상 창업벤처" in pd
    assert "1,000만원" in pd
    assert "본문 기준" in pd
    assert "본문 규모" not in pd
    assert pd.find("마감일") < pd.find("대상")
    assert pd.find("대상") < pd.find("1,000")
    assert "AX 전환" not in pd
    assert "마감일·신청자격" not in serp.notice_title(paid)


def test_bid_copy_stays_off_support_words():
    banned = ("지원금", "바우처", "보조금", "소상공인 지원")
    texts = [
        serp.bid_hub_title(), serp.bid_hub_desc({"today": 1, "urgent": 4, "open": 20}),
        serp.bid_urgent_title(4), serp.bid_urgent_desc(4),
        serp.bid_kind_title("용역", 8), serp.bid_kind_desc("용역", 8, "용역 입찰공고"),
        serp.bid_region_title("서울", 3), serp.bid_region_desc("서울", 3),
        serp.bid_region_desc("경기", 3),
        serp.bid_notice_title(_item(title="사무용품 구매", dday=0, is_open=True)),
    ]
    for t in texts:
        for b in banned:
            assert b not in t, (b, t)
        if t.endswith("판") or "| 지원사업 마감판" in t:
            _branded(t)
    assert "서울과" in serp.bid_region_desc("서울", 3)
    assert "경기와" in serp.bid_region_desc("경기", 3)
    ht = _branded(serp.bid_hub_title())
    assert "나라장터" in ht and "마감일시" in ht and "2026" in ht
    assert ht.lower().count("나라장터") == 1
    ut = _branded(serp.bid_urgent_title(4))
    assert "나라장터" in ut and "마감일시" in ut and "2026" in ut
    assert "4건" in ut
    kt = _branded(serp.bid_kind_title("용역", 8))
    assert kt.startswith("나라장터 용역 입찰공고")
    assert "마감일시" in kt and "2026" in kt
    hd = serp.bid_hub_desc({"today": 1, "urgent": 4, "open": 20})
    assert "2026" in hd and "나라장터" in hd
    assert "지원금" not in hd


def test_intros_wrappers_match_serp():
    items = [_item(category="금융", dday=1) for _ in range(2)]
    cat = {"desc": "융자·보증·이차보전 등 자금 지원"}
    assert intros.category_title("금융", items) == serp.category_title("금융", items)
    assert intros.category_desc("금융", cat, items) == serp.category_desc("금융", cat, items)


def test_static_and_guide_pages():
    assert "2026" in serp.guide_hub_title()
    assert "자격" in serp.guide_hub_desc()
    for slug in ("about", "privacy", "terms", "contact", "pricing"):
        d = serp.static_desc(slug)
        assert len(d) >= 40
        assert "이(가)" not in d
    assert "요금제" in serp.pricing_title()
    assert "이메일" in serp.pricing_desc()
    assert "ICS" in serp.calendar_title()


def test_gsc_region_and_nationwide_copy():
    items = [_item(dday=4, region="부산") for _ in range(3)]
    bt = _branded(serp.region_title("부산", items))
    assert bt.startswith("부산시 2026 기업 지원사업 공고")
    assert "3건" in bt
    assert "이번 주 마감" in bt
    assert "오늘마감부터" not in bt
    bd = serp.region_desc("부산", items)
    assert "부산시 2026 기업 지원사업 공고" in bd
    assert "광역시" in bd
    assert "원문" in bd
    nt = _branded(serp.region_title("전국", items))
    assert nt.startswith("전국 2026 기업 지원사업 공고")
    assert "이번 주 마감" in nt
    nd = serp.region_desc("전국", items)
    assert "소재지 제한" in nd
    assert nd.startswith("전국 어디서나")
    mgmt = [_item(region="전국", category="경영", dday=10) for _ in range(4)]
    ct = _branded(serp.combo_title("전국", "경영", mgmt))
    assert ct.startswith("전국 경영 지원사업 공고 2026")
    assert "소재지 제한 없음" in ct
    assert "컨설팅" in ct
    cd = serp.combo_desc("전국", "경영", {"desc": "컨설팅·경영개선·시설 지원"}, mgmt)
    assert cd.startswith("전국에서")
    assert "소재지 제한" in cd
    assert "컨설팅" in cd
    assert cd.find("컨설팅") < cd.find("원문")
    etc = serp.combo_title("전국", "기타", mgmt)
    assert "전국 기타 지원사업 공고" in etc
    jeonbuk = serp.combo_title("전북", "기술", [_item(region="전북", category="기술", dday=2)])
    assert jeonbuk.startswith("전북 기술 지원사업 공고 2026")
    empty_busan = _branded(serp.region_title("부산", []))
    assert "오늘마감" not in empty_busan
    assert "광역시" in empty_busan


def test_gsc_notice_longtail_keeps_keywords():
    ax = _item(
        title="2026년 AX 전환 및 확산 시범사업 외부 지원 프로그램 참여기업 모집 공고",
        region="인천", category="창업", org="인천광역시", target="창업벤처",
        dday=16, apply_end="2026-10-02",
    )
    t = _branded(serp.notice_title(ax))
    assert t.startswith("2026년 AX 전환")
    assert "참여기업 모집" in t
    assert "마감된 공고" not in t
    assert "마감일·신청자격" not in t
    d = serp.notice_desc(ax)
    assert "2026-10-02" in d
    assert "창업벤처" in d or "인천" in d
    assert "원문" in d

    fnb = _item(
        title="2026 고양시 F&B 성장지원 프로그램 with G-ROUND 877 참여기업 모집공고",
        region="경기", category="경영", org="스타에셋파트너스(주)",
        target="고양시 소재 F&B·프랜차이즈 분야 창업 7년 이내 초기 창업기업",
        dday=14, apply_end="2026-09-30",
    )
    ft = _branded(serp.notice_title(fnb))
    assert "고양시" in ft and "F&B" in ft
    assert ft.startswith("2026 고양시")
    fd = serp.notice_desc(fnb)
    assert "2026-09-30" in fd
    assert "고양시" in fd or "F&B" in fd

    lotte = _item(
        title="2026년 오프라인 기획전(롯데백화점 부산본점, 10월) 참여기업 모집 공고",
        region="전국", category="내수", org="중소벤처기업부", target="중소기업",
        dday=5, apply_end="2026-09-21",
    )
    lt = _branded(serp.notice_title(lotte))
    assert lt.startswith("이번 주 마감 D-5 ·")
    assert "롯데백화점 부산본점" in lt
    ld = serp.notice_desc(lotte)
    assert ld.startswith("이번 주 마감")
    assert "소재지 제한" in ld


def test_region_and_combo_openings_differ():
    """17개 지역 스니펫 둘째 문장과 지역/조합 앞머리가 같은 틀이 아니어야 한다."""
    items = [_item(dday=4) for _ in range(5)]
    seconds = []
    for r in config.REGIONS:
        d = serp.region_desc(r["name"], items)
        assert "2026 기업 지원사업 공고" in d, (r["name"], d)
        assert "이(가)" not in d
        bits = [p.strip() for p in d.split(".") if p.strip()]
        assert len(bits) >= 2, (r["name"], d)
        seconds.append(bits[1])
        t = serp.region_title(r["name"], items)
        assert "오늘마감부터" not in t
        assert "오늘마감" not in t, (r["name"], t)
    assert len(seconds) == len(set(seconds)), seconds
    busan_r = serp.region_desc("부산", items)
    busan_c = serp.combo_desc("부산", "경영", {"desc": "컨설팅·경영개선·시설 지원"}, items)
    assert busan_r != busan_c
    assert busan_c.startswith("부산시 경영")
    assert "컨설팅" in busan_c
    etc_c = serp.combo_desc("경기", "기타", {"desc": "그 외 지원사업"}, items)
    assert "어려운입니다" not in etc_c
    assert "넣기 어려운 지원입니다" in etc_c
    fin_c = serp.combo_desc("경기", "금융", {"desc": "융자·보증·이차보전 등 자금 지원"}, items)
    assert "금융 지원입니다" in fin_c
    nat_r = serp.region_desc("전국", items)
    nat_c = serp.combo_desc("전국", "경영", {"desc": "컨설팅·경영개선·시설 지원"}, items)
    assert nat_r.startswith("전국 어디서나")
    assert nat_c.startswith("전국에서 신청하는 경영")
    suwon = serp.district_desc("경기", "수원", items)
    assert suwon.startswith("수원 2026 기업 지원사업 공고")
    assert "해시태그" in suwon
    assert suwon != busan_r


def test_ctr_magnets_keep_gsc_heads():
    """클릭용 뒷말을 붙여도 검색어 앞머리와 브랜드 접미사는 유지한다."""
    rows = [_item(dday=0) for _ in range(2)]
    ht = _branded(serp.home_title())
    assert ht.startswith("오늘마감")
    assert "오늘 마감" in ht
    assert "정부지원사업" in ht
    assert "보조금" in ht
    ut = _branded(serp.urgent_title(rows))
    assert ut.startswith("오늘마감 2건")
    assert "오늘 마감" in ut
    seoul = _branded(serp.region_title("서울", rows))
    assert seoul.startswith("서울시 2026 기업 지원사업 공고")
    assert "오늘마감" in seoul
    nd = serp.notice_desc(_item(dday=0, title="소상공인 특례보증"))
    assert nd.startswith("오늘마감")
    assert "대상 소상공인" in nd
    assert "원문에서 신청" in nd


def test_clip_and_counts():
    assert serp.counts_of([
        _item(dday=0), _item(dday=5), _item(period_type="always", dday=99),
        _item(dday=-1, is_open=False),
    ]) == {"n": 4, "today": 1, "week": 2, "always": 1, "open": 3}
    long = "가" * 80 + "다. " + "나" * 80
    clipped = serp.clip_desc(long, lo=70, hi=120)
    assert len(clipped) <= 120
    assert clipped.endswith("다.")


def test_mock_build_html_titles():
    """목업 빌드가 있으면 대표 URL의 title·desc를 읽는다."""
    root = os.path.join(os.path.dirname(__file__), "..", "dist")
    samples = {
        "index.html": ("오늘 마감 정부지원사업", "오늘마감"),
        "urgent/index.html": ("오늘마감", "오늘마감"),
        "all/index.html": ("정부지원사업 전체", "마감일"),
        "region/index.html": ("지역별 정부지원사업", "사업장"),
        "category/index.html": ("분야별 정부지원사업", "8종"),
        "category/startup/index.html": ("창업 지원금", "창업"),
        "region/gyeonggi/index.html": ("경기 2026 기업 지원사업 공고", "기업 지원사업"),
        "region/gyeonggi/startup/index.html": ("경기 창업 지원사업 공고", "창업"),
        "guide/start/index.html": ("정부지원사업 신청 방법", "신청 방법"),
        "bid/index.html": ("나라장터 입찰공고", "나라장터"),
        "bid/urgent/index.html": ("나라장터 이번 주 마감", "마감일시"),
        "bid/kind/service/index.html": ("나라장터 용역 입찰공고", "용역"),
    }
    if not os.path.exists(os.path.join(root, "index.html")):
        return
    for rel, (title_bit, desc_bit) in samples.items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        m = re.search(r"<title>(.*?)</title>", html)
        d = re.search(r'<meta name="description" content="(.*?)"', html)
        assert m, rel
        assert d, rel
        title, desc = m.group(1), d.group(1)
        assert title_bit in title, (rel, title)
        assert "| 지원사업 마감판" in title, (rel, title)
        assert desc_bit in desc, (rel, desc)
        ogt = re.search(r'<meta property="og:title" content="(.*?)"', html)
        ogd = re.search(r'<meta property="og:description" content="(.*?)"', html)
        assert ogt and ogt.group(1) == title
        assert ogd and ogd.group(1) == desc
        assert "이(가)" not in title + desc
        if rel.startswith("bid/"):
            assert "지원금" not in title and "바우처" not in title
            if rel in ("bid/index.html", "bid/urgent/index.html", "bid/kind/service/index.html"):
                assert "나라장터" in title and "마감일시" in title and "2026" in title
    ads = os.path.join(root, "ads.txt")
    if os.path.exists(ads):
        body = open(ads, encoding="utf-8").read()
        assert body.endswith("\n"), repr(body)
        assert body.splitlines()[0] == "google.com, pub-2738052782253666, DIRECT, f08c47fec0942fa0"
        app = os.path.join(root, "app-ads.txt")
        if os.path.exists(app):
            assert open(app, encoding="utf-8").read() == body
    headers = os.path.join(root, "_headers")
    if os.path.exists(headers):
        h = open(headers, encoding="utf-8").read()
        assert "/ads.txt" in h
        assert "/app-ads.txt" in h
        assert "text/plain" in h
        assert "Cache-Control" in h
        assert "/rss.xml" in h
    redirects = os.path.join(root, "_redirects")
    if os.path.exists(redirects):
        r = open(redirects, encoding="utf-8").read()
        assert "/* /index.html" not in r
        assert "/* /404.html" not in r
        assert "/ads.txt" in r


if __name__ == "__main__":
    test_home_urgent_all_have_magnets()
    test_no_zero_count_in_titles()
    test_page_types_differ()
    test_region_and_category_variants()
    test_combo_titles_unique_and_use_real_counts()
    test_notice_urgency_prefix_only_within_week()
    test_bid_copy_stays_off_support_words()
    test_intros_wrappers_match_serp()
    test_static_and_guide_pages()
    test_gsc_region_and_nationwide_copy()
    test_gsc_notice_longtail_keeps_keywords()
    test_region_and_combo_openings_differ()
    test_ctr_magnets_keep_gsc_heads()
    test_clip_and_counts()
    test_mock_build_html_titles()
    print("serp tests ok")
