# -*- coding: utf-8 -*-
"""색인 축소 정책(index_policy)과 gone.json 테스트."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SKIP_LIVE_GUARD", "1")

import index_policy as ip


def test_closed_notice_noindex_even_if_rich():
    a = {"is_open": False, "is_closed": True}
    assert not ip.notice_indexable(a, "/notice/x/", body_len=2000)


def test_open_rich_notice_indexed():
    a = {"is_open": True, "is_closed": False}
    assert ip.notice_indexable(a, "/notice/x/", body_len=ip.NOTICE_RICH_MIN)
    assert not ip.notice_indexable(a, "/notice/x/", body_len=ip.NOTICE_RICH_MIN - 1)
    assert not ip.notice_indexable(a, "/notice/x/", thin=True, body_len=5000)


def test_keep_indexed_wins():
    a = {"is_open": False, "is_closed": True}
    assert ip.notice_indexable(a, "/notice/x/", keep={"/notice/x/"}, thin=True)
    assert ip.bid_indexable("/bid/notice/1/", keep={"/bid/notice/1/"})


def test_bids_not_indexed_by_default():
    assert not ip.bid_indexable("/bid/notice/1/")
    assert not ip.bid_indexable("/bid/notice/1/", keep={"/bid/notice/1/"}, canonical_path="/bid/notice/2/")


def test_list_permutations():
    few = [{"is_open": True}] * (ip.LIST_MIN_OPEN - 1)
    many = [{"is_open": True}] * ip.LIST_MIN_OPEN
    assert ip.list_indexable("/region/seoul/", few)
    assert ip.list_indexable("/category/startup/", [])
    assert not ip.list_indexable("/region/seoul/gangnam/", few)
    assert ip.list_indexable("/region/seoul/gangnam/", many)
    assert ip.list_indexable("/region/seoul/gangnam/", few, keep={"/region/seoul/gangnam/"})


def test_gone_json():
    import build
    written = {"index.html", "region/seoul/index.html", "bid/kind/goods/index.html",
               "category/startup/index.html", "notice/live/index.html", "bid/notice/B2/index.html"}
    cats = {"창업": {"slug": "startup"}}
    gj = build.gone_json(written, {"old": {"category": "창업"}, "live": {"category": "창업"},
                                   "nocat": {"category": "없음"}},
                         {"B1": "goods", "B2": "goods", "B3": "nokind"}, cats)
    assert gj["n"] == {"old": "/category/startup/"}
    assert gj["b"] == {"B1": "/bid/kind/goods/"}
    assert "/region/seoul/" in gj["hubs"] and "/notice/live/" not in gj["hubs"]


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("ok")
