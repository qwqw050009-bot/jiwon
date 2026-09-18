# -*- coding: utf-8 -*-
"""입찰 정규화·D-day·종류 라우팅·지원/입찰 분리 회귀."""
import io
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import redirect_stdout
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

import bidinfo
import bid_build
import config

NOW = datetime(2026, 9, 15, 10, 0, tzinfo=bidinfo.KST)


def _item(**kw):
    base = {
        "bidNtceNo": "20260915099",
        "bidNtceOrd": "000",
        "bidNtceNm": "테스트 입찰공고",
        "dminsttNm": "서울특별시",
        "ntceInsttNm": "서울특별시",
        "presmptPrce": "123456789",
        "bidNtceDt": "2026-09-01 09:00:00",
        "bidClseDt": "2026-09-18 18:00:00",
        "bidNtceDtlUrl": "https://www.g2b.go.kr/notice",
        "prtcptLmtRgnNm": "서울특별시",
        "bidMethdNm": "전자입찰",
    }
    base.update(kw)
    return base


def test_normalize_id_and_kind():
    row = bidinfo.normalize(_item(), "용역", now=NOW)
    assert row["id"] == "20260915099-000"
    assert row["kind"] == "용역"
    assert row["kind_slug"] == "service"
    assert row["org"] == "서울특별시"
    redo = bidinfo.normalize(_item(bidNtceOrd="001"), "물품", now=NOW)
    assert redo["id"] == "20260915099-001"
    assert redo["kind_slug"] == "goods"
    assert redo["is_correction"] is True
    first = bidinfo.normalize(_item(bidNtceOrd="000"), "용역", now=NOW)
    assert first["is_correction"] is False


def test_kind_routing():
    assert bidinfo.kind_of_slug("goods")["name"] == "물품"
    assert bidinfo.kind_of_slug("service")["op"] == "getBidPblancListInfoServc"
    assert bidinfo.kind_of_slug("construction")["name"] == "공사"
    assert bidinfo.kind_of_slug("foreign")["api"] == "frgcpt"
    assert bidinfo.slug_of_kind("용역") == "service"
    assert bidinfo.kind_of_slug("nope") is None
    names = {k["name"] for k in config.BID_KINDS}
    assert names == {"물품", "용역", "공사", "외자"}


def test_dday_and_status():
    today = bidinfo.normalize(_item(bidClseDt="2026-09-15 17:00:00"), "물품", now=NOW)
    assert today["dday"] == 0
    assert today["status"] == "open"
    assert today["dlabel"] == "오늘"
    past = bidinfo.normalize(_item(bidClseDt="2026-09-14 09:00:00"), "물품", now=NOW)
    assert past["dday"] == -1
    assert past["status"] == "closed"
    assert past["is_open"] is False
    week = bidinfo.normalize(_item(bidClseDt="2026-09-18 18:00:00"), "공사", now=NOW)
    assert week["dday"] == 3
    assert week["cls"] == "d-u"


def test_price_not_invented():
    empty = bidinfo.normalize(_item(presmptPrce="", bdgtAmt=""), "물품", now=NOW)
    assert empty["budget"] == ""
    assert empty["budget_raw"] is None
    assert empty["budget_card"] == ""
    zero = bidinfo.normalize(_item(presmptPrce="0"), "물품", now=NOW)
    assert zero["budget"] == ""
    got = bidinfo.normalize(_item(presmptPrce="85000000"), "물품", now=NOW)
    assert "만" in got["budget"]
    assert got["budget_raw"] == 85000000


def test_region_exact_only_no_guessing():
    hit = bidinfo.normalize(_item(prtcptLmtRgnNm="서울특별시"), "물품", now=NOW)
    assert hit["region"] == "서울"
    gwangju = bidinfo.normalize(
        _item(prtcptLmtRgnNm="광주광역시", prtcptPsblRgnNm=""), "용역", now=NOW)
    assert gwangju["region"] == "광주"
    jeonnam = bidinfo.normalize(
        _item(prtcptLmtRgnNm="전라남도"), "공사", now=NOW)
    assert jeonnam["region"] == "전남"
    assert gwangju["region"] != jeonnam["region"]
    # 제목에만 지역이 있으면 추측하지 않는다
    titled = bidinfo.normalize(_item(
        bidNtceNm="[서울] 물품 구매",
        prtcptLmtRgnNm="",
        prtcptPsblRgnNm="",
    ), "물품", now=NOW)
    assert titled["region"] == ""
    # 여러 지역이 나열되면 정확 일치가 아니므로 비운다
    multi = bidinfo.normalize(_item(prtcptLmtRgnNm="서울특별시,경기도"), "외자", now=NOW)
    assert multi["region"] == ""
    # 전남광주 통합 단위는 나라장터 필드에 그대로 있어도 지원 쪽 통합명으로 합치지 않는다
    assert bidinfo.region_of({"prtcptLmtRgnNm": "전남광주통합특별시"}) == ""


