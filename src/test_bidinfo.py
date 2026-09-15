# -*- coding: utf-8 -*-
"""입찰 정규화·D-day·종류 라우팅·지원/입찰 분리 회귀."""
import json
import os
import sys
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
    assert "지원사업 처음이세요?" in support
    assert "지원사업 보기" not in support
    assert 'action="/all/"' in support
    assert 'href="/urgent/"' in support
    assert 'href="/bid/urgent/"' not in support
    # 입찰 헤더
    assert "입찰" in bid
    assert 'action="/bid/"' in bid
    assert "지원사업 보기" in bid
    assert "지원사업 처음이세요?" not in bid
    assert 'href="/bid/kind/goods/"' in bid
    assert 'href="/category/"' not in bid
    assert 'href="/urgent/"' not in bid.replace("/bid/urgent/", "")
    # 모드 스위치 활성
    assert support.split("mode-switch", 1)[1].split("</nav>", 1)[0].count("is-on") == 1
    assert 'href="/" class="is-on"' in support.replace("\n", " ") or 'href="/" class="is-on"' in support
    assert 'href="/bid/" class="is-on"' in bid or 'class="is-on">입찰' in bid


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
        "title": "용역 입찰", "org": "조달청", "kind": "용역",
        "region": "", "budget_card": "", "blurb": "조달청 · 용역",
    })
    assert "/notice/abc/" in row_s
    assert "/bid/notice/" not in row_s
    assert "/bid/notice/2026-000/" in row_b
    assert 'href="/notice/' not in row_b


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
    test_no_cross_contamination()
    test_hub_copy_has_no_grant_vocab()
    test_nav_split_templates()
    test_row_templates_do_not_cross_link()
    print("bid tests ok")