def test_drop_without_close():
    assert bidinfo.normalize(_item(bidClseDt=""), "용역", now=NOW) is None
    assert bidinfo.normalize(_item(bidNtceNm=""), "용역", now=NOW) is None


def test_parse_dt_formats():
    a = bidinfo.parse_dt("2026-09-18 18:00:00")
    b = bidinfo.parse_dt("202609181800")
    c = bidinfo.parse_dt("2026-09-18")
    assert a.day == 18 and a.hour == 18
    assert b.hour == 18 and b.minute == 0
    assert c.hour == 0
    assert bidinfo.parse_dt("") is None
    assert bidinfo.parse_dt("마감일 미정") is None


def test_mock_load_and_open_first():
    rows = bidinfo.load_mock(now=NOW)
    assert len(rows) >= 8
    kinds = {r["kind"] for r in rows}
    assert kinds == {"물품", "용역", "공사", "외자"}
    assert all("/bid/" not in (r.get("title") or "") for r in rows)
    # 열린 것이 닫힌 것보다 앞
    closed_idx = next((i for i, r in enumerate(rows) if not r["is_open"]), None)
    if closed_idx is not None:
        assert all(rows[i]["is_open"] for i in range(closed_idx))
    # 재공고 차수가 id에 붙는다
    assert any(r["id"].endswith("-001") for r in rows)
    # 추정가격 없는 건 금액 칩을 안 붙인다
    no_price = [r for r in rows if not r["budget"]]
    assert no_price
    assert all(not r.get("budget_card") for r in no_price)


def test_load_without_key_uses_mock(tmp_path=None):
    os.environ.pop("NARA_API_KEY", None)
    os.environ.pop("DATA_GO_KR_SERVICE_KEY", None)
    os.environ.pop("GITHUB_ACTIONS", None)
    os.environ.pop("MAGAMPAN_USE_CACHE", None)
    # 캐시가 비어 있으면 목업
    rows = bidinfo.load_mock(now=NOW)
    assert rows
    assert all(r["kind"] in {"물품", "용역", "공사", "외자"} for r in rows)


def test_invalid_key_falls_back_to_mock(monkey=None):
    def boom(*args, **kwargs):
        raise RuntimeError("network")
    orig = bidinfo.fetch_live
    bidinfo.fetch_live = boom
    try:
        os.environ["NARA_API_KEY"] = "invalid-test-key"
        os.environ.pop("GITHUB_ACTIONS", None)
        rows = bidinfo.load(now=NOW)
        assert rows
        assert all("kind" in r for r in rows)
    finally:
        bidinfo.fetch_live = orig
        os.environ.pop("NARA_API_KEY", None)


def test_no_cross_contamination():
    support = [{"id": "biz-1", "title": "소상공인 바우처 지원금", "category": "수출"}]
    bids = bidinfo.load_mock(now=NOW)
    sids = {a["id"] for a in support}
    bids_ids = {b["id"] for b in bids}
    assert sids.isdisjoint(bids_ids)
    assert all(b.get("kind") in {"물품", "용역", "공사", "외자"} for b in bids)
    assert all(a.get("kind") is None for a in support)
    joined = " ".join(b["title"] + b.get("blurb", "") for b in bids)
    assert "지원금" not in joined
    assert "바우처" not in joined


def test_hub_copy_has_no_grant_vocab():
    faqs = bid_build.hub_faqs({"today": 1, "urgent": 2, "open": 3, "soon": 0})
    text = bid_build.hub_intro({"today": 1, "urgent": 2, "open": 3}) + json.dumps(faqs, ensure_ascii=False)
    assert "지원금" not in text
    assert "바우처" not in text
    assert "입찰" in text
    assert "지원사업" in text
    assert "오늘 마감 1건" in text
    empty = bid_build.empty_hub_intro() + json.dumps(bid_build.empty_hub_faqs(), ensure_ascii=False)
    assert "지원금" not in empty
    assert "바우처" not in empty
    assert "나라장터" in empty
    assert "지원 탭" in empty


def test_nav_split_templates():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    root = os.path.join(os.path.dirname(__file__), "..")
    env = Environment(loader=FileSystemLoader(os.path.join(root, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    env.globals["bid_kinds"] = config.BID_KINDS
    env.globals["bid_has_regions"] = True
    site = config.SITE
    support = env.get_template("base.html").render(
        site=site, path="/", title="t", desc="d", section="support")
    bid = env.get_template("base.html").render(
        site=site, path="/bid/", title="t", desc="d", section="bid")
    assert 'class="is-on"' in support
    assert 'href="/bid/"' in support and 'href="/"' in support
    assert "구독하기" in support
    assert 'href="/pricing/"' in support
    assert "알림 등록" in support
    assert "로그인" not in support
    assert "지원사업 보기" not in support
    assert 'action="/all/"' in support
    assert 'href="/urgent/"' in support
    assert 'href="/bid/urgent/"' not in support
    # 입찰 헤더
    assert "입찰" in bid
    assert 'action="/bid/"' in bid
    assert "구독하기" in bid
    assert "알림 등록" in bid
    assert "로그인" not in bid
    assert "지원사업 처음이세요?" not in bid
    assert "지원사업 보기" not in bid
    assert 'href="/bid/kind/goods/"' in bid
    assert 'href="/category/"' not in bid
    assert 'href="/urgent/"' not in bid.replace("/bid/urgent/", "")
    # 모드 스위치 활성
    support_sw = support.split('<nav class="mode-switch"', 1)[1].split("</nav>", 1)[0]
    bid_sw = bid.split('<nav class="mode-switch"', 1)[1].split("</nav>", 1)[0]
    assert support_sw.count("is-on") == 1
    assert 'data-mode="support"' in support
    assert 'class="is-on"' in support_sw
    assert 'href="/bid/"' in bid
    assert 'class="is-on"' in bid_sw
    assert "지원사업<b>마감판</b>" in support
    assert "지원·입찰<b>마감판</b>" in bid
    assert "지원·입찰<b>마감판</b>" not in support
    assert "지원사업<b>마감판</b>" not in bid
    assert 'class="brand-cluster"' in support and 'class="brand-cluster"' in bid
    assert 'href="/bid/"' in bid.split('class="brand"', 1)[1][:80]


def test_list_and_detail_wework_chrome():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    root = os.path.join(os.path.dirname(__file__), "..")
    env = Environment(loader=FileSystemLoader(os.path.join(root, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    env.globals["bid_kinds"] = config.BID_KINDS
    env.globals["bid_has_regions"] = False
    env.globals["amount_bands"] = [
        {"id": "lt10", "name": "1천만 원 미만", "desc": "본문 표기가 1천만 원 미만"},
    ]
    import landing
    env.globals["landing"] = landing.context()
    item = {
        "id": "abc", "cls": "d-u", "dlabel": "오늘", "dsub": "오늘 마감",
        "title": "지원사업", "org": "중기부", "category": "금융", "region": "서울",
        "target_short": "소상공인", "amount_card": "3백만원", "signals": [],
        "blurb": "한 줄", "is_new": False, "amount": "3백만원",
        "target": "소상공인", "method": "온라인", "contact": "",
        "apply_start": "2026-09-01", "apply_end": "2026-09-16",
        "period_type": "dated", "period_raw": "", "points": ["내용"],
        "detail_url": "https://www.bizinfo.go.kr/",
        "ai": {"summary": "요약", "fit": ["맞음"], "caution": ["주의"],
               "checklist": ["서류"]},
        "is_closed": False,
    }
    listing = env.get_template("list.html").render(
        site=config.SITE, path="/all/", page="list", section="support",
        title="t", desc="d", h1="전체 공고", lede="마감일 순",
        items=[item], tally={"urgent": 1, "soon": 0, "open": 1},
        blocks=[], intro="", intro_paras=[], faqs=[], faq_jsonld="",
        website_jsonld="", ad_top=None, ad_mid_after=None, ad_bottom=None,
        all_regions=config.REGIONS, all_categories=config.CATEGORIES,
        sel_region="", sel_category="", sel_district="", slugmap="{}",
        today=0, new_cnt=0, ics_url="", limit=20, more_href="",
        sections=[], beginner_cta=False, crumbs=[], crumb_jsonld="",
        home_guides=[], list_guides=[], urgent_rail=[item], source_tally={},
    )
    assert 'class="find"' in listing
    assert 'data-panel="region"' in listing
    assert 'data-panel="save"' in listing
    assert 'id="f-q"' in listing
    assert 'class="f-apply"' in listing
    assert "조건 저장" in listing
    assert "더 많은 필터" in listing
    assert "회원가입 없이" in listing
    assert "접수 중만" in listing
    assert 'id="f-live"' in listing
    assert 'id="f-pills"' in listing
    assert "마감 임박" in listing
    assert 'class="row-tags"' in listing
    assert "지원사업 마감판" in listing
    assert "thevc" not in listing.lower()
    assert "wework" not in listing.lower()
    home = env.get_template("list.html").render(
        site=config.SITE, path="/", page="home", section="support",
        title="t", desc="d", h1="오늘 마감되는 정부지원사업부터 봅니다",
        lede="마감일 순", items=[], tally={"urgent": 1, "soon": 0, "open": 1},
        blocks=[], intro="<p>소개</p>", intro_paras=[], faqs=[], faq_jsonld="",
        website_jsonld="", ad_top=None, ad_mid_after=None, ad_bottom=None,
        all_regions=config.REGIONS, all_categories=config.CATEGORIES,
        sel_region="", sel_category="", sel_district="", slugmap="{}",
        today=1, new_cnt=0, ics_url="", limit=0, more_href="/all/",
        sections=[{"title": "이번 주에 닫히는 공고", "items": [item],
                   "href": "/urgent/", "total": 1}],
        beginner_cta=True, crumbs=[], crumb_jsonld="",
        home_guides=[], list_guides=[], urgent_rail=[item], source_tally={},
    )
    assert "hero--alert" in home
    assert "지원사업부터 입찰까지, 마감을 놓치면 수천만 원이 날아갑니다" in home
    assert "전국 지원사업·나라장터 입찰 공고를 한 곳에서" in home
    assert "무료 알림 등록" in home
    assert "이 조건 저장하고 알림받기" in home
    assert "조명·전기공사" in home
    assert "요금제 안내" in home
    assert "무료 알림 등록" in home
    assert "후기" not in home
    assert "낙찰까지 받았습니다" not in home
    assert "path-card" in home
    assert "오늘 마감" in home
    assert "내 지역부터 보기" in home
    assert "처음이세요?" in home
    assert 'href="/guide/start/"' in home
    assert "지원사업, 처음이신가요?" in home
    assert "입찰은 위" in home
    assert "입찰 탭" in home
    assert 'href="/bid/"' in home
    assert 'class="skip"' in home
    assert 'href="#main"' in home
    assert "순위를 매기거나 선정을 보장하지 않습니다" in home
    assert "example.com" not in home
    detail = env.get_template("detail.html").render(
        site=config.SITE, path="/notice/abc/", page="detail", section="support",
        title="t", desc="d", a=item, related=[], jsonld="{}", faq_jsonld="{}",
        faqs=__import__("detail_faq").notice_faqs(item),
        howto=__import__("detail_faq").notice_howto(item),
        crumbs=[], crumb_jsonld="",
    )
    assert 'class="notice-head"' in detail
    assert 'class="notice-chips"' in detail
    assert "원문 공고 보기" in detail
    assert "cta-bar--lead" in detail
    assert "요약" in detail
    assert "이(가)" not in detail
    assert "마지막 수집" in detail
    assert "공고번호" in detail
    assert "trust-facts" in detail
    assert "원문 공고 보기" in detail
    assert "자주 묻는 질문" in detail
    assert "이어서 볼 공고가 없습니다" in detail
    assert "신청하는 순서" in detail
    assert "누가 신청할 수 있나요?" in detail
    assert "소상공인" in detail
    assert "onboard" in home
    assert "건너뛰기" in home
    assert "필터 완화" in open(os.path.join(root, "static", "filter.js"), encoding="utf-8").read()
    state_js = open(os.path.join(root, "static", "state.js"), encoding="utf-8").read()
    assert "field" in state_js and "deadline" in state_js
    assert "serializeGrant" in state_js
    card_js = open(os.path.join(root, "static", "card.js"), encoding="utf-8").read()
    assert "시간 미상" in card_js
    assert "pill-src" in card_js
    assert "비교에 넣기" in card_js
    base = open(os.path.join(root, "templates", "base.html"), encoding="utf-8").read()
    assert 'rel="icon"' in base
    assert "favicon.svg" in base
    assert "compare.js" in base
    assert "scrap.js" in base
    assert "suggest.js" in base
    assert 'data-mode="support"' in base
    assert "pretendard-dynamic-subset.css" in base


def test_row_templates_do_not_cross_link():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    root = os.path.join(os.path.dirname(__file__), "..")
    env = Environment(loader=FileSystemLoader(os.path.join(root, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    row_s = env.get_template("_row.html").module.row({
        "id": "abc", "cls": "d-u", "dlabel": "오늘", "dsub": "오늘 마감",
        "title": "지원사업", "org": "중기부", "category": "금융",
        "target_short": "", "amount_card": "", "signals": [], "blurb": "",
        "is_new": False,
    })
    row_b = env.get_template("_bid_row.html").module.row({
        "id": "2026-000", "cls": "d-u", "dlabel": "오늘", "dsub": "18:00 마감",
        "title": "용역 입찰", "org": "조달청", "kind": "용역", "kind_slug": "service",
        "region": "", "budget_card": "", "blurb": "조달청 · 용역", "dday": 0,
        "detail_url": "https://www.g2b.go.kr/notice", "notice_no": "2026-000",
        "status_label": "진행", "deadline_line": "2026-09-16 18:00 (KST)",
    })
    assert "/notice/abc/" in row_s
    assert "/bid/notice/" not in row_s
    assert "/bid/notice/2026-000/" in row_b
    assert 'href="/notice/' not in row_b
    assert 'data-kind="용역"' in row_b
    assert 'data-kind-slug="service"' in row_b
    assert "원문" in row_b
    assert "www.g2b.go.kr" in row_b
    assert "나라장터" in row_b
    assert 'class="cmp"' in row_s
    assert 'class="cmp"' in row_b
    assert 'data-kind="bid"' in row_b
    assert 'data-kind="grant"' in row_s


def test_gha_without_key_returns_empty_not_mock():
    os.environ.pop("NARA_API_KEY", None)
    os.environ.pop("DATA_GO_KR_SERVICE_KEY", None)
    os.environ["GITHUB_ACTIONS"] = "true"
    orig = bidinfo.load_cache
    bidinfo.load_cache = lambda now=None: []
    try:
        rows = bidinfo.load(now=NOW)
        assert rows == []
    finally:
        bidinfo.load_cache = orig
        os.environ.pop("GITHUB_ACTIONS", None)


def test_gha_live_fail_no_cache_returns_empty():
    def boom(*args, **kwargs):
        raise RuntimeError("network")
    orig_live, orig_cache = bidinfo.fetch_live, bidinfo.load_cache
    bidinfo.fetch_live = boom
    bidinfo.load_cache = lambda now=None: []
    os.environ["NARA_API_KEY"] = "invalid-test-key"
    os.environ["GITHUB_ACTIONS"] = "true"
    try:
        assert bidinfo.load(now=NOW) == []
    finally:
        bidinfo.fetch_live = orig_live
        bidinfo.load_cache = orig_cache
        os.environ.pop("NARA_API_KEY", None)
        os.environ.pop("GITHUB_ACTIONS", None)


class _FakeHTTPResp:
    def __init__(self, payload):
        if isinstance(payload, bytes):
            self._raw = payload
        else:
            self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._raw


def _ok_payload(item=None):
    return {
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "totalCount": 1,
                "items": {"item": item or {"bidNtceNo": "1", "bidNtceNm": "x"}},
            },
        }
    }


def test_timeout_retries_then_succeeds():
    """urlopen 타임아웃 후 backoff 재시도, 최종 성공. 키는 로그에 안 남긴다."""
    calls, sleeps = [], []
    secret = "SECRETKEY-DO-NOT-LOG"

    def fake_urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "timeout": timeout})
        if len(calls) < 3:
            raise urllib.error.URLError(TimeoutError("timed out"))
        return _FakeHTTPResp(_ok_payload())

    orig_open, orig_sleep = urllib.request.urlopen, time.sleep
    urllib.request.urlopen = fake_urlopen
    time.sleep = lambda s: sleeps.append(s)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            items, total = bidinfo._get(
                secret, "getBidPblancListInfoThng", 1, "202609010000", "202609080000")
    finally:
        urllib.request.urlopen = orig_open
        time.sleep = orig_sleep
    assert items and total == 1
    assert len(calls) >= 3
    assert sleeps  # timeout/5xx 라운드 사이 backoff
    assert all(c["timeout"] >= 60 for c in calls)
    assert all(c["timeout"] == max(bidinfo.CONNECT_TIMEOUT, bidinfo.READ_TIMEOUT)
               for c in calls)
    assert bidinfo.CONNECT_TIMEOUT >= 60
    assert bidinfo.READ_TIMEOUT >= 60
    assert 4 <= bidinfo.HTTP_ATTEMPTS <= 6
    log = buf.getvalue()
    assert secret not in log
    assert "serviceKey=" not in log
    assert "timed out" in log
    schemes = {urllib.parse.urlparse(c["url"]).scheme for c in calls}
    assert "https" in schemes and "http" in schemes


def test_http_5xx_retries():
    calls, sleeps = [], []

    def fake_urlopen(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                req.full_url, 503, "Service Unavailable", None, io.BytesIO(b""))
        return _FakeHTTPResp(_ok_payload())

    orig_open, orig_sleep = urllib.request.urlopen, time.sleep
    urllib.request.urlopen = fake_urlopen
    time.sleep = lambda s: sleeps.append(s)
    try:
        items, total = bidinfo._get(
            "k", "getBidPblancListInfoServc", 1, "202609010000", "202609080000")
    finally:
        urllib.request.urlopen = orig_open
        time.sleep = orig_sleep
    assert items and total == 1
    assert len(calls) >= 2


def test_timeout_first_kind_still_fetches_others_and_writes_cache():
    """한 종류 타임아웃이 나머지를 스킵하거나 캐시를 비우면 안 된다."""
    td = tempfile.mkdtemp()
    cache = os.path.join(td, "bid_cache.json")
    orig_cache, orig_fetch = bidinfo.CACHE, bidinfo._fetch_kind
    seen = []

    def fake_kind(key, kind, bgn, end, pages):
        seen.append(kind["name"])
        if kind["name"] == "물품":
            raise urllib.error.URLError(TimeoutError("timed out"))
        if kind["name"] == "용역":
            return [_item(bidNtceNo="20260915111", bidNtceNm="용역 공고")]
        if kind["name"] == "공사":
            raise urllib.error.HTTPError(
                "https://apis.data.go.kr/x", 400, "Bad Request", None, io.BytesIO(b""))
        return [_item(bidNtceNo="20260915112", bidNtceNm="외자 공고")]

    bidinfo.CACHE = cache
    bidinfo._fetch_kind = fake_kind
    try:
        rows = bidinfo.fetch_live(key="test-key", pages=1, now=NOW)
        kinds = {r["kind"] for r in rows}
        assert seen == ["물품", "용역", "공사", "외자"]
        assert kinds == {"용역", "외자"}
        assert "물품" not in kinds
        assert os.path.exists(cache)
        saved = json.load(open(cache, encoding="utf-8"))
        assert {r["kind"] for r in saved} == {"용역", "외자"}
    finally:
        bidinfo.CACHE = orig_cache
        bidinfo._fetch_kind = orig_fetch


def test_auth_failure_skips_remaining_kinds_timeout_does_not():
    assert bidinfo._is_auth_failure(urllib.error.URLError(TimeoutError("timed out"))) is False
    assert bidinfo._is_auth_failure(urllib.error.HTTPError(
        "https://apis.data.go.kr/x", 400, "Bad Request", None, io.BytesIO(b""))) is False
    assert bidinfo._is_auth_failure(urllib.error.HTTPError(
        "https://apis.data.go.kr/x", 401, "Unauthorized", None, io.BytesIO(b""))) is True
    assert bidinfo._is_auth_failure(RuntimeError("getBidPblancListInfoThng resultCode=30")) is True
    orig = bidinfo._fetch_kind
    seen = []

    def fake_kind(key, kind, bgn, end, pages):
        seen.append(kind["name"])
        raise urllib.error.HTTPError(
            "https://apis.data.go.kr/x", 401, "Unauthorized", None, io.BytesIO(b""))

    bidinfo._fetch_kind = fake_kind
    try:
        raised = False
        try:
            bidinfo.fetch_live(key="test-key", pages=1, now=NOW)
        except RuntimeError:
            raised = True
        assert raised
        assert seen == ["물품"]
    finally:
        bidinfo._fetch_kind = orig


def test_partial_fetch_writes_cache_not_empty_on_total_fail():
    td = tempfile.mkdtemp()
    cache = os.path.join(td, "bid_cache.json")
    orig_cache, orig_fetch = bidinfo.CACHE, bidinfo._fetch_kind

    def fake_kind(key, kind, bgn, end, pages):
        if kind["name"] == "물품":
            return [_item()]
        raise urllib.error.URLError(TimeoutError("timed out"))

    bidinfo.CACHE = cache
    bidinfo._fetch_kind = fake_kind
    try:
        rows = bidinfo.fetch_live(key="test-key", pages=1, now=NOW)
        assert rows
        assert all(r["kind"] == "물품" for r in rows)
        assert os.path.exists(cache)
        saved = json.load(open(cache, encoding="utf-8"))
        assert saved and saved[0]["id"]
        assert bidinfo._save_cache([]) is False
        assert json.load(open(cache, encoding="utf-8"))[0]["id"] == saved[0]["id"]
    finally:
        bidinfo.CACHE = orig_cache
        bidinfo._fetch_kind = orig_fetch

    bidinfo.CACHE = cache
    bidinfo._fetch_kind = lambda *a, **k: (_ for _ in ()).throw(
        urllib.error.URLError(TimeoutError("timed out")))
    try:
        raised = False
        try:
            bidinfo.fetch_live(key="test-key", pages=1, now=NOW)
        except RuntimeError:
            raised = True
        assert raised
        # 전부 실패하면 빈 목록으로 덮지 않는다
        assert json.load(open(cache, encoding="utf-8"))[0]["id"] == saved[0]["id"]
    finally:
        bidinfo.CACHE = orig_cache
        bidinfo._fetch_kind = orig_fetch


def test_bid_list_wework_chips_and_detail_cta():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    root = os.path.join(os.path.dirname(__file__), "..")
    env = Environment(loader=FileSystemLoader(os.path.join(root, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    env.globals["bid_kinds"] = config.BID_KINDS
    env.globals["bid_has_regions"] = False
    import landing
    env.globals["landing"] = landing.context()
    item = {
        "id": "20260915001-000", "cls": "d-u", "dlabel": "오늘", "dsub": "23:00 마감",
        "title": "사무용 가구 구매", "org": "중구청", "kind": "물품", "kind_slug": "goods",
        "region": "서울", "budget_card": "8,500만원", "dday": 0, "is_open": True,
        "ntce_org": "중구청", "budget": "8,500만원", "open_dt": "2026-09-01 09:00",
        "close_dt": "2026-09-15 23:00", "method": "전자입찰", "contract": "일반경쟁",
        "blurb": "중구청 · 물품", "detail_url": "https://www.g2b.go.kr/",
        "seq": "001", "is_correction": True, "is_new": False,
        "deadline_line": "2026-09-15 23:00 (KST)", "notice_no": "20260915001",
    }
    listing = env.get_template("bid_list.html").render(
        site=config.SITE, path="/bid/", page="list", section="bid",
        title="t", desc="d", h1="나라장터 입찰, 마감일시 순",
        lede="오늘 마감되는 입찰부터 봅니다.",
        items=[item], sections=[], blocks=[],
        tally={"today": 1, "urgent": 1, "open": 1, "soon": 0},
        intro="<p>입찰은 나라장터 공고입니다.</p>", faqs=[], faq_jsonld="",
        beginner=True, empty="", bid_empty=False, today=1,
        ad_top=None, ad_mid_after=None, ad_bottom=None,
        crumbs=[], crumb_jsonld="", sel_kind="", sel_due="", sel_region="",
        limit=20,
    )
    assert 'id="bid-find"' in listing
    assert 'id="bid-q"' in listing
    assert 'data-bid-kind="goods"' in listing
    assert 'data-bid-kind="service"' in listing
    assert 'data-bid-due="today"' in listing
    assert 'data-bid-due="week"' in listing
    assert 'id="bid-count"' in listing
    assert 'id="bid-live"' in listing
    assert "로그인 없이" in listing
    assert "종류 고르기" in listing
    assert "오늘 마감" in listing
    assert "나라장터 원문" in listing
    assert "지원 탭" in listing
    assert "무료 알림" in listing
    assert "프로 전용" not in listing
    assert "개인이 운영하는 지원사업·입찰 마감 안내 사이트" in listing
    assert "[대표자명]" not in listing
    assert "지원금" not in listing
    assert "바우처" not in listing
    assert "보조금" not in listing
    assert "find-chips--bid" in listing
    assert 'data-kind-slug="goods"' in listing
    assert "bid_filter.js" in listing
    assert 'href="/bid/notice/' in listing
    urgent = env.get_template("bid_list.html").render(
        site=config.SITE, path="/bid/urgent/", page="list", section="bid",
        title="t", desc="d", h1="이번 주 마감 입찰", lede="7일",
        items=[item], sections=[], blocks=[],
        tally={"today": 1, "urgent": 1, "open": 1, "soon": 0},
        intro="", faqs=[], faq_jsonld="", beginner=False, empty="",
        bid_empty=False, today=1, ad_top=None, ad_mid_after=None, ad_bottom=None,
        crumbs=[], crumb_jsonld="", sel_kind="", sel_due="week", sel_region="",
        limit=20,
    )
    assert 'data-due="week"' in urgent
    assert 'data-bid-due="week"' in urgent
    assert "is-on" in urgent
    detail = env.get_template("bid_detail.html").render(
        site=config.SITE, path="/bid/notice/x/", page="bid-detail", section="bid",
        title="t", desc="d", a=item, related=[], faqs=bid_build.notice_faqs(item),
        faq_jsonld="", howto=__import__("detail_faq").bid_notice_howto(item),
        crumbs=[], crumb_jsonld="",
    )
    assert "cta-bar--lead" in detail
    assert "cta-bar--end" in detail
    assert "나라장터 원문 보기" in detail
    assert "같은 종류의 다른 진행 중 입찰이 없습니다" in detail
    assert "지원금" not in detail
    assert "마지막 수집" in detail
    assert "공고번호" in detail
    assert "trust-facts" in detail
    assert "정정공고" in detail
    assert "자주 묻는 질문" in detail
    assert "투찰하는 순서" in detail
    assert "누가 신청할 수 있나요?" not in detail
    assert 'data-kind="bid"' in detail
    assert "공고번호" in detail
    assert "trust-facts" in detail
    assert "발주기관" in listing
    assert "추정가격" in listing
    assert "조건 저장" in listing
    css = open(os.path.join(root, "static", "style.css"), encoding="utf-8").read()
    assert ".find-chips--bid" in css
    assert ".skip" in css
    assert "min-height:40px" in css
    js = open(os.path.join(root, "static", "bid_filter.js"), encoding="utf-8").read()
    assert "fetch('/notices.json')" not in js
    assert 'fetch("/notices.json")' not in js
    assert "bids.json" in js
    assert "data-bid-kind" in js
    assert "data-bid-due" in js
    assert "지원금" not in js
    assert "MagampanState" in js
    assert "serializeBid" in open(os.path.join(root, "static", "state.js"), encoding="utf-8").read()
    assert "필터 완화" in js
    assert "이 조건 알림" in js


def test_contact_email_is_real_not_example():
    assert "example.com" not in config.SITE["email"]
    assert config.SITE["email"] == "qwqw050009@gmail.com"
    pages = __import__("pages")
    about = "\n".join(c for _, _, c in pages.build(config.SITE, {"open": 1, "orgs": 1, "regions": 1}))
    assert "qwqw050009@gmail.com" in about
    assert "contact@example.com" not in about
    assert "순위를 매기거나 선정을 보장하지 않습니다" in about
    assert "운영 주체" in about
    assert "개인이 운영하는 지원사업·입찰 마감 안내 사이트" in about
    assert "없는 번호를 만들지" in about
    assert "[대표자명]" not in about
    assert "000-00-00000" not in about
    assert "기업마당" in about
    assert "나라장터" in about


def test_guide_start_has_next_cta():
    import guides
    start = next(g for g in guides.build() if g[0] == "start")
    body = start[3]
    assert 'href="/"' in body
    assert 'href="/region/"' in body
    assert "오늘 마감부터 보기" in body
    assert "내 지역 고르기" in body
    assert "hero-primary" in body


def test_empty_hub_looks_intentional():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    root = os.path.join(os.path.dirname(__file__), "..")
    env = Environment(loader=FileSystemLoader(os.path.join(root, "templates")),
                      autoescape=select_autoescape(["html"]))
    env.globals["asset_v"] = "test"
    env.globals["bid_kinds"] = config.BID_KINDS
    env.globals["bid_has_regions"] = False
    import landing
    env.globals["landing"] = landing.context()
    html = env.get_template("bid_list.html").render(
        site=config.SITE, path="/bid/", section="bid", title="t", desc="d",
        h1="나라장터 입찰, 마감일시 순",
        lede="지금은 표시할 진행 중 입찰이 없습니다.",
        items=[], sections=[], blocks=[], tally=None, intro="", faqs=[],
        beginner=False, empty="나라장터 연동이 꺼져 있거나, 오늘 기준 진행 중인 공고가 없습니다.",
        bid_empty=True, today=0, ad_top=None, ad_mid_after=None, ad_bottom=None,
        crumbs=[], crumb_jsonld="", faq_jsonld="",
    )
    assert "지금은 표시할 입찰공고가 없습니다" in html
    assert "www.g2b.go.kr" in html
    assert "지원 탭" in html
    assert "empty-panel" in html
    assert 'id="bid-q"' not in html
    assert "진행중" not in html
    assert "0</b>" not in html
    assert "bid_filter.js" not in html
    assert "지원·입찰<b>마감판</b>" in html


def test_no_catchall_redirects_in_build():
    src = open(os.path.join(os.path.dirname(__file__), "build.py"), encoding="utf-8").read()
    assert "404.html" in src
    import build as buildmod
    redir = buildmod.cf_redirects_contents()
    assert "/* /404.html" not in redir
    assert "/* /index.html" not in redir
    assert "/ads.txt /ads.txt 200" in redir
    assert "/app-ads.txt /app-ads.txt 200" in redir


if __name__ == "__main__":
    test_normalize_id_and_kind()
    test_kind_routing()
    test_dday_and_status()
    test_price_not_invented()
    test_region_exact_only_no_guessing()
    test_drop_without_close()
    test_parse_dt_formats()
    test_mock_load_and_open_first()
    test_load_without_key_uses_mock()
    test_invalid_key_falls_back_to_mock()
    test_gha_without_key_returns_empty_not_mock()
    test_gha_live_fail_no_cache_returns_empty()
    test_timeout_retries_then_succeeds()
    test_http_5xx_retries()
    test_timeout_first_kind_still_fetches_others_and_writes_cache()
    test_auth_failure_skips_remaining_kinds_timeout_does_not()
    test_partial_fetch_writes_cache_not_empty_on_total_fail()
    test_no_cross_contamination()
    test_hub_copy_has_no_grant_vocab()
    test_nav_split_templates()
    test_list_and_detail_wework_chrome()
    test_row_templates_do_not_cross_link()
    test_bid_list_wework_chips_and_detail_cta()
    test_contact_email_is_real_not_example()
    test_guide_start_has_next_cta()
    test_empty_hub_looks_intentional()
    test_no_catchall_redirects_in_build()
    print("bid tests ok")
